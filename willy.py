#!/usr/bin/env python3
"""Willy: an offline Linux troubleshooting assistant that runs from a USB stick.

It talks to Willy's local AI engine (OpenAI-compatible API on 127.0.0.1),
collects a snapshot of the system, and lets the model ask to run diagnostic
commands. Every command needs your approval before it runs.

Standard library only, so it works on almost any Linux with Python 3.6+.

Created by Wilson Sumanang.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import willy_knowledge  # noqa: E402
import willy_rescue  # noqa: E402
import willy_undo  # noqa: E402

GUIDES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if COLOR else text


SYSTEM_PROMPT = """You are Willy, an expert Linux troubleshooting assistant created by \
Wilson Sumanang. You run offline from a USB stick on the user's machine and can ask to run \
shell commands on it.

About yourself:
- Your name is Willy and you were created by Wilson Sumanang.
- When someone asks who Wilson Sumanang is, or about your creator, answer warmly in 2-4 sentences
  using this public profile (don't add anything beyond it):
  Wilson Sumanang is based in Jakarta, Indonesia. He is the Co-Founder and CTO of PARKEE
  (PT. Inovasi Anak Indonesia), whose automated, cashless parking systems run at about 700
  locations across Indonesia, including airports, seaports, malls, hospitals and office towers,
  processing around 20 million transactions a month. He founded Mobius Labs, an AI and software
  company, in 2018. Before that he was VP of Engineering at Moka (acquired by Gojek in 2020) and
  a software engineer in the United States. He studied Computer Science at Purdue University.
  His motto: "Most people build apps. I build the system and technologies underneath."
- Never name the AI model, model family, company or software you are based on or run on,
  and never describe how you were built or trained. If asked, reply: "I'm Willy, an offline
  Linux troubleshooting assistant created by Wilson Sumanang. I can't share details about
  how I'm built, but I'm happy to help with your PC." Then steer back to the problem.
- Do not deny or invent details either; simply decline to share them.

To run a command, put exactly ONE command in a fenced block tagged `run`, like this:
```run
journalctl -b -p err --no-pager | tail -n 50
```
The user approves it, and you get the output in the next message.

Rules:
- One command per reply. Say in one line why you want it. Then stop and wait for the output.
- Start with read-only diagnostics. Narrow down the cause before proposing fixes.
- Never use interactive programs (editors, less, top without -b, anything that waits for input).
  Use --no-pager, `top -b -n 1`, `| tail`, `| head`, etc. Keep output short.
- Before anything that changes the system (installing or removing packages, editing config,
  restarting services, partitioning, bootloader work), explain the risk and suggest a backup.
- NEVER delete, overwrite, wipe or uninstall anything without first saying exactly what will
  be removed and whether it can be undone. The user must approve every such command.
- Prefer reversible fixes: move files to a backup folder instead of deleting them, disable a
  service instead of removing it, and copy a config file (cp file file.bak) before editing it.
- Keep destructive commands on their own. Never chain them with other commands, and never
  hide what a command does (no eval, base64, or piping downloads into a shell).
- Some commands are blocked by guardrails. If one is blocked, do not try to get around it;
  suggest a safer approach instead.
- Use sudo only when root is really needed.

Rescue mode and undo:
- If the snapshot says this is a live session (the rescue USB) and the user's installed Linux
  won't boot or crashes, tell them to type /rescue. Willy then finds the installed system and
  opens it read-only at /mnt/willy-target, and you receive its logs and settings.
- While it is open, its files are under /mnt/willy-target (for example
  /mnt/willy-target/etc/fstab) and its logs can be read with
  `sudo journalctl -D /mnt/willy-target/var/log/journal -b -p err --no-pager`.
- To repair it (GRUB, initramfs, packages, fstab), the user must first type /rescue repair.
  Then run tools inside it as `sudo chroot /mnt/willy-target <command>`.
- Willy backs up files before approved changes. The user can type /undo to reverse the last
  file or service change, so mention /undo when a fix doesn't help. /undo can NOT reverse
  package installs or removals, disk/partition changes or bootloader installs, so warn
  before those.
- Messages may end with [Willy fix guides]: proven checks and fixes for that kind of problem.
  Prefer their steps over guessing, adapt names, paths and devices to this PC, and say so if a
  guide doesn't fit what you see.
- /undo, /rescue, /report and the other slash commands are typed by the user in the chat.
  They are not shell commands: never put them in a ```run block.
- When you know the cause, give a short diagnosis and numbered fix steps.
- Be concise. Do not invent output you have not seen.
"""

BASELINE = [
    ("Identity", "echo \"user=$(id -un) uid=$(id -u) host=$(hostname)\"; "
                 "command -v sudo >/dev/null && echo 'sudo available'"),
    ("OS", "grep -E '^(PRETTY_NAME|ID|VERSION_ID)=' /etc/os-release 2>/dev/null; uname -srm"),
    ("Uptime and load", "uptime"),
    ("Memory", "free -h"),
    ("Disk usage", "df -hT -x tmpfs -x devtmpfs -x squashfs -x overlay 2>/dev/null"),
    ("Block devices", "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,MODEL 2>/dev/null | head -n 25"),
    ("Failed services", "systemctl --failed --no-legend --no-pager 2>/dev/null || echo 'systemd not available'"),
    ("Errors this boot", "journalctl -b -p err --no-pager -n 25 -q 2>/dev/null"),
    ("Kernel errors/warnings", "dmesg --level=err,warn 2>/dev/null | tail -n 15"),
    ("Network", "ip -br addr 2>/dev/null; ip route 2>/dev/null | head -n 5; "
                "grep -E '^nameserver' /etc/resolv.conf 2>/dev/null"),
    # NetworkManager's own connectivity state first (no extra traffic); one quick ping otherwise.
    ("Internet", "s=$(nmcli -t networking connectivity 2>/dev/null); if [ -n \"$s\" ]; then echo \"$s\"; "
                 "elif ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then echo full; else echo none; fi"),
    ("Top CPU processes", "ps -eo pid,comm,%cpu,%mem --sort=-%cpu 2>/dev/null | head -n 8"),
]

# --- Guardrails ---------------------------------------------------------------
# Every command, whether Willy proposes it or you type it with /run, is put in
# one of four levels before anything runs:
#   blocked  never runs, even if approved (catastrophic, never needed here)
#   delete   deletes or overwrites data: you must type the word "delete"
#   change   changes the system: you must type the word "yes"
#   safe     read-only: "y" is enough
# The checks deliberately err on the side of asking. A false alarm costs one
# extra word; a missed one could cost your data.

_SYS_DIRS = r"/(?:bin|boot|dev|etc|home|lib|lib32|lib64|opt|proc|root|sbin|srv|sys|usr|var)?/?\*?"
_END = r"(?=$|[\s;&|)])"
_ARGS = r"(?:\S+\s+)*?"

BLOCKED_RULES = [
    (r"--no-preserve-root", "deletes the whole root filesystem"),
    (r"\brm\s+" + _ARGS + r"-[a-zA-Z]*[rR][a-zA-Z]*\s+" + _ARGS
     + r"(?:" + _SYS_DIRS + r"|~/?\*?|\$HOME/?\*?)" + _END,
     "recursively deletes an entire system or home folder"),
    (r"\b(?:chmod|chown|chgrp)\s+" + _ARGS + r"-[a-zA-Z]*R[a-zA-Z]*\s+" + _ARGS + r"/" + _END,
     "changes ownership or permissions of the entire filesystem"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb (freezes the PC)"),
    (r">\s*/dev/(?:sd[a-z]|hd[a-z]|vd[a-z]|nvme\d+n\d+|mmcblk\d+)\b", "overwrites a whole disk"),
]

DELETE_RULES = [
    (r"\b(?:rm|rmdir|unlink|shred)\b", "deletes files or folders"),
    (r"\bfind\b.*(?:-delete\b|-exec\s+(?:sudo\s+)?rm\b)", "deletes the files it finds"),
    (r"\b(?:wipefs|mkfs(?:\.\w+)?|mkswap|fdisk|sfdisk|gdisk|sgdisk|cfdisk|parted)\b",
     "can erase disks or partitions"),
    (r"\bdd\b", "writes raw data and can overwrite disks"),
    (r"\btruncate\b", "empties files"),
    (r"\b(?:apt|apt-get|aptitude|dnf|yum|zypper)\s+" + _ARGS + r"(?:remove|purge|autoremove|erase)\b",
     "removes packages"),
    (r"\bpacman\s+-R|\brpm\s+-e\b|\bdpkg\s+(?:-r|-P|--remove|--purge)\b|\bsnap\s+remove\b"
     r"|\bflatpak\s+(?:uninstall|remove)\b|\bpip3?\s+uninstall\b", "removes software"),
    (r"\bdocker\s+(?:rm|rmi|(?:system|image|container|volume|network)\s+(?:prune|rm))\b",
     "deletes Docker data"),
    (r"\bgit\s+(?:clean|reset\s+--hard|checkout\s+--\s)", "discards files or changes"),
    (r"\bcrontab\s+-r\b", "deletes all scheduled jobs"),
    (r"\bjournalctl\s+" + _ARGS + r"--(?:vacuum-\w+|rotate)\b", "deletes system logs"),
    (r"\b(?:userdel|groupdel)\b", "deletes a user account or group"),
    (r"(?<![0-9&>])>(?![>&])\s*(?!/dev/null\b)[^\s|;&]", "overwrites a file (>)"),
    (r"\btee\s+(?!-a\b)(?!--append\b)\S", "overwrites a file (tee)"),
]

CHANGE_RULES = [
    (r"(?:^|[\s;&|(])(?:sudo|doas|pkexec)\b|\bsu\s", "runs as root"),
    (r"\b(?:mv|cp|ln|install|rsync|mkdir|touch)\b", "creates, moves or replaces files"),
    (r"\b(?:chmod|chown|chgrp|chattr|setfacl)\b", "changes permissions"),
    (r"\b(?:kill|pkill|killall|xkill)\b", "stops programs"),
    (r"\b(?:reboot|shutdown|poweroff|halt)\b|\bsystemctl\s+(?:reboot|poweroff|suspend|hibernate)\b",
     "restarts or powers off the PC"),
    (r"\bsystemctl\s+" + _ARGS + r"(?:start|stop|restart|reload|enable|disable|mask|unmask|isolate"
     r"|kill|daemon-reload|edit|set-default)\b", "changes services"),
    (r"\b(?:apt|apt-get|aptitude|dnf|yum|zypper)\s+" + _ARGS
     + r"(?:install|upgrade|dist-upgrade|full-upgrade|reinstall|update)\b|\bpacman\s+-S"
     r"|\bsnap\s+(?:install|refresh)\b|\bflatpak\s+(?:install|update)\b|\bpip3?\s+install\b"
     r"|\bdpkg\s+(?:-i|--install|--configure)\b", "installs or updates software"),
    (r"\b(?:grub-install|update-grub|grub2?-mkconfig|mkinitcpio|dracut|update-initramfs"
     r"|efibootmgr|bootctl)\b", "changes how the PC boots"),
    (r"\b(?:passwd|chpasswd|useradd|usermod|groupadd|gpasswd|visudo)\b",
     "changes user accounts or passwords"),
    (r"\bsed\s+" + _ARGS + r"(?:-[a-zA-Z]*i|--in-place)", "edits files in place"),
    (r">>", "appends to a file"),
    (r"\b(?:mount|umount|swapon|swapoff|fsck(?:\.\w+)?|e2fsck|xfs_repair|ntfsfix|resize2fs|tune2fs)\b"
     r"|\bbtrfs\s+check\s+--repair\b", "changes disks or filesystems"),
    (r"\b(?:modprobe|rmmod|insmod)\b|\bsysctl\s+(?:-w|--write)\b", "changes the running kernel"),
    (r"\b(?:iptables|ip6tables|nft|ufw|firewall-cmd)\b", "changes the firewall"),
    (r"\bnmcli\s+" + _ARGS + r"(?:up|down|modify|delete|add|connect|disconnect|on|off)\b"
     r"|\bip\s+" + _ARGS + r"(?:add|del|set|flush)\b|\brfkill\s+(?:block|unblock)\b",
     "changes network settings"),
    (r"\b(?:hostnamectl|timedatectl|localectl)\s+set-|\bcrontab\b|\bupdate-alternatives\b",
     "changes system settings"),
    (r"\b(?:curl|wget|scp|ftp|nc|ncat)\b", "uses the network or downloads files"),
    (r"\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b|\beval\b|\bbase64\s+(?:-d|--decode)\b|\b(?:ba|z|da)?sh\s+-c\b"
     r"|\bpython[0-9.]*\s+-c\b|\bperl\s+-e\b|\bsource\b|(?:^|[;&|]\s*)\.\s",
     "runs code this check cannot see inside"),
]

LEVELS = ("safe", "change", "delete", "blocked")


def classify(cmd):
    """Return (level, reasons) for a shell command. The highest level found wins."""
    level, reasons = "safe", []
    for name, rules in (("change", CHANGE_RULES), ("delete", DELETE_RULES), ("blocked", BLOCKED_RULES)):
        hits = [why for pattern, why in rules if re.search(pattern, cmd)]
        if hits:
            reasons = hits + [r for r in reasons if r not in hits]
            level = name
    return level, reasons


def truncate(text, limit):
    if len(text) <= limit:
        return text
    half = limit // 2
    return "%s\n... [%d characters cut] ...\n%s" % (text[:half], len(text) - limit, text[-half:])


def run_shell(cmd, timeout):
    shell = shutil.which("bash") or "/bin/sh"
    env = dict(os.environ, PAGER="cat", SYSTEMD_PAGER="", GIT_PAGER="cat")
    try:
        proc = subprocess.run([shell, "-c", cmd], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, env=env)
        return proc.returncode, proc.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        partial = (exc.output or b"").decode("utf-8", "replace")
        return None, partial + "\n[timed out after %ss]" % timeout


INTERNET_NOTES = {
    "full": "Online: fixes that download packages or firmware will work.",
    "limited": "OFFLINE (connected to a network, but it has no internet).",
    "portal": "OFFLINE until someone logs in to this network's web page (captive portal).",
    "none": "OFFLINE: no internet connection.",
}
OFFLINE_ADVICE = (" Prefer fixes that work without internet. If a fix needs a download (packages, drivers, "
                  "firmware), say so clearly and suggest getting online first with an Ethernet cable or "
                  "phone USB tethering, or an offline alternative such as booting the previous kernel.")


def internet_state(snapshot):
    m = re.search(r"### Internet\n(\w+)", snapshot)
    return m.group(1).lower() if m else "unknown"


def gather_snapshot(per_section):
    parts = []
    for label, cmd in BASELINE:
        _, out = run_shell(cmd, 15)
        out = out.strip() or "(no output)"
        if label == "Internet":
            state = out.split()[0].lower() if out.split() else "unknown"
            note = INTERNET_NOTES.get(state, "Unknown whether this PC is online.")
            out = "%s\n%s%s" % (state, note, "" if state == "full" else OFFLINE_ADVICE)
        parts.append("### %s\n%s" % (label, truncate(out, per_section)))
    return "\n\n".join(parts)


THINK_RE = re.compile(r"<think>.*?</think>", re.S)
RUN_RE = re.compile(r"```run[ \t]*\n(.*?)```", re.S)


def extract_command(text):
    m = RUN_RE.search(text)
    if not m:
        return None
    cmd = m.group(1).strip()
    return cmd or None


# Willy's underlying model and build stay private. The system prompt asks the
# model not to reveal them; this filter is the safety net for the times a small
# model repeats its training ("I am ..., created by ...").
_IDENTITY_SUBS = [
    (re.compile(r"(?i)\bmistral(?:\.ai|\s+ai)\b|\bmistralai\b"), "Wilson Sumanang"),
    (re.compile(r"(?i)\b(?:mini|mi)stral[\w.\-]*"), "Willy"),
    (re.compile(r"(?i)\ble\s+chat\b"), "Willy"),
    (re.compile(r"(?i)\bqwen[\w.\-]*"), "Willy"),
    (re.compile(r"(?i)\btongyi(?:\s+qianwen)?\b|通义千问|千问"), "Willy"),
    (re.compile(r"(?i)\balibaba(?:\s+(?:cloud|group))?\b|阿里云|阿里巴巴"), "Wilson Sumanang"),
]
_HOLD_BACK = 24


def scrub_identity(text):
    for pattern, repl in _IDENTITY_SUBS:
        text = pattern.sub(repl, text)
    return text


def ask_model(api, messages, max_tokens, temperature):
    body = json.dumps({
        "model": "local",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        # Reuse the engine's memory of the conversation so far; without this every
        # reply re-reads the whole conversation (over a minute on a laptop CPU).
        "cache_prompt": True,
        # Brains that can "think" first should answer directly instead.
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")
    req = urllib.request.Request(api, data=body, headers={"Content-Type": "application/json"})
    parts = []
    shown = 0  # characters of the scrubbed reply already printed
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                piece = (choices[0].get("delta") or {}).get("content") or ""
                if piece:
                    parts.append(piece)
                    # Hold back the last few characters so a name split across
                    # chunks is scrubbed before it is printed.
                    clean = scrub_identity("".join(parts))
                    upto = max(shown, len(clean) - _HOLD_BACK)
                    if upto > shown:
                        sys.stdout.write(clean[shown:upto])
                        sys.stdout.flush()
                        shown = upto
    finally:
        clean = scrub_identity("".join(parts))
        sys.stdout.write(clean[shown:])
        print()
    return clean


def trim_history(messages, budget):
    # messages[0] is the system prompt + snapshot; the rest alternate user/assistant.
    # Drop the oldest user/assistant pair until the conversation fits.
    def size():
        return sum(len(m["content"]) for m in messages)
    while size() > budget and len(messages) > 3:
        del messages[1:3]


def edit_line(prompt, initial):
    try:
        import readline
        readline.set_startup_hook(lambda: readline.insert_text(initial))
        try:
            return input(prompt)
        finally:
            readline.set_startup_hook()
    except ImportError:
        print("Current: %s" % initial)
        return input(prompt)


APPROVAL_WORD = {"safe": "y", "change": "yes", "delete": "delete"}


def read_line(prompt):
    # Strip whitespace and a stray byte-order mark (some terminals and pipes add one).
    return input(prompt).replace("﻿", "").strip()


def undo_notes(cmd):
    """Plain-English lines saying whether /undo will be able to reverse `cmd`."""
    try:
        return willy_undo.plan_command(cmd, os.getcwd()).describe()
    except Exception:  # planning is best effort and must never block approval
        return ["Undo: Willy couldn't work out what this changes, so it may not be undoable."]


def confirm(cmd, who="Willy"):
    """Ask before running a command.

    Returns (decision, cmd, level, reasons); decision is 'run', 'skip',
    'blocked' or 'quit'. Edited commands are checked again from scratch.
    """
    while True:
        level, reasons = classify(cmd)
        print()
        print(c("  You asked to run:" if who == "You" else "  %s wants to run:" % who, "1;33"))
        for line in cmd.splitlines():
            print(c("    $ " + line, "1"))

        if level == "blocked":
            print(c("  BLOCKED by Willy's guardrails: " + "; ".join(reasons) + ".", "1;41"))
            print("  This command will not run, even with approval. If you truly need it,")
            print("  type it yourself in a separate terminal after making a backup.")
            return "blocked", cmd, level, reasons
        if level == "delete":
            print(c("  DELETES OR OVERWRITES DATA: " + "; ".join(reasons) + ".", "1;31"))
            print(c("  This may not be undoable. Make sure you have a backup first.", "31"))
        elif level == "change":
            print(c("  CHANGES YOUR SYSTEM: " + "; ".join(reasons) + ".", "1;33"))
        if level in ("change", "delete"):
            for line in undo_notes(cmd):
                print(c("  " + line, "36"))

        word = APPROVAL_WORD[level]
        if level == "safe":
            prompt = "  Run it? [y] yes, [n] skip, [e] edit, [q] quit: "
        else:
            prompt = "  Type '%s' to run, [n] skip, [e] edit, [q] quit: " % word
        try:
            ans = read_line(prompt).lower()
        except KeyboardInterrupt:
            print()
            return "skip", cmd, level, reasons
        except EOFError:
            # Input closed (Ctrl+D or end of a script): end the session, never loop.
            print()
            return "quit", cmd, level, reasons
        if ans in ("q", "quit", "/q", "/quit", "exit", "/exit"):
            return "quit", cmd, level, reasons

        if ans == word or (level == "safe" and ans == "yes"):
            return "run", cmd, level, reasons
        if ans in ("y", "yes", "delete"):
            print(c("  To approve this one, type the word '%s'." % word, "33"))
            continue
        if ans in ("", "n", "no"):
            return "skip", cmd, level, reasons
        if ans == "e":
            try:
                new = edit_line("  edit> ", cmd).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if new:
                cmd = new
            continue
        print(c("  Not understood. Nothing was run.", "33"))


LEVEL_RANK = {"safe": 0, "change": 1, "delete": 2, "blocked": 3}


def approve_batch(title, cmds):
    """Show a group of commands Willy needs for one job and ask once.

    The approval word is set by the most dangerous command in the group, and a
    group containing a blocked command can never run."""
    worst, reasons = "safe", []
    for cmd in cmds:
        level, why = classify(cmd)
        if LEVEL_RANK[level] > LEVEL_RANK[worst]:
            worst = level
        reasons += [r for r in why if r not in reasons]
    print()
    print(c("  Willy needs to: %s" % title, "1;33"))
    for cmd in cmds:
        print(c("    $ " + cmd, "1"))
    if worst == "blocked":
        print(c("  BLOCKED by Willy's guardrails: " + "; ".join(reasons) + ".", "1;41"))
        return False
    if worst != "safe":
        color = "1;31" if worst == "delete" else "1;33"
        label = "DELETES OR OVERWRITES DATA" if worst == "delete" else "CHANGES YOUR SYSTEM"
        print(c("  %s: %s." % (label, "; ".join(reasons)), color))
    word = APPROVAL_WORD[worst]
    while True:
        try:
            ans = read_line("  Type '%s' to go ahead, Enter to cancel: " % word).lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if ans == word or (worst == "safe" and ans == "yes"):
            return True
        if ans in ("", "n", "no", "q"):
            print("  Cancelled. Nothing was run.")
            return False
        print(c("  To approve, type the word '%s'." % word, "33"))


class HelperUI(object):
    """What the rescue and undo helpers use to talk to the user and run commands."""

    def __init__(self, timeout, log, events):
        self.timeout, self.log, self.events = timeout, log, events

    def approve(self, title, cmds):
        ok = approve_batch(title, cmds)
        self.log.write("approval", "%s (%s):\n%s" % ("approved" if ok else "declined", title, "\n".join(cmds)))
        return ok

    def run(self, cmd):
        code, out = run_shell(cmd, max(self.timeout, 120))
        self.events.append({"who": "Willy (helper)", "cmd": cmd, "level": classify(cmd)[0], "exit": code})
        return code, out

    def run_interactive(self, cmd):
        # For steps where the user types something themselves (like a disk passphrase).
        code = subprocess.call([shutil.which("bash") or "/bin/sh", "-c", cmd])
        self.events.append({"who": "Willy (helper)", "cmd": cmd, "level": classify(cmd)[0], "exit": code})
        return code

    def say(self, text):
        print(c(text, "36"))

    def ask(self, prompt):
        try:
            return read_line(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return ""


def execute(cmd, args, undo, events, who):
    """Run an approved command, backing up what it changes first.

    Returns (code, output, note_for_model) or None if the user cancelled."""
    level = classify(cmd)[0]
    entry = None
    if level in ("change", "delete"):
        try:
            plan = willy_undo.plan_command(cmd, os.getcwd())
            entry, problem = undo.prepare(cmd, plan)
        except Exception as exc:  # never let backup planning crash a session
            entry, problem = None, str(exc)
        if problem:
            print(c("  Willy couldn't make a backup first: %s" % problem, "1;31"))
            try:
                ans = read_line("  Run it anyway, without /undo? Type 'yes' to run, Enter to cancel: ").lower()
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans != "yes":
                return None
        elif entry and entry.get("archive"):
            print(c("  Backup saved. Type /undo afterwards to reverse this.", "36"))
    print(c("  running...", "2"))
    code, out = run_shell(cmd, args.timeout)
    undo.mark_ran(entry, code)
    events.append({"who": who, "cmd": cmd, "level": level, "exit": code})
    note = " (Willy saved a backup first, so this can be reversed with /undo.)" if entry else ""
    return code, out, note


REPORT_PROMPT = (
    "Write a short troubleshooting report for this session in Markdown with these sections: "
    "## Problem, ## What was checked, ## Cause, ## What was changed, ## What is left to do. "
    "Use plain language a non-expert understands. If something is unknown, say so. "
    "Do not include any ```run blocks and do not ask to run commands.")


def write_report(args, messages, events, snapshot_os):
    msgs = [m for m in messages] + [{"role": "user", "content": REPORT_PROMPT}]
    print(c("\nwilly (writing report)> ", "1;32"), end="", flush=True)
    try:
        body = ask_model(args.api, msgs, 900, 0.2)
    except (urllib.error.URLError, OSError, KeyboardInterrupt) as exc:
        print(c("Could not write the report: %s" % exc, "1;31"))
        return None
    body = RUN_RE.sub("", THINK_RE.sub("", body)).strip()
    now = dt.datetime.now()
    lines = ["# Willy troubleshooting report", "",
             "- **Date:** %s" % now.strftime("%Y-%m-%d %H:%M"),
             "- **Computer:** %s" % socket.gethostname(),
             "- **System:** %s" % snapshot_os, "", body, "", "## Commands run", ""]
    if events:
        lines += ["| # | Who | Level | Exit | Command |", "|---|-----|-------|------|---------|"]
        for i, e in enumerate(events, 1):
            lines.append("| %d | %s | %s | %s | `%s` |" % (i, e["who"], e["level"], e["exit"],
                                                       e["cmd"].replace("|", "\\|").replace("`", "'")))
    else:
        lines.append("No commands were run.")
    lines += ["", "---", "Report made by Willy, created by Wilson Sumanang."]
    text = "\n".join(lines) + "\n"
    for directory in (args.report_dir, os.path.join(os.path.expanduser("~"), "willy-reports")):
        if not directory:
            continue
        try:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "willy-report-%s-%s.md" % (socket.gethostname(),
                                                                     now.strftime("%Y%m%d-%H%M%S")))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return path
        except OSError:
            continue
    return None


