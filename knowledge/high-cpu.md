# High CPU: one program or the whole system is busy
Keywords: high cpu 100% cpu load average busy fan noise runaway process top htop ps strace lsof renice nice ionice cpulimit kill pkill killall crypto miner xmrig cron hogging cores nproc mpstat

## Check (read-only)
1. How loaded? `uptime` and `nproc`: a load average above the core count means overloaded; twice the core count is serious.
2. Who uses the CPU? `top -b -n 1 | head -n 20` or `ps aux --sort=-%cpu | head -n 10`
3. Is it really CPU? In `top`, a high `wa` value means the CPU is waiting for the disk (see the disk I/O guide).
4. One core maxed (a single-threaded program)? `mpstat -P ALL 1 3` (sysstat package)
5. What exactly is that process? `cat /proc/<PID>/cmdline | tr '\0' ' '`, `cat /proc/<PID>/status | head -n 12`, `ls -l /proc/<PID>/exe`
6. What is it doing? `lsof -p <PID> | head -n 30`. For a short syscall summary: `sudo timeout 10 strace -c -p <PID>` (strace slows the program, so keep it brief).
7. Something unknown keeps coming back? Check scheduled jobs: `crontab -l`, `sudo crontab -l`, `ls -la /etc/cron.*`, and services: `systemctl list-unit-files --state=enabled --no-pager`.

## Fixes, gentlest first
- **Lower its priority** (keeps it running, the PC stays usable): `sudo renice -n 19 -p <PID>`. For disk-heavy work also `sudo ionice -c 3 -p <PID>`.
- **Start heavy jobs gently next time:** `nice -n 19 ionice -c 3 <command>`
- **Cap it** (cpulimit package): `cpulimit -p <PID> -l 50` limits it to half a core.
- **Stop it:** `kill <PID>` asks it to quit cleanly. Wait about 10 seconds; only if it is still running use `kill -9 <PID>`, which can lose unsaved work. `pkill -f '<part of its command>'` matches by command line, so check with `pgrep -af '<pattern>'` first.
- **A service that keeps restarting and spinning:** see the "service won't start" guide.

## Suspicious processes
Unknown names using lots of CPU, especially with random names, paths in `/tmp` or `/dev/shm`, or names like `xmrig`, may be a crypto-miner. Check `ls -l /proc/<PID>/exe` and the cron jobs above. If it looks malicious, disconnect from the network, back up your data and reinstall; cleaning an infected system is unreliable. Note that `kworker` and `ksoftirqd` are normal kernel threads.

## Undo notes
Priority changes end when the program exits. Killed programs can't be "undone", but they can be started again.
