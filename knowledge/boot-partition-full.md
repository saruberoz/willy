# /boot is full, kernel updates fail
Keywords: /boot full "no space left on device" initramfs update-initramfs kernel update fails linux-image old kernels autoremove dpkg error processing package linux-image boot partition

## Check (read-only)
1. `df -h /boot` (a separate `/boot` partition at 90–100%)
2. Which kernel is running? `uname -r` (**never remove this one**)
3. Installed kernels: `dpkg -l 'linux-image-*' | grep ^ii`
4. Files there: `ls -lh /boot`

## Fix
1. Try the normal way first: `sudo apt autoremove --purge`. This removes kernels that are no longer needed and keeps the running one plus the newest.
2. If apt itself fails because /boot is full, remove one old kernel explicitly. Pick a version that is **not** `uname -r` and not the newest:
   `sudo apt purge linux-image-<version>-generic linux-modules-<version>-generic`
3. Then finish any half-done installs: `sudo dpkg --configure -a` and `sudo apt --fix-broken install`.
4. Rebuild boot images for the remaining kernels: `sudo update-initramfs -u -k all`.

## Keep it from happening again
`sudo apt autoremove --purge` after big updates. Always keep at least two kernels (the running one and one older) so you can boot an older one if an update goes wrong.

## Undo notes
Removing kernels can't be undone with /undo. That's why you keep the running kernel and one spare.
