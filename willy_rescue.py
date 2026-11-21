"""Rescue helper for Willy: find, open and repair a PC's installed Linux.

Used from a live session (the rescue USB) when the PC's own Linux won't boot.
Every command it runs is shown to the user and goes through Willy's normal
approval guardrails first. Probing mounts are read-only and replay no journals,
so nothing on the PC's disk changes until the user explicitly asks for repairs.

Created by Wilson Sumanang.
"""

import json
import os
import re
import shlex

TARGET = "/mnt/willy-target"
PROBE = "/mnt/willy-probe"
LINUX_FS = {"ext4", "ext3", "ext2", "btrfs", "xfs", "f2fs", "jfs"}
BTRFS_ROOT_SUBVOLS = ["", "@", "root", "@rootfs", "rootfs"]


# --- Detection (pure functions, unit-tested) ---------------------------------

def is_live_session(cmdline=None, exists=os.path.exists):
    """True when running from a live USB/DVD (Ubuntu casper, Debian live, etc.)."""
    if cmdline is None:
        try:
            with open("/proc/cmdline") as fh:
                cmdline = fh.read()
        except OSError:
            cmdline = ""
    if re.search(r"\bboot=(casper|live)\b|\brd\.live\.image\b|\barchisobasedir=", cmdline):
        return True
    return any(exists(p) for p in ("/rofs", "/run/live/medium", "/run/initramfs/live"))


def parse_lsblk(json_text):
    """Flatten `lsblk -J -b -o NAME,PATH,SIZE,FSTYPE,MOUNTPOINT,TYPE,LABEL,UUID,TRAN,RM`.

    Each entry gets the parent disk's transport/removable flags and a
    `ventoy_disk` flag when the disk holds the Willy/Ventoy stick itself.
    """
    data = json.loads(json_text)
    flat = []

    def walk(devs, disk):
        for d in devs or []:
            entry = {k: d.get(k) for k in ("name", "path", "size", "fstype", "mountpoint",
                                            "type", "label", "uuid", "tran", "rm")}
            if entry["path"] is None and entry["name"]:
                entry["path"] = "/dev/" + entry["name"]
            this_disk = disk if disk is not None else entry
            entry["disk"] = this_disk["path"]
            entry["tran"] = entry["tran"] or this_disk.get("tran")
            flat.append(entry)
            walk(d.get("children"), this_disk)

    walk(data.get("blockdevices"), None)
    ventoy_disks = {e["disk"] for e in flat if (e.get("label") or "") in ("Ventoy", "VTOYEFI")}
    for e in flat:
        e["ventoy_disk"] = e["disk"] in ventoy_disks
    return flat


def parse_blkid_export(text):
    """Parse `blkid -o export` into {devname: {"TYPE": ..., "LABEL": ..., "UUID": ...}}."""
    result, current = {}, {}
    for line in text.splitlines() + [""]:
        line = line.strip()
        if not line:
            if current.get("DEVNAME"):
                result[current["DEVNAME"]] = current
            current = {}
            continue
        key, _, val = line.partition("=")
        current[key] = val
    return result


def fill_from_blkid(devices, blkid):
    """lsblk gets filesystem types from udev; without udev (minimal systems, containers)
    they are empty. Fill the gaps from blkid, which reads the disks directly."""
    for e in devices:
        info = blkid.get(e["path"])
        if not info:
            continue
        if not e.get("fstype") and info.get("TYPE"):
            e["fstype"] = info["TYPE"]
        if not e.get("label") and info.get("LABEL"):
            e["label"] = info["LABEL"]
        if not e.get("uuid") and info.get("UUID"):
            e["uuid"] = info["UUID"]
    ventoy_disks = {e["disk"] for e in devices if (e.get("label") or "") in ("Ventoy", "VTOYEFI")}
    for e in devices:
        e["ventoy_disk"] = e["disk"] in ventoy_disks
    return devices


def find_candidates(devices):
    """Split devices into (linux_filesystems, locked_luks, inactive_lvm)."""
    linux, locked, lvm = [], [], []
    for e in devices:
        if e["ventoy_disk"]:
            continue
        fs = (e.get("fstype") or "").lower()
        mp = e.get("mountpoint") or ""
        if fs in LINUX_FS and e.get("type") in ("part", "lvm", "crypt", "disk", "loop", "md", "raid1"):
            if mp in ("/", "[SWAP]") or mp.startswith(("/rofs", "/cdrom", "/run/live", "/media/cdrom")):
                continue
            linux.append(e)
        elif fs == "crypto_luks" and not _has_child(devices, e):
            locked.append(e)
        elif fs == "lvm2_member" and not _has_child(devices, e):
            lvm.append(e)
    return linux, locked, lvm


