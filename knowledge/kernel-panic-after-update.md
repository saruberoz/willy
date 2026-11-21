# Kernel panic or won't boot after an update
Keywords: kernel panic "not syncing" "vfs: unable to mount root fs" "unknown-block(0,0)" initramfs initrd missing "end kernel panic" freeze after update black screen after update update broke boot older kernel advanced options update-initramfs

## First aid: boot the previous kernel
1. Restart. Hold **Shift** (BIOS PCs) or tap **Esc** (UEFI PCs) to show the GRUB menu.
2. Choose **Advanced options for Ubuntu**, then the second-newest kernel (not "recovery mode").
3. If that boots, the newest kernel or its initramfs is the problem.

## Check
From the running older kernel, or in rescue mode with /rescue:
1. Installed kernels: `ls /boot` (each `vmlinuz-<version>` needs a matching `initrd.img-<version>`)
2. The last update: `tail -n 40 /var/log/apt/history.log` (in rescue mode: `/mnt/willy-target/var/log/apt/history.log`)
3. "VFS: Unable to mount root fs on unknown-block(0,0)" almost always means the **initramfs is missing or broken** for that kernel.

## Fix
- **Missing or broken initramfs:** rebuild it with `sudo update-initramfs -c -k <version>` (in rescue mode, after `/rescue repair`: `sudo chroot /mnt/willy-target update-initramfs -c -k <version>`), then `update-grub`. Running `sudo update-initramfs -u -k all` updates every kernel.
- **The update was interrupted:** `sudo dpkg --configure -a` then `sudo apt --fix-broken install` (in rescue mode, prefix with `sudo chroot /mnt/willy-target`).
- **The new kernel is simply broken for this hardware:** keep booting the older one and remove the bad one: `sudo apt purge linux-image-<bad version>`. Wait for the next kernel update.
- **It was a driver update (NVIDIA, VirtualBox and similar):** see the graphics guide.

## Undo notes
Kernel removal and initramfs rebuilds can't be undone with /undo. Never remove the kernel you are currently running (`uname -r`).
