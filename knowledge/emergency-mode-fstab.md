# Boot stops in emergency mode or maintenance mode
Keywords: emergency mode maintenance mode "you are in emergency mode" "give root password for maintenance" "control-d" fstab uuid "dependency failed" mount local-fs.target "timed out waiting for device" boot fails won't boot drops to shell

## What it means
Linux started but couldn't mount a filesystem listed in `/etc/fstab`. Most often a disk was removed or reformatted (its UUID changed), or fstab has a typo.

## Check
In rescue mode (`/rescue`), Willy reads the installed system's fstab and its last boot errors. Then compare:
1. `grep -v '^#' /mnt/willy-target/etc/fstab` (the entries)
2. `lsblk -f` (the UUIDs that actually exist)
3. `sudo findmnt --verify --tab-file /mnt/willy-target/etc/fstab` (checks every entry)

Any fstab UUID that isn't in `lsblk -f` is the culprit, unless it's `/` or `/boot/efi`, which are then a bigger problem.

## Fix (rescue mode)
1. `/rescue repair` (opens the installed system read-write).
2. Back up fstab: `sudo cp /mnt/willy-target/etc/fstab /mnt/willy-target/etc/fstab.willy-bak`
3. For a disk that's gone or optional, either comment the line out with `sudo sed -i 's|^UUID=<uuid>|# &|' /mnt/willy-target/etc/fstab`, or add `nofail` to its options so boot continues without it.
4. If the disk is still there but was reformatted, replace the old UUID with the new one from `lsblk -f`.
5. Verify: `sudo findmnt --verify --tab-file /mnt/willy-target/etc/fstab`, then `/rescue off` and restart.

## Avoiding it next time
- Always refer to disks by `UUID=` (from `lsblk -f` or `sudo blkid`), never `/dev/sdb1`, since names can change.
- After editing fstab on a running system, test it **before** rebooting: `sudo findmnt --verify` and `sudo mount -a` (an error here would have stopped the boot).
- Network shares (NFS, SMB/CIFS) need `_netdev,nofail` in their options so boot doesn't wait for the network.

## Fix without the rescue USB
At the emergency prompt, type the root password (Ubuntu has none set, so use rescue mode instead), then `mount -o remount,rw /`, edit `/etc/fstab` with `nano`, and reboot.

## Undo notes
fstab edits are restored with /undo, and the `.willy-bak` copy stays as a second safety net.
