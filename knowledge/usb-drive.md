# USB drive or external disk not detected or won't open
Keywords: usb drive stick flash external disk hard drive not detected not showing won't mount "wrong fs type" "unknown filesystem type" exfat ntfs "unsafe state" hibernated windows fast startup lsblk lsusb dmesg

## Check (read-only)
1. Plug it in, then: `journalctl -k --no-pager | tail -n 20` (do you see "new USB device" and a disk name like `sdb`?)
2. Seen as a USB device? `lsusb`
3. Disks and partitions with filesystem types: `lsblk -f`
4. Try mounting by hand to see the real error: `udisksctl mount -b /dev/sdX1` (use the partition from step 3)

## Causes and fixes
- **Nothing in the log or `lsusb`**: hardware. Try another port (directly on the PC, not a hub) and another cable. A disk that needs more power may need a powered hub.
- **Seen, but "unknown filesystem type 'exfat'"**: install support: `sudo apt install exfatprogs`.
- **NTFS "unsafe state" / "hibernated" / read-only**: Windows didn't shut the disk down cleanly (Fast Startup). Best fix: plug it into Windows and use Shut down while holding Shift, or disable Fast Startup there. Otherwise `sudo ntfsfix /dev/sdX1` fixes common problems.
- **No partitions shown** (`lsblk` lists `sdb` with nothing under it): the disk may be blank or the partition table damaged. **Don't format it** if it holds data. Copy what you can first; `testdisk` can recover partitions.
- **I/O errors in the log**: the disk may be failing. Copy important files off right away (see the disk-errors guide).

## Undo notes
`ntfsfix` and recovery tools change the disk and can't be undone with /undo. Copy important data off first when possible.
