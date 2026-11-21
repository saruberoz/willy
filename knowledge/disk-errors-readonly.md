# "Read-only file system", disk errors, or is my disk healthy?
Keywords: read-only readonly read-only file system filesystem can't save files cannot write files "remounting filesystem read-only" ext4-fs error "i/o error" buffer i/o bad sectors smart smartctl nvme health failing disk fsck corrupt corrupted inode journal disk health check

## Check (read-only)
1. Errors from the disk or filesystem: `journalctl -k -b --no-pager | grep -iE 'ext4-fs|xfs|btrfs|i/o error|read-only|nvme|ata[0-9]' | tail -n 30`
2. Is `/` read-only? `findmnt -no OPTIONS /` (starts with `ro`)
3. Disk health (smartmontools): `sudo smartctl -H /dev/sda` or `sudo smartctl -H /dev/nvme0`; details with `sudo smartctl -a /dev/<disk> | head -n 60`. For NVMe also `sudo nvme smart-log /dev/nvme0`.
4. Space: `df -h` (a full disk gives different errors than a broken one)

## Reading the results
- **"EXT4-fs error … Remounting filesystem read-only"**: the filesystem found damage and protected itself. It needs a filesystem check (`fsck`).
- **"I/O error" / "Buffer I/O error" / failing SMART** ("FAILED", reallocated or pending sectors rising, NVMe "critical_warning" not 0, "Percentage Used" near 100%): the **disk itself is failing**. Copy important data off **first**, before anything else, then replace the disk.

## Fixing filesystem damage safely
`fsck` must run while the filesystem is **not mounted**, so the root filesystem can't be checked from the running system:
1. Back up important files first, while the disk still reads.
2. Boot the rescue USB, start Willy, and **don't** open the system with /rescue (it must stay unmounted). If it is open, run `/rescue off` first.
3. Find the partition with `lsblk -f`, then `sudo fsck -f /dev/<partition>` (for example `/dev/nvme0n1p2`). Answer its questions, or add `-y` to accept all fixes.
4. Restart normally.

On a running system, a non-root partition (for example `/data`) can be unmounted and checked: `sudo umount /data && sudo fsck -f /dev/<partition>`.

## Undo notes
fsck repairs can't be undone with /undo. That's why you back up first.
