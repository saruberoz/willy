# Booting takes a long time
Keywords: slow boot startup takes long "a start job is running" systemd-analyze blame critical-chain NetworkManager-wait-online plymouth timeout 90s fstab device-timeout snapd boot time

## Check (read-only)
1. Total time: `systemd-analyze`
2. Slowest services: `systemd-analyze blame | head -n 15`
3. What the boot actually waited for: `systemd-analyze critical-chain | head -n 25`
4. Timeouts: `journalctl -b --no-pager | grep -iE 'timed out|start job|dependency failed' | tail -n 20`
5. Still waiting right now (boot seems stuck)? `systemctl list-jobs --no-pager`
6. A picture of the whole boot: `systemd-analyze plot > /tmp/boot.svg` (open it in a browser)

## Common causes and fixes
- **"A start job is running for /dev/disk/by-uuid/…" (90 seconds)**: `/etc/fstab` lists a disk that isn't there (removed drive, reformatted partition). Back up fstab with `sudo cp /etc/fstab /etc/fstab.bak`, then add `nofail,x-systemd.device-timeout=10s` to that line's options, or comment the line out if the disk is gone for good. Check the file with `sudo findmnt --verify` afterwards.
- **`NetworkManager-wait-online.service` takes 5–30 s**: most desktops don't need it. `sudo systemctl disable NetworkManager-wait-online.service`.
- **`snapd` or `snapd.seeded` slow**: often only on the first boot after updates. If it's always slow and you don't use snaps, ask before removing snapd.
- **Long firmware or loader times** (in `systemd-analyze` output): set in the BIOS/UEFI; enable "fast boot" there if offered.
- **A slow old hard disk**: everything is slow. An SSD is the real fix.

## Undo notes
Disabling a service is undone with /undo (it re-enables it). fstab edits are undoable with /undo.
