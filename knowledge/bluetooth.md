# Bluetooth won't turn on or a device won't connect
Keywords: bluetooth headphones earbuds speaker mouse keyboard pair pairing connect "no bluetooth adapter found" bluetoothctl rfkill btusb hci0 a2dp

## Check (read-only)
1. Adapter present and powered? `bluetoothctl show`
2. Blocked? `rfkill list bluetooth`
3. Service running? `systemctl status bluetooth --no-pager`
4. Known devices: `bluetoothctl devices`
5. Errors: `journalctl -b --no-pager | grep -iE 'bluetooth|btusb|hci0' | tail -n 20`

## Causes and fixes
- **Blocked**: `rfkill unblock bluetooth`.
- **Adapter off**: `bluetoothctl power on`.
- **Service stopped or stuck**: `sudo systemctl restart bluetooth`.
- **"No Bluetooth adapter found"** and nothing in `bluetoothctl show`: the driver failed. Reload it with `sudo modprobe -r btusb && sudo modprobe btusb`, or reboot. Check that the adapter isn't disabled in the BIOS.
- **Device pairs but won't connect, or connects without sound**: forget it and pair again. `bluetoothctl remove <MAC>` (MAC from `bluetoothctl devices`), put the device in pairing mode, then pair from Settings → Bluetooth. Pairing is interactive, so you do that part yourself.
- **Headphones connect but no sound**: choose them as the output in Settings → Sound, or use `wpctl status` and `wpctl set-default <id>`.

## Undo notes
`bluetoothctl remove` forgets a device; you can pair it again. No files change.
