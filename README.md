# Willy USB: an offline AI troubleshooter for Linux

[![tests](https://github.com/saruberoz/willy/actions/workflows/tests.yml/badge.svg)](https://github.com/saruberoz/willy/actions/workflows/tests.yml)

*Created by Wilson Sumanang.*

Willy is an AI assistant that lives on a USB stick. Plug it into a Linux PC, run one
command, and describe what's wrong in plain words. Willy looks into the system, asks to
run diagnostic commands, and explains the cause and how to fix it.

```
you (? for help)> wifi stopped working after the last update

willy> Let me check whether the wireless driver loaded.
  Willy wants to run:
    $ journalctl -b -k --no-pager | grep -iE 'wlan|wifi|iwlwifi|firmware' | tail -n 30
  Run it? [y] yes, [n] skip, [e] edit, [q] quit:
```

## Highlights

- **Works offline.** Willy's AI runs on the PC's own CPU, so nothing is sent anywhere.
- **Nothing to install.** Everything Willy needs is on the stick.
- **Always asks first.** Every command needs your approval. Deleting data requires typing
  `delete`, and the most dangerous commands are blocked entirely.
- **Fits the PC.** Willy uses its large brain when there's enough memory and its small
  brain on older machines.
- **Rescue mode built in.** The stick can start a broken PC with Ubuntu 26.04. Type `/rescue`
  and Willy finds the PC's own Linux, opens it read-only and reads why it failed.
- **Undo.** Willy backs up the files a fix will touch, and `/undo` puts them back exactly.
- **Reports.** `/report` saves a one-page summary of the problem, the cause and the fix.
- **Keeps a record.** Every session is saved in `willy/logs/` on the stick.

## Quick start

Plug in the USB, open a terminal (Ctrl+Alt+T), and run:

```bash
bash /media/$USER/*/willy/start.sh
```

Willy doesn't start by itself when the USB is plugged in. Type `?` inside Willy for help.

## What's on the stick

```
START-HERE.txt                     the quick steps, for anyone who opens the stick
ubuntu-26.04.1-desktop-amd64.iso   live Ubuntu for rescue mode
willy/
  README.md        this overview
  guidance.md      full guide: using Willy, guardrails, undo, rescue mode, troubleshooting
  start.sh         launcher: starts Willy's AI engine, then Willy
  willy.py         the assistant (Python 3, no installs needed)
  willy_rescue.py  rescue mode: finds, opens and repairs the PC's installed Linux
  willy_undo.py    backups and /undo
  bin/             Willy's AI engine
  models/          Willy's AI brains (small and large)
  logs/  backups/  reports/   session records, undo backups and /report summaries
```

## Build a stick

On Linux (or WSL), from this repository:

```bash
sudo bash setup-usb.sh --rescue /dev/sdX          # complete rescue stick (ERASES the stick)
bash setup-usb.sh /media/$USER/MYUSB              # Willy only, on an exFAT stick
```

Add `--dry-run` to preview every step, or `--share` for sticks you give away (adds the
third-party licences). Every download is verified against a pinned checksum.

## Learn more

See **[guidance.md](guidance.md)** for the full guide:

1. Starting Willy
2. Chat commands and things to ask
3. Guardrails
4. Rescue mode
5. Settings
6. Troubleshooting
7. Safety notes

## License

Willy's code is released under the [MIT License](LICENSE). © 2026 Wilson Sumanang.

The AI brains, the engine, Ventoy and Ubuntu are not part of this repository. They are
separate projects with their own licences, downloaded when a stick is built.
