# Out of memory, memory leaks, and swap
Keywords: memory ram oom out of memory oom-killer "killed process" programs getting killed apps killed out of memory killed memory leak rss swap swappiness swapfile swapon swapoff drop_caches free available pmap smaps oom_score_adj memorymax low memory

## Check (read-only)
1. `free -h`: the **available** column matters, not "free" (Linux uses spare RAM as cache on purpose). Swap that is mostly used means memory pressure.
2. Biggest users: `ps aux --sort=-%mem | head -n 15`
3. Did the kernel kill something? `journalctl -k -b --no-pager | grep -iE 'out of memory|killed process|oom' | tail -n 20` (older boots: add `-b -1`)
4. A leak? Watch one process: `ps -p <PID> -o pid,rss,vsz,etime,cmd` a few minutes apart; an RSS that only ever grows suggests a leak. Details: `sudo pmap -x <PID> | tail -n 3`
5. Swap: `swapon --show` and `cat /proc/sys/vm/swappiness` (default 60; lower prefers RAM)

## Fixes
- **One leaking program:** restart it. For a service: `sudo systemctl restart <service>`. Report the leak to its developers.
- **Too little RAM for the workload:** close programs (browsers with many tabs are the usual cause), or add swap as a safety net:
  1. `sudo fallocate -l 4G /swapfile`
  2. `sudo chmod 600 /swapfile`
  3. `sudo mkswap /swapfile`
  4. `sudo swapon /swapfile`
  5. To keep it after reboot, back up fstab (`sudo cp /etc/fstab /etc/fstab.bak`), then add the line `/swapfile none swap sw 0 0` with `echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab`. A wrong fstab line can stop the PC from booting, so check with `sudo findmnt --verify`.
- **Use RAM before swap:** `sudo sysctl vm.swappiness=10` (until reboot). To keep it: `echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf`.
- **Protect an important service from the OOM killer, or cap a greedy one:** `sudo systemctl edit <service>` and add `OOMScoreAdjust=-500` or `MemoryMax=2G` under `[Service]`, then restart it. This is interactive, so you type it yourself.
- **Pull swapped-out memory back into RAM** (only when `free -h` shows enough available RAM): `sudo swapoff -a && sudo swapon -a`. The PC may freeze for a while.

## Myths
Dropping caches (`echo 3 | sudo tee /proc/sys/vm/drop_caches`) only makes "free" look bigger; it doesn't fix memory problems and makes the PC slower until the cache refills. Use it only for testing.

## Undo notes
swappiness changes are undone with the same command and the old value (usually 60). /undo can restore fstab and sysctl files it backed up. Remove a swap file with `sudo swapoff /swapfile`, then delete it.
