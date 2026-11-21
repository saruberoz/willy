# Printer stopped printing
Keywords: printer printing print queue stuck jobs paused disabled cups lpstat lp cancel cupsenable ipp driverless network printer usb printer "filter failed"

## Check (read-only)
1. Printers and their state: `lpstat -p -d` (look for "disabled" or "paused")
2. Waiting jobs: `lpstat -o`
3. Print service: `systemctl status cups --no-pager`
4. Errors: `journalctl -u cups -b --no-pager | tail -n 30`
5. USB printer seen? `lsusb`. Network printer reachable? `ping -c 3 <printer IP>`

## Causes and fixes
- **Printer disabled or paused** (after an error, CUPS pauses it): `cupsenable <printer>` and `cupsaccept <printer>`.
- **Stuck jobs block the queue**: cancel them with `cancel -a <printer>` (this deletes the waiting jobs, so they must be printed again).
- **Print service stopped**: `sudo systemctl restart cups`.
- **"Filter failed"**: driver problem. Modern printers work "driverless" (IPP Everywhere): remove the printer and add it again in Settings → Printers and choose the driverless option.
- **Network printer changed its IP address** after a router restart: remove and re-add it, or give it a fixed address in the router.
- **Out of paper, toner or ink, or a jam**: the printer's own display usually says. Software can't fix those.

## Undo notes
Cancelled jobs can't be restored; print them again. Enabling a printer is harmless.
