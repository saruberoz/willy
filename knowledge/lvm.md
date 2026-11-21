# LVM: logical volumes full, extending a volume, snapshots
Keywords: lvm lvs vgs pvs logical volume volume group physical volume lvextend resize2fs xfs_growfs extend grow partition snapshot lvcreate lvremove ubuntu-vg ubuntu-lv root full free space in volume group

## Check (read-only)
1. Is LVM in use? `lsblk` (types `lvm`) and `sudo lvs`
2. Volume groups and free space in them: `sudo vgs` (the `VFree` column)
3. Physical disks behind them: `sudo pvs`
4. Filesystem type on the volume: `df -Th`

## A common Ubuntu surprise
Ubuntu's installer often creates the root volume (`ubuntu-vg/ubuntu-lv`) **smaller than the disk** and leaves the rest free in the volume group. If `vgs` shows `VFree`, you can grow root without touching partitions.

## Extend a volume and its filesystem
1. Back up important data first.
2. Grow the volume **and** filesystem in one step (works for ext4 and XFS): `sudo lvextend -r -L +10G /dev/<vg>/<lv>` (or `-l +100%FREE` for all free space)
3. Or in two steps: `sudo lvextend -L +10G /dev/<vg>/<lv>`, then the filesystem: ext4 `sudo resize2fs /dev/<vg>/<lv>`, XFS `sudo xfs_growfs <mountpoint>`
4. Check: `df -h`

Shrinking is risky (data loss if done wrong) and impossible for XFS. Don't shrink without a full backup.

## Snapshots (a safety net before risky changes)
- Create: `sudo lvcreate -L 5G -s -n before-change /dev/<vg>/<lv>` (needs free space in the volume group)
- List: `sudo lvs`
- Remove when no longer needed: `sudo lvremove /dev/<vg>/before-change`. A snapshot that fills up becomes invalid, so don't keep it forever.

## Undo notes
Growing a volume can't be reversed with /undo, but it loses no data. Removed snapshots are gone for good.
