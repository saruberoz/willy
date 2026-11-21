# PC is slow, freezes, or programs get killed (out of memory)
Keywords: pc computer laptop really slow everything slow performance sluggish lag freeze freezes hangs fan hot overheating thermal throttling tracker baloo snapd old pc slow desktop

## Check (read-only)
1. What's busy right now? `top -b -n 1 | head -n 20`
2. Memory and swap: `free -h` (low "available" plus heavy swap use means memory pressure)
3. Biggest memory users: `ps -eo pid,comm,%cpu,%mem --sort=-%mem | head -n 12`
4. Did the kernel kill programs for lack of memory? `journalctl -k -b --no-pager | grep -iE 'out of memory|oom-kill|killed process' | tail`
5. Is the disk the bottleneck? `vmstat 1 5` (a high `wa` column means waiting for disk)
6. Overheating? `cat /sys/class/thermal/thermal_zone*/temp` (values are in thousandths of °C; above about 90000 is hot)
7. Disk nearly full? `df -h /` (a full disk makes everything slow)

## Common causes and fixes
- **One program using lots of CPU or memory**: close it normally. If it is stuck, `kill <pid>`; use `kill -9 <pid>` only if it ignores that.
- **Browser with many tabs**: the most common cause of memory pressure on 4–8 GB PCs. Close tabs, or use the browser's task manager (Shift+Esc in Chrome-based browsers).
- **File indexers** (`tracker-miner-fs`, `baloo_file`) busy after a big copy usually settle down within hours.
- **No or tiny swap on a low-RAM PC**: check `swapon --show`. Adding a swap file (for example 4 GB at `/swapfile`) helps avoid out-of-memory kills.
- **Overheating**: clean the fans and vents. Laptops on soft surfaces block airflow.
- **Slow old hard disk (HDD)**: high `wa` in vmstat. An SSD upgrade is the real fix. Also check disk health (see the disk-errors guide).

## Undo notes
Stopping a program can't be undone, but it can simply be started again.