def _has_child(devices, parent):
    idx = devices.index(parent)
    # lsblk lists children right after their parent; a deeper entry with the
    # same disk directly following means the device is open/active.
    if idx + 1 < len(devices):
        nxt = devices[idx + 1]
        return nxt["disk"] == parent["disk"] and nxt.get("type") in ("crypt", "lvm")
    return False


def ro_mount_options(fstype, subvol=""):
    """Read-only options that also skip journal replay, so nothing is written."""
    fs = (fstype or "").lower()
    if fs in ("ext3", "ext4"):
        opts = "ro,noload"
    elif fs == "xfs":
        opts = "ro,norecovery"
    elif fs == "btrfs":
        opts = "ro,rescue=nologreplay"
    else:
        opts = "ro"
    if subvol:
        opts += ",subvol=" + subvol
    return opts


def parse_os_release(text):
    info = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            info[key.strip()] = val.strip().strip('"')
    return info


def fstab_extra_mounts(fstab_text):
    """Return [(source, mountpoint)] for /boot and /boot/efi entries in a target fstab."""
    wanted = ("/boot", "/boot/efi", "/efi")
    out = []
    for line in fstab_text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) >= 2 and fields[1] in wanted:
            out.append((fields[0], fields[1]))
    out.sort(key=lambda m: m[1].count("/"))  # mount /boot before /boot/efi
    return out


def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%.0f %s" if unit in ("B", "KB") else "%.1f %s") % (n, unit)
        n /= 1024.0


# --- The interactive helper ------------------------------------------------------