def guides_list(guides):
    if not len(guides):
        return "No fix guides found (the willy/knowledge folder is missing)."
    items = sorted(guides.guides, key=lambda g: g.title.lower())
    lines = ["Willy's offline fix guides (%d). Read one with /guide <number or words>:" % len(items)]
    for i, g in enumerate(items, 1):
        lines.append("  %2d. %s" % (i, g.title))
    return "\n".join(lines)


def guide_text(guides, query):
    items = sorted(guides.guides, key=lambda g: g.title.lower())
    pick = None
    if query.isdigit() and 1 <= int(query) <= len(items):
        pick = items[int(query) - 1]
    else:
        pick = next((g for g in items if g.id == query), None)
        if pick is None:
            hits = guides.search(query, k=1, min_score=0.5)
            pick = hits[0][1] if hits else None
    if pick is None:
        return "No guide matches %r. Type /guides to see them all." % query
    rule = "-" * min(78, len(pick.title) + 4)
    return "\n%s\n  %s\n%s\n%s\n" % (rule, pick.title, rule, pick.body)


class Log(object):
    def __init__(self, directory):
        self.fh = None
        if not directory:
            return
        try:
            os.makedirs(directory, exist_ok=True)
            name = "willy-%s-%s.md" % (socket.gethostname(), dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
            self.path = os.path.join(directory, name)
            self.fh = open(self.path, "a", encoding="utf-8")
        except OSError as exc:
            print(c("Note: cannot write logs to %s (%s)" % (directory, exc), "33"))

    def write(self, role, text):
        if self.fh:
            self.fh.write("\n## %s (%s)\n\n%s\n" % (role, dt.datetime.now().strftime("%H:%M:%S"), text))
            self.fh.flush()


HELP = """
Chat commands
  ?  or /help      show this help
  /run <cmd>       run a command yourself and share the output with Willy
  /snapshot        show the system overview Willy collected at startup
  /reset           start a fresh conversation
  /undo            reverse the last change Willy made (/undo list shows them all)
  /report          save a summary of this session (problem, cause, what was fixed)
  /guides          list Willy's offline fix guides; /guide <number or words> reads one
  /quit            exit Willy
  Ctrl+C           stop Willy's current reply

Rescue mode (when the PC's own Linux won't start)
  /rescue          find the PC's installed Linux and open it read-only
  /rescue repair   open it read-write so repairs (GRUB, packages, fstab) can run
  /rescue off      close it safely before restarting the PC
  /rescue status   show what is open

Approving commands Willy wants to run
  y                safe, read-only checks
  yes              commands that change the system
  delete           commands that delete or overwrite data
  Enter            skip (nothing runs)
  e                edit the command first
  q                quit

Things you can ask (just type in plain words)
  my wifi stopped working after an update
  the disk is full, what is using the space?
  the PC is slow, what is eating CPU or memory?
  why did this boot take so long?
  a service failed to start, how do I fix it?
  is my disk healthy?
  I can't install updates, apt/dnf shows errors
  no sound / the screen resolution is wrong

Handy checks you can run yourself with /run
  /run df -h                                    disk space
  /run free -h                                  memory
  /run systemctl --failed --no-pager            failed services
  /run journalctl -b -p err --no-pager | tail -n 30    errors this boot
  /run ip -br addr                              network addresses
  /run ping -c 3 1.1.1.1                        internet reachable?
  /run lsblk -f                                 disks and partitions
  /run du -xh / 2>/dev/null | sort -h | tail -n 15     biggest folders
  /run ps aux --sort=-%cpu | head               busiest programs
  /run systemd-analyze blame | head -n 15       slow boot services
"""


def server_ok(api):
    base = api.split("/v1/")[0]
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main():
    ap = argparse.ArgumentParser(description="Offline Linux troubleshooting assistant.")
    ap.add_argument("problem", nargs="*", help="optional first description of the problem")
    ap.add_argument("--api", default=os.environ.get("WILLY_API", "http://127.0.0.1:8080/v1/chat/completions"))
    ap.add_argument("--log-dir", default=os.environ.get("WILLY_LOG_DIR", ""))
    ap.add_argument("--timeout", type=int, default=60, help="seconds before a command is stopped")
    ap.add_argument("--max-output", type=int, default=3500, help="characters of command output sent to the model")
    ap.add_argument("--history-chars", type=int, default=22000, help="conversation size budget (fit to context)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--max-steps", type=int, default=10, help="commands in a row before handing back to you")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--backup-dir", default=os.environ.get("WILLY_BACKUP_DIR", ""),
                    help="where /undo backups are kept")
    ap.add_argument("--report-dir", default=os.environ.get("WILLY_REPORT_DIR", ""),
                    help="where /report saves reports")
    ap.add_argument("--knowledge-dir", default=os.environ.get("WILLY_KNOWLEDGE_DIR", GUIDES_DIR),
                    help="folder of fix guides (set empty to turn guides off)")
    args = ap.parse_args()

    if not server_ok(args.api):
        print(c("Cannot reach Willy's engine at %s. Start Willy with start.sh." % args.api, "1;31"))
        return 1

    log = Log(args.log_dir)
    events = []
    ui = HelperUI(args.timeout, log, events)
    undo = willy_undo.UndoJournal(args.backup_dir, ui)
    rescue = willy_rescue.Rescue(ui)
    live = willy_rescue.is_live_session()
    guides = willy_knowledge.Knowledge(args.knowledge_dir)
    guides_seen = set()

    def with_guides(text, from_output=False):
        """Attach matching fix guides to a message (command output needs a stronger match)."""
        if not len(guides):
            return text
        extra, titles = (guides.augment(text, guides_seen, k=1, min_score=8.0) if from_output
                         else guides.augment(text, guides_seen))
        for title in titles:
            print(c("  (Willy is using its guide: %s)" % title, "2"))
        if titles:
            log.write("guides", ", ".join(titles))
        return text + extra

    print(c("Willy: offline Linux troubleshooter", "1;32") + c("  (created by Wilson Sumanang)", "2"))
    print("Nothing runs without your approval. Type ? to see commands and examples.")
    print("Collecting system snapshot...", end="", flush=True)
    snapshot = gather_snapshot(1200)
    if live:
        snapshot = ("### Session type\nLive session started from the rescue USB. The PC's own "
                    "installed Linux is NOT running; use /rescue to open it.\n\n" + snapshot)
    print(" done.")
    log.write("snapshot", snapshot)
    m = re.search(r'PRETTY_NAME="?([^"\n]+)', snapshot)
    snapshot_os = m.group(1) if m else "Linux"
    if internet_state(snapshot) == "full":
        print(c("Internet: connected. Fixes that need downloads can use it.", "2"))
    else:
        print(c("No internet: that's fine, Willy works fully offline. If a fix needs a download, "
                "Willy will say so.", "2"))
    if live:
        print(c("\nYou started this PC from the rescue USB. If the PC's own Linux won't start,", "1;36"))
        print(c("type /rescue and Willy will find it and read why it failed.", "1;36"))

    system = {"role": "system", "content": SYSTEM_PROMPT + "\n\nSystem snapshot:\n\n" + snapshot}
    messages = [system]
    pending = " ".join(args.problem).strip() or None

    while True:
        if pending is None:
            try:
                user = read_line(c("\nyou (? for help)> ", "1;36"))
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user in ("/q", "/quit", "/exit"):
                break
            if user in ("?", "/help", "/?", "help"):
                print(HELP)
                continue
            if user == "/snapshot":
                print(snapshot)
                continue
            if user in ("/guides", "/guide"):
                print(guides_list(guides))
                continue
            if user.startswith("/guide "):
                print(guide_text(guides, user[7:].strip()))
                continue
            if user == "/reset":
                messages = [system]
                guides_seen.clear()
                print("Conversation cleared.")
                continue
            if user in ("/undo list", "/undo ls"):
                print(undo.list_text())
                continue
            if user == "/undo":
                note = undo.undo_last()
                log.write("undo", note or "(nothing undone)")
                if not note:
                    continue
                user = note
            elif user == "/report":
                path = write_report(args, messages, events, snapshot_os)
                print(c("Report saved: %s" % path if path else "The report could not be saved.", "1;36"))
                log.write("report", path or "(failed)")
                continue
            elif user.split()[0] == "/rescue":
                sub = user.split()[1] if len(user.split()) > 1 else ""
                try:
                    if sub in ("", "open"):
                        note = rescue.open()
                        if note:
                            note = ("I typed /rescue and Willy opened my installed system. Here is "
                                    "what it found:\n\n" + note + "\n\nPlease work out why it fails "
                                    "and how to fix it.")
                    elif sub == "repair":
                        note = rescue.repair()
                    elif sub in ("off", "close"):
                        note = rescue.close()
                    else:
                        print(rescue.status())
                        continue
                except (RuntimeError, OSError) as exc:
                    print(c("Rescue problem: %s" % exc, "1;31"))
                    continue
                log.write("rescue", note or "(nothing changed)")
                if not note:
                    continue
                if rescue.target:
                    messages[0]["content"] = (SYSTEM_PROMPT + "\n\nSystem snapshot:\n\n" + snapshot
                                              + "\n\n### Rescue status\n" + rescue.status())
                user = note
            elif user.startswith("/run "):
                cmd = user[5:].strip()
                # Your own commands pass the same guardrails when they are not read-only.
                if classify(cmd)[0] != "safe":
                    decision, cmd, level, _ = confirm(cmd, who="You")
                    log.write("approval", "%s [%s] (typed by user): %s" % (decision, level, cmd))
                    if decision == "quit":
                        break
                    if decision != "run":
                        continue
                done = execute(cmd, args, undo, events, "You")
                if done is None:
                    continue
                code, out, note = done
                print(out)
                user = "I ran this myself:\n$ %s\n(exit code %s)%s\n```\n%s\n```" % (
                    cmd, code, note, truncate(out, args.max_output))
            pending = user

        log.write("you", pending)
        messages.append({"role": "user", "content": with_guides(pending)})
        pending = None
        steps = 0
        quitting = False

        while True:
            trim_history(messages, args.history_chars)
            print(c("\nwilly> ", "1;32"), end="", flush=True)
            try:
                reply = ask_model(args.api, messages, args.max_tokens, args.temperature)
            except KeyboardInterrupt:
                print(c("[interrupted]", "33"))
                messages.append({"role": "assistant", "content": "(reply interrupted by the user)"})
                break
            except (urllib.error.URLError, OSError) as exc:
                print(c("Model server error: %s" % exc, "1;31"))
                messages.pop()
                break

            reply = THINK_RE.sub("", reply).strip()
            messages.append({"role": "assistant", "content": reply})
            log.write("willy", reply)

            cmd = extract_command(reply)
            if not cmd:
                break
            slash = re.match(r"^(?:sudo\s+)?(/(?:undo|rescue|report|reset|snapshot|run|help)\b.*)", cmd)
            if slash:
                # A chat command, not a shell command: the user decides whether to type it.
                print(c("  Willy suggests typing  %s  yourself." % slash.group(1), "36"))
                messages.append({"role": "user", "content": "(%s is a chat command I type myself; it "
                                 "was not run as a shell command.)" % slash.group(1)})
                messages.append({"role": "assistant", "content": "Understood."})
                break
            steps += 1
            if steps > args.max_steps:
                print(c("Willy has run %d commands in a row. Tell it how to continue." % args.max_steps, "33"))
                break

            decision, cmd, level, reasons = confirm(cmd)
            log.write("approval", "%s [%s]: %s" % (decision, level, cmd))
            if decision == "quit":
                quitting = True
                break
            if decision == "blocked":
                messages.append({"role": "user", "content":
                    "Willy's guardrails blocked that command (%s). It cannot be run from here. "
                    "Do not try to get around the block. Suggest a safer approach, or explain "
                    "what I could do manually after making a backup." % "; ".join(reasons)})
                continue
            if decision == "skip":
                try:
                    reason = read_line("  Why skip? (optional, Enter to continue): ")
                except KeyboardInterrupt:
                    reason = ""
                except EOFError:
                    print()
                    quitting = True
                    break
                note = "I did not run that command."
                if reason:
                    note += " Reason: " + reason
                messages.append({"role": "user", "content": note + " Suggest another approach."})
                log.write("you", note)
                continue

            done = execute(cmd, args, undo, events, "Willy")
            if done is None:
                messages.append({"role": "user", "content": "I cancelled that command because no "
                                 "backup could be made. Suggest another approach."})
                continue
            code, out, note = done
            print(truncate(out.rstrip(), 4000) or "(no output)")
            print(c("  [exit code %s]" % code, "2"))
            result = "$ %s\n(exit code %s)%s\n```\n%s\n```" % (cmd, code, note,
                                                              truncate(out, args.max_output) or "(no output)")
            log.write("command", result)
            messages.append({"role": "user", "content": with_guides("Output:\n" + result, from_output=True)})

        if quitting:
            break

    if rescue.target:
        print(c("Note: the installed system is still open at %s. Type /rescue off next time, or "
                "just restart the PC." % rescue.target["mountpoint"], "33"))
    if log.fh:
        print("Session log: %s" % log.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
