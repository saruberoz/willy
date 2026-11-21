# Disks, partitions, mounting, "target is busy", and filesystem checks
Keywords: lsblk fdisk parted blkid uuid partition mount umount "target is busy" "device is busy" lazy unmount bind mount findmnt fsck e2fsck xfs_repair tune2fs smartctl self-test hdparm filesystem type df -th

## See the disks (read-only)
- Tree of disks, partitions, filesystems and UUIDs: `lsblk -f`
- Partition tables: `sudo fdisk -l` or `sudo parted -l`
- Filesystem types and space: `df -Th`
- UUIDs and labels: `sudo blkid`
- Disk model and features: `sudo smartctl -i /dev/<disk>` or `sudo hdparm -I /dev/sda`
- Where something is mounted: `findmnt <mountpoint>`, or `findmnt -S /dev/<partition>`

## Mounting
- `sudo mount /dev/<partition> /mnt` (add `-t ext4` etc. if the type isn't detected; `-o ro` for read-only, safest for rescuing data)
- Show a folder at a second place: `sudo mount --bind <source> <destination>`
- Unmount: `sudo umount /mnt`

## "target is busy" when unmounting
1. Who's using it? `sudo fuser -vm /mnt` or `sudo lsof +D /mnt`. Often a terminal whose current folder is inside it (`cd` out of it).
2. Close those programs, then `umount` again.
3. Last resort: `sudo umount -l /mnt` (lazy) detaches it now and finishes when it's no longer in use. **Never unplug the disk** until that has finished.

## Checking a filesystem (fsck)
The filesystem must **not be mounted**. For the root filesystem, boot the rescue USB (see the disk-errors guide).
1. Look first, change nothing: `sudo fsck -n /dev/<partition>`
2. ext4: `sudo e2fsck -f /dev/<partition>` (forced full check; it asks before each fix). `-y` answers yes to all.
3. XFS: `sudo xfs_repair -n /dev/<partition>` to check, then `sudo xfs_repair /dev/<partition>` to repair.
4. Filesystem facts (state, last check, mount count): `sudo tune2fs -l /dev/<partition> | head -n 30`
5. A disk self-test: `sudo smartctl -t short /dev/<disk>`, wait about 2 minutes, then `sudo smartctl -a /dev/<disk> | grep -A5 'Self-test'`.

## Undo notes
Mounts are undone by unmounting. fsck and xfs_repair changes can't be undone: back up important data first when the disk still reads.