class Rescue(object):
    """Drives /rescue. `ui` provides approve(title, cmds) -> bool, run(cmd) -> (code, out),
    run_interactive(cmd) -> code, and say(text)."""

    def __init__(self, ui):
        self.ui = ui
        self.target = None      # dict: device, fstype, subvol, pretty, mounted_by_us, mountpoint
        self.repair_ready = False

    # -- helpers --
    def _q(self, s):
        return shlex.quote(s)

    def _scan(self):
        code, out = self.ui.run("lsblk -J -b -o NAME,PATH,SIZE,FSTYPE,MOUNTPOINT,TYPE,LABEL,UUID,TRAN,RM")
        if code != 0:
            raise RuntimeError("could not list disks: " + out.strip())
        devices = parse_lsblk(out)
        if any(not e.get("fstype") and e.get("type") in ("part", "loop", "lvm", "crypt", "md")
               for e in devices):
            # Reading filesystem signatures is read-only but needs root.
            code, out = self.ui.run("sudo -n blkid -o export 2>/dev/null || blkid -o export 2>/dev/null")
            if out.strip():
                fill_from_blkid(devices, parse_blkid_export(out))
        return devices

    def status(self):
        if not self.target:
            return "No installed system is open. Type /rescue to find one."
        t = self.target
        mode = "read-write, ready for repairs" if self.repair_ready else "read-only"
        return "%s (%s) is open at %s, %s." % (t["pretty"], t["device"], t["mountpoint"], mode)

    # -- /rescue --
    def open(self):
        if self.target:
            self.ui.say(self.status())
            return None
        devices = self._scan()
        linux, locked, lvm = find_candidates(devices)

        if locked or lvm:
            unlocked = self._unlock(locked, lvm)
            if unlocked:
                devices = self._scan()
                linux, _, _ = find_candidates(devices)

        if not linux:
            self.ui.say("Willy didn't find any Linux system on this PC's disks.")
            return None

        found = self._probe(linux)
        if not found:
            self.ui.say("Willy found Linux partitions but none of them holds an installed system "
                        "(no /etc/os-release).")
            return None

        choice = found[0]
        if len(found) > 1:
            self.ui.say("Willy found more than one installed Linux:")
            for i, f in enumerate(found, 1):
                self.ui.say("  %d) %s on %s (%s)" % (i, f["pretty"], f["device"], human_size(f["size"])))
            pick = self.ui.ask("  Which one should Willy open? [1-%d, Enter to cancel]: " % len(found))
            if not pick.isdigit() or not 1 <= int(pick) <= len(found):
                self.ui.say("Cancelled. Nothing was mounted.")
                return None
            choice = found[int(pick) - 1]

        if not self._mount_target(choice):
            return None
        return self._gather_context()

    def _unlock(self, locked, lvm):
        changed = False
        for dev in locked:
            name = "willy-crypt-" + os.path.basename(dev["path"])
            self.ui.say("An encrypted partition was found at %s (%s). To look inside it, it has to "
                        "be unlocked with its passphrase. You type the passphrase yourself; Willy "
                        "never sees it." % (dev["path"], human_size(dev["size"])))
            cmd = "sudo cryptsetup open %s %s" % (self._q(dev["path"]), name)
            if self.ui.approve("Unlock the encrypted partition", [cmd]):
                if self.ui.run_interactive(cmd) == 0:
                    changed = True
        if lvm or changed:
            cmd = "sudo vgchange -ay"
            self.ui.say("This PC uses LVM volumes, which have to be activated before Willy can look inside.")
            if self.ui.approve("Activate LVM volumes (nothing on disk is changed)", [cmd]):
                self.ui.run(cmd)
                changed = True
        return changed

    def _probe(self, linux):
        cmds = ["sudo mkdir -p %s" % PROBE]
        self.ui.say("Willy found %d Linux partition(s). To see which one is the installed system, "
                    "it will open each one read-only and read /etc/os-release. Nothing on the "
                    "disk is written, and each one is closed again straight away." % len(linux))
        for e in linux:
            if e.get("mountpoint"):
                continue
            cmds.append("sudo mount -o %s %s %s" % (ro_mount_options(e["fstype"]), self._q(e["path"]), PROBE))
            cmds.append("sudo umount %s" % PROBE)
        if not self.ui.approve("Look for the installed system (read-only)", cmds):
            return []
        self.ui.run(cmds[0])

        found = []
        for e in linux:
            if e.get("mountpoint"):
                info, subvol = self._read_os_release(e["mountpoint"], e["fstype"])
                if info:
                    found.append(self._found(e, info, subvol, mounted_at=e["mountpoint"]))
                continue
            code, out = self.ui.run("sudo mount -o %s %s %s" % (ro_mount_options(e["fstype"]),
                                                                 self._q(e["path"]), PROBE))
            if code != 0:
                continue
            info, subvol = self._read_os_release(PROBE, e["fstype"])
            self.ui.run("sudo umount %s" % PROBE)
            if info:
                found.append(self._found(e, info, subvol))
        return found

    def _read_os_release(self, root, fstype):
        subvols = BTRFS_ROOT_SUBVOLS if (fstype or "").lower() == "btrfs" else [""]
        for sv in subvols:
            path = os.path.join(root, sv, "etc/os-release") if sv else os.path.join(root, "etc/os-release")
            code, out = self.ui.run("cat %s 2>/dev/null || sudo cat %s" % (self._q(path), self._q(path)))
            if code == 0 and "NAME=" in out:
                return parse_os_release(out), sv
        return None, ""

    def _found(self, e, info, subvol, mounted_at=None):
        pretty = info.get("PRETTY_NAME") or info.get("NAME") or "Linux"
        return {"device": e["path"], "fstype": e["fstype"], "size": e["size"], "subvol": subvol,
                "pretty": pretty, "already_mounted": mounted_at}

    def _mount_target(self, f):
        if f["already_mounted"]:
            root = os.path.join(f["already_mounted"], f["subvol"]) if f["subvol"] else f["already_mounted"]
            self.target = dict(f, mountpoint=root, mounted_by_us=False)
            self.ui.say("%s is already open at %s; Willy will use it there." % (f["pretty"], root))
            return True
        cmds = ["sudo mkdir -p %s" % TARGET,
                "sudo mount -o %s %s %s" % (ro_mount_options(f["fstype"], f["subvol"]),
                                            self._q(f["device"]), TARGET)]
        self.ui.say("Willy will open %s (%s) read-only at %s so it can read its logs and settings."
                    % (f["pretty"], f["device"], TARGET))
        if not self.ui.approve("Open the installed system read-only", cmds):
            return False
        for cmd in cmds:
            code, out = self.ui.run(cmd)
            if code != 0:
                self.ui.say("Opening it failed: " + out.strip())
                return False
        self.target = dict(f, mountpoint=TARGET, mounted_by_us=True)
        return True

    def _gather_context(self):
        t = self.target["mountpoint"]
        q = self._q
        jdir = q(os.path.join(t, "var/log/journal"))
        checks = [
            ("Kernels in /boot", "ls -1 %s 2>/dev/null | grep -E 'vmlinuz|initrd|initramfs' | tail -n 8"
             % q(os.path.join(t, "boot"))),
            ("Its /etc/fstab", "grep -v '^#' %s 2>/dev/null | sed '/^$/d'" % q(os.path.join(t, "etc/fstab"))),
            ("Disk space", "df -h %s | tail -n 1" % q(t)),
            ("Recent boots", "sudo journalctl -D %s --list-boots --no-pager 2>/dev/null | tail -n 4" % jdir),
            ("Errors from its last boot", "sudo journalctl -D %s -b -p err --no-pager -q 2>/dev/null | tail -n 40"
             % jdir),
            ("Errors from the boot before", "sudo journalctl -D %s -b -1 -p err --no-pager -q 2>/dev/null "
             "| tail -n 20" % jdir),
            ("Recent package changes", "tail -n 25 %s 2>/dev/null || tail -n 25 %s 2>/dev/null"
             % (q(os.path.join(t, "var/log/apt/history.log")), q(os.path.join(t, "var/log/dnf.log")))),
            ("Crash records saved by firmware", "ls /sys/fs/pstore 2>/dev/null | head"),
        ]
        cmds = [c for _, c in checks]
        self.ui.say("Willy will now read the installed system's logs and settings (read-only).")
        if not self.ui.approve("Read the installed system's logs", cmds):
            return None
        parts = ["Installed system: %s on %s, opened read-only at %s." % (
            self.target["pretty"], self.target["device"], t)]
        for label, cmd in checks:
            _, out = self.ui.run(cmd)
            out = out.strip() or "(nothing found)"
            if len(out) > 1500:
                out = out[:700] + "\n...\n" + out[-700:]
            parts.append("### %s\n%s" % (label, out))
        return "\n\n".join(parts)

    # -- /rescue repair --
    def repair(self):
        if not self.target:
            self.ui.say("Open the installed system first with /rescue.")
            return None
        if self.repair_ready:
            self.ui.say(self.status())
            return None
        t = self.target["mountpoint"]
        q = self._q
        cmds = []
        if self.target["mounted_by_us"]:
            sub = (",subvol=" + self.target["subvol"]) if self.target["subvol"] else ""
            cmds += ["sudo umount %s" % t,
                     "sudo mount -o rw%s %s %s" % (sub, q(self.target["device"]), t)]
        _, fstab = self.ui.run("cat %s 2>/dev/null" % q(os.path.join(t, "etc/fstab")))
        for source, mp in fstab_extra_mounts(fstab):
            cmds.append("sudo mount %s %s" % (q(source), q(t + mp)))
        cmds += ["sudo mount --rbind /dev %s/dev" % t,
                 "sudo mount -t proc proc %s/proc" % t,
                 "sudo mount --rbind /sys %s/sys" % t,
                 "sudo mount --bind /run %s/run" % t]
        self.ui.say("To repair %s, Willy has to open it read-write and connect it to this live "
                    "system so repair tools (GRUB, initramfs, package manager) can run inside it. "
                    "From now on changes are real, so back up anything important first."
                    % self.target["pretty"])
        if not self.ui.approve("Prepare the installed system for repairs", cmds):
            return None
        for cmd in cmds:
            code, out = self.ui.run(cmd)
            if code != 0 and "already mounted" not in out:
                self.ui.say("Step failed: %s\n%s" % (cmd, out.strip()))
                return None
        self.repair_ready = True
        return ("The installed system %s is now open read-write at %s and ready for repairs. "
                "Run commands inside it with: sudo chroot %s <command>  (for example "
                "`sudo chroot %s update-grub`)." % (self.target["pretty"], t, t, t))

    # -- /rescue off --
    def close(self):
        if not self.target:
            self.ui.say("Nothing is open.")
            return None
        t = self.target["mountpoint"]
        if not self.target["mounted_by_us"] and not self.repair_ready:
            self.target = None
            self.ui.say("Done. Willy stopped using it (it was already open before /rescue).")
            return "The installed system is no longer open in rescue mode."
        cmd = "sync; sudo umount -R %s || sudo umount -R -l %s" % (t, t)
        if not self.ui.approve("Close the installed system safely", [cmd]):
            return None
        code, out = self.ui.run(cmd)
        if code != 0:
            self.ui.say("Closing reported a problem: " + out.strip())
        self.target = None
        self.repair_ready = False
        self.ui.say("The installed system is closed. It is now safe to restart the PC.")
        return "The installed system was closed with /rescue off."
