# Disk is the bottleneck: high I/O wait, everything stalls
Keywords: disk io i/o wait iowait wa slow disk iostat iotop pidstat await util saturated hdd ssd scheduler bfq mq-deadline none ionice heavy disk activity inotifywait thrashing

## Check (read-only)
1. Is the CPU waiting for the disk? `vmstat 1 5`: the `wa` column. Above about 30% means the disk is holding everything up. Also check `b` (processes blocked on I/O) and `si`/`so` (swapping, which is not zero when RAM is short; see the memory guide).
2. How busy is each disk? `iostat -x 1 3` (sysstat package). In the last report: `%util` near 100 = saturated; `await` above about 20 ms on an SSD or 50 ms on a hard disk = slow.
3. Which program does the I/O? `sudo iotop -o -b -n 3` (iotop package) or `sudo pidstat -d 1 3`
4. Which files does it touch? `sudo lsof -p <PID> | grep REG | head -n 30`. To watch a folder live: `sudo inotifywait -m -r <folder>` (inotify-tools; stop with Ctrl+C, so run it yourself).
5. Is the disk failing? `sudo smartctl -H /dev/<disk>` and `journalctl -k -b --no-pager | grep -iE 'i/o error|blk_update_request|ata[0-9].*error' | tail` (see the disk-errors guide).

## Fixes
- **One program hammers the disk** (backup, indexer, update): give it idle I/O priority with `sudo ionice -c 3 -p <PID>`, or best-effort lowest priority with `sudo ionice -c 2 -n 7 -p <PID>`.
- **A service does it regularly:** `sudo systemctl edit <service>` and add `IOSchedulingClass=idle` and `Nice=19` under `[Service]` (interactive, so you type it yourself), then restart the service.
- **Swapping causes it:** fix the memory shortage (see the memory guide).
- **I/O scheduler:** `cat /sys/block/<disk>/queue/scheduler` shows the choices with the active one in brackets. Modern distros pick well: `none` or `mq-deadline` for SSD/NVMe, `bfq` for hard disks with desktop use. To try another until reboot: `echo bfq | sudo tee /sys/block/sda/queue/scheduler`.
- **A slow old hard disk:** an SSD is the real fix.

## Undo notes
ionice settings end when the program exits. Scheduler changes made with `tee` last only until reboot.
