# Wi-Fi stopped working or no Wi-Fi adapter found
Keywords: wifi wi-fi wireless wlan wlp wlo iwlwifi rtw88 rtw89 rtl8821ce rtl88 ath10k ath11k mt7921 broadcom bcm43 brcmfmac wl driver firmware adapter airplane rfkill "no wi-fi adapter found" kernel update

## Check (read-only)
1. Is the radio switched off? `rfkill list` and `nmcli radio`
2. Does the adapter exist? `ip -br link` (look for a name starting with `wl`)
3. Which chip and driver? `lspci -nnk | grep -iA3 net` (or `lsusb` for USB adapters). No "Kernel driver in use" line means the driver is missing.
4. Driver or firmware errors? `journalctl -b -k --no-pager | grep -iE 'firmware|iwlwifi|rtw|brcm|ath1|mt79|wlan' | tail -n 30`
5. Did a kernel update just happen? `uname -r` and `ls /lib/modules`

## Causes and fixes
- **Soft-blocked (airplane mode):** `rfkill unblock wifi` or `nmcli radio wifi on`.
- **Hard-blocked:** rfkill says "Hard blocked: yes". Use the laptop's Wi-Fi switch or Fn key, or enable wireless in the BIOS/UEFI settings. No command can fix this.
- **Driver modules missing after a kernel update (Ubuntu):** usually `linux-modules-extra` didn't install for the new kernel. Get temporary internet (Ethernet or phone USB tethering, which appears as `usb0` or `enx…`) and run `sudo apt install linux-modules-extra-$(uname -r)`. Without internet: reboot, choose GRUB → *Advanced options* → the previous kernel.
- **Missing or damaged firmware** ("failed to load firmware" in the log): `sudo apt install --reinstall linux-firmware` (needs internet).
- **Driver stuck after suspend:** reload it. Find the module name from step 3, then `sudo modprobe -r iwlwifi && sudo modprobe iwlwifi` (replace `iwlwifi` with yours).
- **Broadcom chips (BCM43xx):** `sudo apt install bcmwl-kernel-source`, or run `sudo ubuntu-drivers install`.
- **Wi-Fi connects but nothing loads:** see the "No internet / websites don't load" guide.

## Undo notes
Package installs can't be reversed with /undo. Reloading a driver (`modprobe`) is harmless and is undone by a reboot.
