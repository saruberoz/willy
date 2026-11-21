# Disk still full after deleting files, inodes full, or logs grow forever
Keywords: deleted files still using space "lsof +l1" deleted open files inode df -i "no space left on device" despite free space logrotate log rotation growing logs huge log file large files find size

## Check (read-only)
1. Space versus inodes: `df -h` and `df -i`. When `IUse%` is 100%, the disk has room but no more file slots, usually from millions of tiny files (mail queues, caches, session files).
2. Deleted files still held open by a program (space only returns when it closes them): `sudo lsof +L1 2>/dev/null | head -n 20`
3. Largest files anywhere: `sudo find / -xdev -type f -size +500M -exec du -h {} + 2>/dev/null | sort -rh | head -n 20`
4. Folders with the most files (for inode problems): `sudo du --inodes -x -d 2 / 2>/dev/null | sort -n | tail -n 10`
5. Log rotation setup: `cat /etc/logrotate.conf` and `ls /etc/logrotate.d/`

## Fixes
- **Deleted but still open:** restart the program holding them (the COMMAND column of `lsof +L1`), for example `sudo systemctl restart <service>`. Next time, empty a live log with `sudo truncate -s 0 <file>` instead of deleting it.
- **Inodes full:** find the folder with millions of small files (step 4) and clean what's safe there, such as old cache or session files, rather than deleting system files.
- **A log that grows without limit:** add a rotation rule. Create `/etc/logrotate.d/<app>` with:
  ```
  /var/log/<app>/*.log {
      daily
      rotate 7
      compress
      delaycompress
      missingok
      notifempty
  }
  ```
  Test it without changing anything: `sudo logrotate -d /etc/logrotate.d/<app>`. Rotate once now: `sudo logrotate -f /etc/logrotate.d/<app>`.
- For general space clean-ups (journal, apt, snaps, Docker), see the "Disk full" guide.

## Undo notes
Truncated logs can't be restored unless /undo backed them up (it skips files over 200 MB). A new logrotate file is removed by /undo.
