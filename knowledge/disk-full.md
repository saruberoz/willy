# Disk full: "No space left on device"
Keywords: disk full disk is full full disk disk space running out of space free up space "no space left on device" df du storage journal logs /var/log apt cache snap revisions flatpak docker trash thumbnails cache large files cleanup free space

## Check (read-only)
1. Which filesystem is full? `df -h -x tmpfs -x squashfs`
2. What uses the space? `sudo du -xh --max-depth=1 / 2>/dev/null | sort -h | tail -n 12`, then go deeper into the biggest folder (for example `sudo du -xh --max-depth=2 /var | sort -h | tail`).
3. System logs: `journalctl --disk-usage`
4. Snap old versions: `snap list --all | grep disabled`
5. Your own files: `du -h --max-depth=1 ~ 2>/dev/null | sort -h | tail -n 10`
6. If `df` shows space but writes still fail, check inodes: `df -i`

## Safe clean-ups (biggest wins first)
- **Huge system journal (`/var/log/journal`)**: `sudo journalctl --vacuum-size=500M`, and make it permanent by setting `SystemMaxUse=500M` in `/etc/systemd/journald.conf`.
- **A runaway log file** (`/var/log/syslog`, `kern.log` growing by GBs): find what is spamming it first (`tail -n 50 /var/log/syslog`). Empty it with `sudo truncate -s 0 /var/log/syslog` rather than deleting it.
- **Package cache**: `sudo apt clean` (Fedora/RHEL: `sudo dnf clean all`). **Unused packages and old kernels**: `sudo apt autoremove --purge`.
- **Space didn't come back after deleting, or `df -i` is at 100%**: see the "Disk still full after deleting files" guide.
- **Old snap versions**: for each disabled one, `sudo snap remove <name> --revision=<rev>`. Keep fewer in future: `sudo snap set system refresh.retain=2`.
- **Flatpak leftovers**: `flatpak uninstall --unused`.
- **Docker**: `docker system df` to look, then `docker system prune` (deletes stopped containers and unused images).
- **Trash and thumbnails**: `~/.local/share/Trash` and `~/.cache/thumbnails`.
- **/boot is full** rather than `/`: see the "/boot is full" guide.

## Never
Don't delete files under `/usr`, `/lib`, `/etc` or `/var/lib/dpkg` to free space.

## Undo notes
Deleted logs, caches and snap revisions can't be restored by /undo if they are larger than 200 MB, so check the size first. Package clean-ups can't be undone either, but nothing important is lost.
