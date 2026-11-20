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

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if COLOR else text


SYSTEM_PROMPT = """You are Willy, an expert Linux troubleshooting assistant created by \
Wilson Sumanang. You run offline from a USB stick on the user's machine and can ask to run \
shell commands on it.

About yourself:
- Your name is Willy and you were created by Wilson Sumanang. That is all you share about yourself.
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


def gather_snapshot(per_section):
    parts = []
    for label, cmd in BASELINE:
        _, out = run_shell(cmd, 15)
        out = out.strip() or "(no output)"
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


def confirm(cmd, who="Willy"):
    """Ask before running a command.

    Returns (decision, cmd, level, reasons); decision is 'run', 'skip',
    'blocked' or 'quit'. Edited commands are checked again from scratch.
    """
    while True:
        level, reasons = classify(cmd)
        print()
        print(c("  %s wants to run:" % who, "1;33"))
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
  /quit            exit Willy (also stops the AI model)
  Ctrl+C           stop Willy's current reply

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
    args = ap.parse_args()

    if not server_ok(args.api):
        print(c("Cannot reach the model server at %s. Start Willy with start.sh." % args.api, "1;31"))
        return 1

    log = Log(args.log_dir)
    print(c("Willy: offline Linux troubleshooter", "1;32") + c("  (created by Wilson Sumanang)", "2"))
    print("Nothing runs without your approval. Type ? to see commands and examples.")
    print("Collecting system snapshot...", end="", flush=True)
    snapshot = gather_snapshot(1200)
    print(" done.")
    log.write("snapshot", snapshot)

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
            if user == "/reset":
                messages = [system]
                print("Conversation cleared.")
                continue
            if user.startswith("/run "):
                cmd = user[5:].strip()
                # Your own commands pass the same guardrails when they are not read-only.
                if classify(cmd)[0] != "safe":
                    decision, cmd, level, _ = confirm(cmd, who="You")
                    log.write("approval", "%s [%s] (typed by user): %s" % (decision, level, cmd))
                    if decision == "quit":
                        break
                    if decision != "run":
                        continue
                code, out = run_shell(cmd, args.timeout)
                print(out)
                user = "I ran this myself:\n$ %s\n(exit code %s)\n```\n%s\n```" % (
                    cmd, code, truncate(out, args.max_output))
            pending = user

        messages.append({"role": "user", "content": pending})
        log.write("you", pending)
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

            print(c("  running...", "2"))
            code, out = run_shell(cmd, args.timeout)
            print(truncate(out.rstrip(), 4000) or "(no output)")
            print(c("  [exit code %s]" % code, "2"))
            result = "$ %s\n(exit code %s)\n```\n%s\n```" % (cmd, code, truncate(out, args.max_output) or "(no output)")
            messages.append({"role": "user", "content": "Output:\n" + result})
            log.write("command", result)

        if quitting:
            break

    if log.fh:
        print("Session log: %s" % log.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
