# Kernel modules and drivers: won't load, missing after update, DKMS, Secure Boot
Keywords: kernel module driver lsmod modinfo modprobe insmod rmmod "unknown symbol" "module not found" "key was rejected by service" "required key not available" dkms secure boot mok signing linux-headers out-of-tree driver virtualbox nvidia vmware blacklist

## Check (read-only)
1. Loaded? `lsmod | grep <module>`
2. Exists for this kernel? `modinfo <module>` (shows file path, version, parameters, dependencies); `uname -r` for the running kernel
3. Why loading failed: `sudo dmesg -T | tail -n 20` right after trying `sudo modprobe <module>`
4. Out-of-tree drivers (NVIDIA, VirtualBox, some Wi-Fi): `dkms status`
5. Secure Boot on? `mokutil --sb-state`
6. Blacklisted? `grep -r <module> /etc/modprobe.d/`

## Match the problem
- **"Module not found" after a kernel update:** the module wasn't built for the new kernel. For DKMS drivers: install headers for this kernel, `sudo apt install linux-headers-$(uname -r)` (needs internet), then `sudo dkms autoinstall`. Or boot the previous kernel from GRUB's Advanced options.
- **"Key was rejected by service" / "Required key not available":** Secure Boot refuses an unsigned module. Either enroll the DKMS signing key (`sudo mokutil --import /var/lib/shim-signed/mok/MOK.der`, set a one-time password, and confirm it in the blue MOK screen at the next boot), or turn off Secure Boot in the firmware settings.
- **"Unknown symbol" with insmod:** dependencies weren't loaded. Use `sudo modprobe <module>`, which loads them, instead of `insmod`.
- **Driver loaded but device still not working:** reload it with `sudo modprobe -r <module> && sudo modprobe <module>` and check `dmesg` again; it may need firmware (`linux-firmware` package).
- **Wrong driver grabs a device:** blacklist the unwanted one in `/etc/modprobe.d/blacklist-<name>.conf` with the line `blacklist <module>`, then `sudo update-initramfs -u` and reboot.

## For developers
Build modules against the running kernel's headers (`/lib/modules/$(uname -r)/build`), test with `insmod`/`rmmod`, and read your `printk` output with `dmesg`. Debugging a built-in module: match the kernel source to `uname -r` exactly.

## Undo notes
Loading or unloading modules lasts until reboot. /undo removes a blacklist file it saw created. Rerun `update-initramfs -u` after undoing a blacklist.
