# A service won't start (nginx, apache, ssh, docker, mysql and others)
Keywords: service fails failed won't start systemctl status journalctl unit "failed to start" "job for" "control process exited" "address already in use" bind port permission denied config syntax nginx apache2 httpd ssh sshd docker mysql mariadb postgresql

## Check (read-only)
1. `systemctl status <service> --no-pager -l`
2. Its log from this boot: `journalctl -u <service> -b --no-pager | tail -n 40`
3. All failed services: `systemctl --failed --no-pager`
4. Config test, where the program has one: `sudo nginx -t`, `sudo apachectl configtest`, `sudo sshd -t`, `docker info`
5. What it actually runs (unit file plus overrides): `systemctl cat <service>`; what it needs first: `systemctl list-dependencies <service> --no-pager`
6. Quick state: `systemctl is-active <service>` and `systemctl is-enabled <service>` (`masked` means it was deliberately blocked: `sudo systemctl unmask <service>`)

## Match the error
- **"Address already in use" / "bind() to 0.0.0.0:80 failed (98)"**: another program holds the port. Find it with `sudo ss -ltnp 'sport = :80'` (use the port from the error). Usually two web servers (nginx and apache2) are fighting: stop and disable the one you don't want, for example `sudo systemctl disable --now apache2`, then `sudo systemctl restart nginx`.
- **Syntax or config errors** (the config test fails, or "unknown directive"): the test output names the file and line. Back up the file before editing it.
- **"Permission denied"** on a file or socket: check ownership with `ls -l <path>`. Often a file copied as root, or a directory with the wrong owner.
- **"No such file or directory"** for a certificate, socket or data directory: the path in the config is wrong, or a disk or mount is missing.
- **Start limit hit / restarting too quickly**: fix the real cause first, then `sudo systemctl reset-failed <service>` and start it again.
- **Disk full**: many services fail to start when `/` or `/var` is full (`df -h`).

- **Changing how a service runs** (limits, environment, restart policy): `sudo systemctl edit <service>` creates an override file (interactive, so you type it yourself), never edit files in `/usr/lib/systemd`. After changing unit files by hand: `sudo systemctl daemon-reload`.

## After fixing
`sudo systemctl restart <service>`, then `systemctl status <service> --no-pager` to confirm it's "active (running)".

## Undo notes
`systemctl disable/enable/stop/start` changes are undone with /undo. Edited config files are restored by /undo.
