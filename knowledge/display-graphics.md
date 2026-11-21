# Wrong screen resolution, black screen, or graphics driver problems
Keywords: display screen resolution monitor black screen blank screen flicker graphics gpu nvidia amd intel nouveau driver xrandr wayland x11 nomodeset "low graphics mode" external monitor hdmi second monitor ubuntu-drivers

## Check (read-only)
1. Session type: `echo $XDG_SESSION_TYPE` (wayland or x11)
2. Graphics chip and driver in use: `lspci -nnk | grep -A3 -E 'VGA|3D|Display'`
3. NVIDIA driver state: `nvidia-smi` (an error means the NVIDIA driver isn't loaded), and `ubuntu-drivers list`
4. Monitors and modes (X11): `xrandr`
5. Errors: `journalctl -b -k --no-pager | grep -iE 'drm|nvidia|amdgpu|i915|nouveau' | tail -n 30`

## Causes and fixes
- **Resolution stuck low, or only one "Unknown display"**: no proper driver loaded (step 2 shows `vesa`, `simpledrm` or no driver). On NVIDIA: `sudo ubuntu-drivers install`, then reboot (needs internet).
- **Wrong resolution with a working driver**: choose it in Settings → Displays. On X11 you can test with `xrandr --output <name> --mode 1920x1080`.
- **Black screen after an NVIDIA driver update**: from the GRUB menu, boot the previous kernel, or press `e` and add `nomodeset` to the `linux` line to boot once with basic graphics. Then reinstall the driver: `sudo apt purge 'nvidia-*' 'libnvidia-*'` followed by `sudo ubuntu-drivers install`. If the PC won't reach a desktop at all, use rescue mode: `/rescue`, `/rescue repair`, then run those commands with `sudo chroot /mnt/willy-target …`.
- **External monitor not detected**: try another cable or port. Check the monitor appears in `xrandr` (X11) or Settings → Displays. With hybrid graphics, the HDMI port is often wired to the NVIDIA card, so its driver must be working.
- **Flicker or tearing on Intel/AMD**: usually fixed by kernel and Mesa updates. `sudo apt update && sudo apt upgrade`.

## Undo notes
Driver installs and removals can't be undone with /undo. Keep the `nomodeset` trick in mind as the way back in.
