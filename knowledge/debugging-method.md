# How to troubleshoot: method, sanity checks and getting unstuck
Keywords: how to troubleshoot debug where to start method checklist unknown problem something is wrong general diagnosis stuck can't figure out mindset reproduce isolate compare working system what changed sanity check

## The method
1. **Observe:** what exactly happens, since when, and what changed (an update, new hardware, a config edit)?
2. **Reproduce:** find the shortest command that shows the problem. A reproducible problem can be tested and fixed; a vague one can't.
3. **Read the events:** `journalctl -b -p err --no-pager | tail -n 40` and `sudo dmesg -T | tail -n 40`. Read error messages in full and take them literally ("No space left on device", "Permission denied", "Address already in use").
4. **Hypothesis, then test:** pick the most likely cause from the evidence, then one read-only check that confirms or rules it out.
5. **Isolate:** change one thing at a time; remove parts (plugins, extensions, config files, sandboxes) until it works.
6. **Fix, with a backup:** one change at a time.
7. **Verify:** run the reproduction again. Is it really gone?
8. **Record:** `/report` saves what was found and done.

## Sanity checks before going deep
- Is this the right machine, and the right config file (the one the program actually reads)? `systemctl cat <service>` shows which.
- Is the disk full? (`df -h`) Is the clock right? (`timedatectl`) Does DNS work? (`resolvectl query ubuntu.com`)
- Does a config syntax check pass? (`sudo nginx -t`, `sudo sshd -t`, `sudo visudo -c`)
- Is a security layer blocking it? (firewall, SELinux, AppArmor, a sandbox)
- Who else is logged in or running heavy jobs? `who` and `top -b -n 1 | head -n 15`
- Compare with a machine or user account where it works: what's different?

## Quick symptom checklists
**Slow:** `uptime` → `free -h` → `vmstat 1 5` (si/so, wa) → `iostat -x 1 3` → `df -h` (full performance checklist: the triage guide)
**Can't reach a service:** `ping <ip>` → `ping <name>` (IP works but name fails = DNS) → on the server `sudo ss -tlnp` → `curl -v <url>` → firewall
**Service won't start:** `systemctl status <svc>` → `journalctl -u <svc> -n 50` → `systemctl cat <svc>`
**Can't write a file:** `df -h .` → `df -i .` → `ls -la <file>` → `lsattr <file>` → `id`
**It worked yesterday:** `tail -n 40 /var/log/apt/history.log` (or `sudo dnf history`) and compare `journalctl -b -1 -p err` with `journalctl -b -p err`

## When stuck
Write the problem down in one plain sentence; take a break; re-check what the actual goal is; raise the program's log level; read its documentation (`man <program>`); ask someone who knows that system. Understand a command before running it, rather than pasting answers from the internet.

## Undo notes
All checks in this guide are read-only.
