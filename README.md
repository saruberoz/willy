# Willy USB: an offline AI troubleshooter for Linux

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
- **Rescue mode built in.** The stick can start a broken PC with Ubuntu 26.04, so Willy can
  help fix PCs that crash or won't boot.
- **Keeps a record.** Every session is saved in `willy/logs/` on the stick.

## Quick start

Plug in the USB, open a terminal (Ctrl+Alt+T), and run:

```bash
bash /media/$USER/*/willy/start.sh
```

Willy doesn't start by itself when the USB is plugged in. Type `?` inside Willy for help.

## What's on the stick

```
ubuntu-26.04.1-desktop-amd64.iso   live Ubuntu for rescue mode
willy/
  README.md     this overview
  guidance.md   full guide: using Willy, guardrails, rescue mode, troubleshooting
  start.sh      launcher: starts Willy's AI engine, then Willy
  willy.py      the assistant (Python 3, no installs needed)
  bin/          Willy's AI engine
  models/       Willy's AI brains (small and large)
  logs/         a record of every session
```

## Learn more

See **[guidance.md](guidance.md)** for the full guide:

1. Starting Willy
2. Chat commands and things to ask
3. Guardrails
4. Rescue mode
5. Settings
6. Troubleshooting
7. Safety notes
