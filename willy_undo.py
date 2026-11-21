"""Undo for Willy: back up what a command will change, and put it back on /undo.

Before an approved "change" or "delete" command runs, Willy works out which
files it touches, saves them in a tar archive (tar keeps permissions and
owners even when the archive sits on the exFAT USB stick), and records the
step in a journal. /undo restores the most recent step. Restores also go
through Willy's approval guardrails.

Created by Wilson Sumanang.
"""

import datetime as dt
import json
import os
import shlex
import subprocess

MAX_BACKUP_BYTES = 200 * 1024 * 1024
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
SYSTEMCTL_INVERSE = {"enable": "disable", "disable": "enable", "mask": "unmask",
                     "unmask": "mask", "start": "stop", "stop": "start"}
NOT_UNDOABLE = {
    "packages": ("apt", "apt-get", "aptitude", "dnf", "yum", "zypper", "pacman", "rpm", "dpkg",
                 "snap", "flatpak", "pip", "pip3"),
    "disks": ("mkfs", "mkswap", "wipefs", "fdisk", "sfdisk", "gdisk", "sgdisk", "cfdisk", "parted",
              "dd", "shred", "cryptsetup"),
    "boot": ("grub-install", "update-initramfs", "mkinitcpio", "dracut", "efibootmgr", "bootctl"),
    "power": ("reboot", "shutdown", "poweroff", "halt"),
}
GENERATED = {"update-grub": ["/boot/grub/grub.cfg"], "update-grub2": ["/boot/grub/grub.cfg"]}


# --- Planning (pure, unit-tested) ---------------------------------------------

class Plan(object):
    def __init__(self):
        self.files = []       # existing paths to back up (absolute, host view)
        self.created = []     # paths the command may create (removed on undo)
        self.inverse = []     # commands that reverse service changes
        self.notes = []       # plain-English notes for the user
        self.not_undoable = []

    @property
    def undoable(self):
        return bool(self.files or self.created or self.inverse)

    def describe(self):
        lines = []
        if self.files:
            lines.append("Undo: Willy will back up %s first." % _list(self.files))
        if self.created:
            lines.append("Undo: %s will be removed again on /undo." % _list(self.created))
        if self.inverse:
            lines.append("Undo: reversible with: %s" % "; ".join(self.inverse))
        for what in self.not_undoable:
            lines.append("Undo: NOT available for %s. It can't be reversed automatically." % what)
        lines.extend(self.notes)
        if not lines:
            lines.append("Undo: nothing to back up for this command.")
        return lines


def _list(paths, limit=4):
    shown = ", ".join(paths[:limit])
    return shown + (" and %d more" % (len(paths) - limit) if len(paths) > limit else "")


