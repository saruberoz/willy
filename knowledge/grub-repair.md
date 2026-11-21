# GRUB broken: "grub rescue>", "no such partition", or Linux missing from the boot menu
Keywords: grub "grub rescue" "no such partition" "unknown filesystem" "minimal bash-like" bootloader boot menu missing windows update overwrote dual boot efi uefi bios mbr grub-install update-grub os-prober secure boot "no bootable device" efibootmgr

## What it means
The bootloader (GRUB) is damaged, points to a partition that moved, or was replaced, often by a Windows update on dual-boot PCs.

## Check (in rescue mode)
1. `/rescue`, then `/rescue repair` (needed: it mounts the installed system with its /boot and /boot/efi).
2. Is this PC booted in UEFI or old BIOS mode? `[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS` (the rescue USB boots the same way the PC does)
3. UEFI boot entries: `sudo efibootmgr -v` (UEFI only)
4. The disk holding Linux: `lsblk -f` (for BIOS mode you need the whole disk, like `/dev/sda`, not `/dev/sda2`)

## Fix
- **UEFI PCs (most since 2013):**
  `sudo chroot /mnt/willy-target grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu`
  then `sudo chroot /mnt/willy-target update-grub`
- **BIOS/legacy PCs:**
  `sudo chroot /mnt/willy-target grub-install /dev/sdX` (whole disk)
  then `sudo chroot /mnt/willy-target update-grub`
- **Dual boot and Windows is missing from the menu:** enable os-prober. Add `GRUB_DISABLE_OS_PROBER=false` to `/mnt/willy-target/etc/default/grub` (back it up first), then run `update-grub` again.
- **Windows boots straight away and Linux never appears (UEFI):** the boot order changed. Pick "ubuntu" in the PC's boot menu (F12, F11 or Esc) or the UEFI settings. `sudo efibootmgr` shows the order.

Then `/rescue off` and restart without the USB.

## Booting by hand from the grub rescue> prompt (one time)
Type these at the prompt itself: `ls` lists disks such as `(hd0,gpt2)`; `ls (hd0,gpt2)/` until one shows `boot/`; then `set root=(hd0,gpt2)`, `set prefix=(hd0,gpt2)/boot/grub`, `insmod normal`, `normal`. Once Linux is up, run `sudo grub-install` and `sudo update-grub` as above to make it permanent.

## If grub-install fails
- "cannot find EFI directory": /boot/efi isn't mounted. Check `findmnt /mnt/willy-target/boot/efi`; it should come from the installed system's fstab.
- With Secure Boot on, Ubuntu's signed GRUB (`shim-signed`, `grub-efi-amd64-signed`) is needed. These are installed by default.

## Undo notes
grub-install can't be undone with /undo. update-grub regenerates `/boot/grub/grub.cfg`, which /undo can restore.
