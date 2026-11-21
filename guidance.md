# Willy USB: guidance

How to start and use Willy. For a short overview, see `README.md`.

## Contents

1. [Start Willy](#1-start-willy)
2. [Talking to Willy](#2-talking-to-willy)
3. [Guardrails: Willy always asks first](#3-guardrails-willy-always-asks-first)
4. [Rescue mode: a PC that won't boot](#4-rescue-mode-a-pc-that-wont-boot)
5. [Settings](#5-settings)
6. [Troubleshooting](#6-troubleshooting)
7. [Safety notes](#7-safety-notes)

## 1. Start Willy

Willy does **not** start by itself when you plug in the stick. Linux never runs programs
from a USB drive automatically, which protects you from USB malware.

1. **Plug in the USB.** Most desktops mount it automatically. You can close the file window if one opens.
2. **Open a terminal.** Ctrl+Alt+T works on most distros.
3. **Run:**

   ```bash
   bash /media/$USER/*/willy/start.sh
   ```

   If it can't find the file, run `lsblk` to see where the USB is mounted. Some distros
   use `/run/media/<your-username>/...` instead.
4. **Wait for the model to load.** You'll see `Starting Willy (large brain...)`. It takes up to a minute from USB.
5. **Describe your problem in plain words** at the prompt.
6. **Type `/quit` when you're done.** The model stops and a session log is saved in `willy/logs/`.

You can also describe the problem in the start command, so Willy begins right away:

```bash
bash /media/$USER/*/willy/start.sh "the disk is full and I don't know why"
```

## 2. Talking to Willy

Type `?` at any time to see the help screen inside Willy.

### Chat commands

| Command      | What it does                                                    |
|--------------|-----------------------------------------------------------------|
| `?`          | help: shows commands, how to approve, example questions and handy checks |
| `/run <cmd>` | run a command yourself and share its output with Willy          |
| `/snapshot`  | show the system overview Willy collected at startup             |
| `/reset`     | start a new conversation                                        |
| `/undo`      | reverse the last change (`/undo list` shows every change you can undo) |
| `/report`    | save a one-page summary: problem, cause, what was fixed, what's left |
| `/rescue`    | rescue mode: find and open the PC's installed Linux (see section 4) |
| `/quit`      | exit Willy (also stops its AI engine)                           |
| Ctrl+C       | stop Willy's current reply                                      |

### Undo: reversing a change

Before any approved command that changes or deletes files, Willy saves a backup of exactly
the files it will touch, and the approval prompt tells you so:

```
  Willy wants to run:
    $ sudo sed -i 's/^UUID=old/UUID=new/' /etc/fstab
  CHANGES YOUR SYSTEM: runs as root; edits files in place.
  Undo: Willy will back up /etc/fstab first.
```

If the fix doesn't help, type `/undo` and the files go back exactly as they were, including
permissions and owners. Service changes (`systemctl enable/disable/mask/start/stop`) are undone
by reversing them, and files the command created are removed.

**Some changes can't be undone**, and Willy tells you *before* you approve them: installing or
removing software, disk and partition changes, and bootloader installs. Backups are kept in
`willy/backups/` on the stick (files over 200 MB are skipped, and Willy says so).

### Reports

Type `/report` at the end of a session. Willy writes a plain-language summary (problem, what
was checked, cause, what was changed, what's left to do) plus a table of every command run, and
saves it in `willy/reports/` on the stick. It's handy to keep or to give to the PC's owner.

### Answering Willy's requests

When Willy wants to run a command, it shows the command and waits for you:

```
willy> Let me check whether the wireless driver loaded.
  Willy wants to run:
    $ journalctl -b -k --no-pager | grep -iE 'wlan|wifi|iwlwifi|firmware' | tail -n 30
  Run it? [y] yes, [n] skip, [e] edit, [q] quit:
```

| You type | Effect                                          |
|----------|-------------------------------------------------|
| `y`      | runs a safe, read-only check                    |
| `yes`    | runs a command that changes the system          |
| `delete` | runs a command that deletes or overwrites data  |
| Enter    | skips it; nothing runs                          |
| `e`      | edit the command first                          |
| `q`      | quit Willy                                      |

### Things you can ask

- my wifi stopped working after an update
- the disk is full, what is using the space?
- the PC is slow, what is eating CPU or memory?
- why did this boot take so long?
- a service failed to start, how do I fix it?
- is my disk healthy?
- I can't install updates, apt/dnf shows errors
- no sound, or the screen resolution is wrong

### Handy checks you can run yourself

| Command | Shows |
|---------|-------|
| `/run df -h` | disk space |
| `/run free -h` | memory |
| `/run systemctl --failed --no-pager` | failed services |
| `/run journalctl -b -p err --no-pager \| tail -n 30` | errors this boot |
| `/run ip -br addr` | network addresses |
| `/run ping -c 3 1.1.1.1` | whether the internet is reachable |
| `/run lsblk -f` | disks and partitions |
| `/run du -xh / 2>/dev/null \| sort -h \| tail -n 15` | biggest folders |
| `/run ps aux --sort=-%cpu \| head` | busiest programs |
| `/run systemd-analyze blame \| head -n 15` | slow boot services |

## 3. Guardrails: Willy always asks first

Willy never runs anything on its own. Before any command runs, whether Willy suggests it or
you type it with `/run`, it is sorted into one of four levels. The more dangerous the
command, the more deliberately you have to approve it.

| Level | Examples | To approve |
|-------|----------|------------|
| **Safe** (read-only) | `df -h`, `journalctl -b`, `lsblk`, `cat /etc/fstab` | type `y` |
| **Changes the system** | `sudo ...`, installing packages, restarting services, `mount`, editing files with `sed -i`, `cp`/`mv`, network or firewall changes, downloads, GRUB/initramfs | type the full word `yes` |
| **Deletes or overwrites data** | `rm`, `find -delete`, uninstalling packages, `dd`, `mkfs`, partitioning, `> file`, `tee file`, `git reset --hard`, `crontab -r`, clearing logs | type the full word `delete` |
| **Blocked** | `rm -rf /`, `rm -rf ~`, `rm -rf /etc` (or any system folder), `chmod -R ... /`, writing straight to a disk with `> /dev/sda`, fork bombs | **cannot be run from Willy at all** |

More rules:

- **Before every delete, Willy warns you in red**, says what the command will remove, and
  reminds you to have a backup. Answering `y` or `yes` is not enough; you have to type `delete`.
- **Pressing Enter on its own, or anything Willy doesn't understand, skips the command.**
  Nothing runs by accident.
- **`e` lets you edit a command before it runs.** The edited command is checked again from scratch.
- **Hidden commands are flagged.** `eval`, `base64 -d`, `bash -c` and piping a download into
  a shell all need `yes`, because the check can't see what they will do.
- **Willy is told to prefer reversible fixes**: back up a config file before editing it,
  disable a service rather than remove it, move files to a backup folder rather than delete them.
- **If a command is blocked**, Willy is told not to work around it and to suggest a safer approach.
- **Every decision is logged.** Each approval, skip and block is written to the session log
  in `willy/logs/`, with the exact command.

The checks deliberately err on the side of asking: a false alarm costs you one word, while
a missed one could cost you your data. Guardrails reduce mistakes but can't catch everything,
so still read each command before you approve it.

## 4. Rescue mode: a PC that won't boot

The stick can start a PC by itself, using the Ubuntu 26.04 live system stored on it.
Use this when Linux crashes, freezes at startup, shows a black screen, drops to
`grub rescue>`, or won't boot at all.

1. Plug the stick into the broken PC and turn it on.
2. Open the boot menu straight away. The key is usually **F12**, **F11**, **F8** or **Esc**,
   depending on the PC maker; the screen often shows it briefly.
3. Choose the USB stick. A menu appears listing `ubuntu-26.04.1-desktop-amd64.iso`; select it
   and choose the normal boot option.
4. When Ubuntu starts, choose **Try Ubuntu** (not Install). Nothing is changed on the PC's disk.
5. Open a terminal (Ctrl+Alt+T) and run:

   ```bash
   bash /media/*/Ventoy/willy/start.sh
   ```

6. Willy notices it's running from the rescue USB. Type **`/rescue`** and Willy:
   - finds the PC's installed Linux on its internal disks, and if there's more than one
     it asks which. Encrypted disks are supported: **you** type the disk passphrase and
     Willy never sees it.
   - opens it **read-only**. Nothing on the PC's disk is written, not even a journal replay.
   - reads why it failed: errors from its last boots, its kernels, its `/etc/fstab`, recent
     software updates and disk space. It then explains the likely cause.
7. To fix it, type **`/rescue repair`**. Willy opens the system read-write and connects it so
   repair tools (GRUB, initramfs, the package manager) run inside it. Every repair command still
   needs your approval, and file changes can be reversed with `/undo`.
8. When you're done, type **`/rescue off`** to close everything safely, then restart the PC
   without the stick.

`/rescue status` shows what is open. Each `/rescue` step lists its exact commands and waits for
your approval before running them.

### If the boot menu doesn't show the stick

- Look in the PC's firmware settings (often F2 or Del at power-on) for "Secure Boot". If the
  stick's menu says the image is not trusted, follow its on-screen "Enroll key" steps once,
  or turn Secure Boot off temporarily.
- Try a different USB port, preferably one directly on the PC rather than a hub.

## 5. Settings

Set these before the start command, for example `WILLY_THREADS=4 bash .../start.sh`.

| Setting | Default | What it does |
|---------|---------|--------------|
| `WILLY_MODEL` | the largest brain that fits in RAM | `.../willy/models/willy-small.gguf` or `willy-large.gguf` |
| `WILLY_CTX` | `8192` | how much of the conversation Willy remembers |
| `WILLY_THREADS` | all cores | CPU threads Willy uses |
| `WILLY_PORT` | `8080` | local port for Willy's engine |
| `WILLY_GPU` | on when an NVIDIA or AMD card is found | set to `0` to always use the CPU |

**Graphics cards:** Willy tries to use an NVIDIA or AMD card automatically, which makes replies
much faster. It needs the card's driver installed. When the card can't be used, Willy says so
at startup and runs on the CPU instead.
The Ubuntu rescue system uses open-source drivers, so in rescue mode Willy usually runs on the CPU.

## 6. Troubleshooting

- **"could not run willy-engine"**: some distros let WINE intercept the engine.
  Run `sudo sh -c 'echo -1 > /proc/sys/fs/binfmt_misc/status'` for this session, then try again.
- **Very slow replies**: use the small brain (`WILLY_MODEL=.../willy/models/willy-small.gguf`) or
  close other programs. Expect 3–10 words a second on a typical laptop CPU.
- **Port 8080 already in use**: `WILLY_PORT=8099 bash start.sh`.
- **"python3 is required"**: almost every distro ships Python 3. On a minimal install,
  install it with your package manager first.

## 7. Safety notes

- The AI can be wrong. Read each command before approving it, especially red ones.
- Back up important data before letting it change disks, the bootloader or packages.
- Everything runs locally, so nothing is sent off the machine. Session logs, backups and reports
  are saved in `willy/logs/`, `willy/backups/` and `willy/reports/` on the stick. They may contain
  hostnames, usernames, paths and copies of settings files from that PC, so clear them before
  giving the stick to someone else.

---

Willy USB was created by **Wilson Sumanang**.