def split_commands(cmd):
    """Tokenize a shell command and split it into simple commands (lists of words)
    plus redirect targets."""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        tokens = cmd.split()
    commands, redirects, current = [], [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            if current:
                commands.append(current)
            current = []
        elif tok in REDIRECTS or (tok.endswith(">") and tok.rstrip(">").isdigit()):
            if current and current[-1].isdigit() and tok in REDIRECTS:
                current.pop()  # the "2" in "2>file"
            if i + 1 < len(tokens):
                redirects.append(tokens[i + 1])
                i += 1
        elif tok in ("<", "<<", "<<<", ">&", "<&"):
            if current and current[-1].isdigit():
                current.pop()  # the "2" in "2>&1"
            i += 1
        else:
            current.append(tok)
        i += 1
    if current:
        commands.append(current)
    return commands, redirects


def _strip_prefix(words):
    """Drop sudo/env/etc. Returns (words, root) where root is a chroot dir or ''."""
    root = ""
    changed = True
    while words and changed:
        changed = False
        w = os.path.basename(words[0])
        if w in ("sudo", "doas", "pkexec", "nice", "ionice", "nohup", "time", "env", "command"):
            words = words[1:]
            while words and (words[0].startswith("-") or "=" in words[0]):
                if words[0] in ("-u", "-g") and len(words) > 1:
                    words = words[1:]
                words = words[1:]
            changed = True
        elif w == "chroot" and len(words) > 1:
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[1:]
            if words:
                root = words[0]
                words = words[1:]
            changed = True
        elif "=" in words[0] and not words[0].startswith("-"):
            words = words[1:]
            changed = True
    return words, root


def _operands(args):
    out, end = [], False
    for a in args:
        if a == "--":
            end = True
            continue
        if not end and a.startswith("-") and a != "-":
            continue
        out.append(a)
    return out


def plan_command(cmd, cwd="/", exists=os.path.exists, isdir=os.path.isdir):
    """Work out what `cmd` will change and how to reverse it."""
    plan = Plan()
    commands, redirects = split_commands(cmd)
    sudo_prefix = "sudo " if "sudo" in cmd.split() else ""

    def resolve(path, root=""):
        if not path or path == "-" or path.startswith("/dev/") or path.startswith("/proc/"):
            return None
        path = os.path.expanduser(path)
        if root:
            path = root.rstrip("/") + "/" + path.lstrip("/") if path.startswith("/") else \
                os.path.join(root, path)
        elif not path.startswith("/"):
            path = os.path.join(cwd, path)
        return os.path.normpath(path)

    def touch(path, root=""):
        p = resolve(path, root)
        if not p:
            return
        if exists(p):
            if p not in plan.files:
                plan.files.append(p)
        elif p not in plan.created:
            plan.created.append(p)

    for target in redirects:
        touch(target)

    for words in commands:
        words, root = _strip_prefix(words)
        if not words:
            continue
        prog = os.path.basename(words[0])
        args = words[1:]
        ops = _operands(args)

        for kind, progs in NOT_UNDOABLE.items():
            if prog in progs or any(prog.startswith(p + ".") for p in progs):
                label = {"packages": "installing or removing software",
                         "disks": "disk and partition changes",
                         "boot": "bootloader and initramfs changes",
                         "power": "restarting or powering off"}[kind]
                if label not in plan.not_undoable:
                    plan.not_undoable.append(label)
        if prog in GENERATED:
            for p in GENERATED[prog]:
                touch(p, root)
        elif prog in ("grub-mkconfig", "grub2-mkconfig"):
            if "-o" in args and args.index("-o") + 1 < len(args):
                touch(args[args.index("-o") + 1], root)
        elif prog == "sed" and any(a.startswith("-i") or a.startswith("--in-place") for a in args):
            files = ops if any(a in ("-e", "-f") or a.startswith(("--expression", "--file")) for a in args) \
                else ops[1:]
            for f in files:
                touch(f, root)
        elif prog == "tee":
            for f in ops:
                touch(f, root)
        elif prog in ("cp", "mv", "install", "ln", "rsync") and len(ops) >= 2:
            dest, sources = ops[-1], ops[:-1]
            d = resolve(dest, root)
            if d and isdir(d):
                for s in sources:
                    touch(os.path.join(dest, os.path.basename(s.rstrip("/"))), root)
            else:
                touch(dest, root)
            if prog == "mv":
                for s in sources:
                    touch(s, root)
        elif prog in ("rm", "unlink", "shred", "truncate", "rmdir"):
            for f in ops:
                if prog == "truncate" and f.lstrip("-").isdigit():
                    continue
                touch(f, root)
        elif prog in ("chmod", "chown", "chgrp") and len(ops) >= 2:
            for f in ops[1:]:
                touch(f, root)
        elif prog in ("chattr", "setfacl"):
            for f in ops:
                if not f.startswith(("+", "=")) and "::" not in f:
                    touch(f, root)
        elif prog in ("touch", "mkdir"):
            for f in ops:
                touch(f, root)
        elif prog == "systemctl" and args:
            verb_idx = next((i for i, a in enumerate(args) if not a.startswith("-")), None)
            if verb_idx is not None:
                verb = args[verb_idx]
                units = [a for a in args[verb_idx + 1:] if not a.startswith("-")]
                if verb in SYSTEMCTL_INVERSE and units:
                    plan.inverse.append("%ssystemctl %s %s" % (sudo_prefix, SYSTEMCTL_INVERSE[verb],
                                                                " ".join(shlex.quote(u) for u in units)))
                elif verb in ("restart", "reload", "daemon-reload"):
                    plan.notes.append("Undo: a %s has nothing to reverse." % verb)
        elif prog not in ("echo", "printf", "cat", "true"):
            # Best effort: back up any existing file named on the command line.
            for f in ops:
                if f.startswith("/") and not f.startswith(("/dev/", "/proc/", "/sys/", "/run/")):
                    p = resolve(f, root)
                    if p and exists(p) and not isdir(p) and p not in plan.files:
                        plan.files.append(p)
    return plan


# --- Journal and backups -------------------------------------------------------

class UndoJournal(object):
    """Keeps backups for one Willy session. `ui` provides approve(title, cmds) -> bool,
    run(cmd) -> (code, out) and say(text)."""

    def __init__(self, base_dir, ui, session_id=None):
        self.ui = ui
        self.session_id = session_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = self._pick_dir(base_dir)
        self.entries = []

    def _pick_dir(self, base_dir):
        for base in (base_dir, os.path.join(os.path.expanduser("~"), ".cache", "willy-backups"), "/tmp"):
            if not base:
                continue
            path = os.path.join(base, self.session_id)
            try:
                os.makedirs(path, exist_ok=True)
                probe = os.path.join(path, ".write-test")
                with open(probe, "w") as fh:
                    fh.write("ok")
                os.remove(probe)
                return path
            except OSError:
                continue
        return None

    @property
    def journal_path(self):
        return os.path.join(self.dir, "journal.json") if self.dir else None

    def _save(self):
        if not self.dir:
            return
        with open(self.journal_path, "w", encoding="utf-8") as fh:
            json.dump(self.entries, fh, indent=2)

    def _size(self, path):
        if not os.path.isdir(path):
            try:
                return os.path.getsize(path)
            except OSError:
                return 0
        total = 0
        for dirpath, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
            if total > MAX_BACKUP_BYTES:
                break
        return total

    def prepare(self, cmd, plan):
        """Back up before running. Returns (entry, problem). entry is None when there is
        nothing to undo; problem is a message when the backup failed."""
        if not plan.undoable:
            return None, None
        if not self.dir:
            return None, "there is nowhere writable to keep backups"
        files = list(plan.files)
        skipped = [f for f in files if self._size(f) > MAX_BACKUP_BYTES]
        files = [f for f in files if f not in skipped]
        entry = {"id": len(self.entries) + 1, "time": dt.datetime.now().isoformat(timespec="seconds"),
                 "command": cmd, "files": files, "created": list(plan.created),
                 "inverse": list(plan.inverse), "skipped": skipped, "archive": None,
                 "needs_root": False, "undone": False, "ran": False}
        if files:
            archive = os.path.join(self.dir, "%03d.tar" % entry["id"])
            needs_root = any(not os.access(f, os.R_OK) or
                             (os.path.isdir(f) and not os.access(f, os.X_OK)) or
                             _owner(f) != os.getuid() for f in files)
            rels = [f.lstrip("/") for f in files]
            argv = (["sudo"] if needs_root else []) + ["tar", "-C", "/", "-cpf", archive, "--"] + rels
            proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode not in (0, 1):
                return None, proc.stdout.decode("utf-8", "replace").strip() or "tar failed"
            entry["archive"] = archive
            entry["needs_root"] = needs_root
        if skipped:
            self.ui.say("  Note: %s too big to back up (over 200 MB)." % _list(skipped))
        self.entries.append(entry)
        self._save()
        return entry, None

    def mark_ran(self, entry, exit_code):
        if entry:
            entry["ran"] = True
            entry["exit_code"] = exit_code
            self._save()

    def pending(self):
        return [e for e in self.entries if e["ran"] and not e["undone"]]

    def list_text(self):
        items = self.pending()
        if not items:
            return "Nothing to undo in this session."
        lines = ["Changes you can undo (newest last):"]
        for e in items:
            what = _list(e["files"] + e["created"]) if (e["files"] or e["created"]) else "service changes"
            lines.append("  %d) %s  $ %s\n     restores: %s" % (e["id"], e["time"][11:], e["command"], what))
        lines.append("Type /undo to reverse the newest one.")
        return "\n".join(lines)

    def undo_last(self):
        items = self.pending()
        if not items:
            self.ui.say("Nothing to undo in this session.")
            return None
        e = items[-1]
        cmds = []
        if e["archive"]:
            cmds.append("%star -C / -xpf %s" % ("sudo " if e["needs_root"] else "",
                                                 shlex.quote(e["archive"])))
        for path in reversed(e["created"]):
            if os.path.lexists(path) and path not in e["files"]:
                rm = "rmdir" if os.path.isdir(path) and not os.path.islink(path) else "rm -f --"
                cmds.append("%s%s %s" % ("sudo " if _owner(path) != os.getuid() else "", rm, shlex.quote(path)))
        cmds.extend(e["inverse"])
        if not cmds:
            self.ui.say("That change left nothing to restore.")
            e["undone"] = True
            self._save()
            return None
        self.ui.say("Undo will reverse:  $ %s" % e["command"])
        if not self.ui.approve("Undo the last change", cmds):
            return None
        failed = []
        for c in cmds:
            code, out = self.ui.run(c)
            if code != 0:
                failed.append("%s -> %s" % (c, out.strip()))
        e["undone"] = True
        self._save()
        if failed:
            self.ui.say("Undo finished with problems:\n  " + "\n  ".join(failed))
            return "I typed /undo for `%s`, but some steps failed: %s" % (e["command"], "; ".join(failed))
        self.ui.say("Undone. Restored the state from before:  $ %s" % e["command"])
        return "I typed /undo: the change made by `%s` was reversed and the files were restored." % e["command"]


def _owner(path):
    try:
        return os.lstat(path).st_uid
    except OSError:
        return -1
