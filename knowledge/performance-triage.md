# Performance triage: the first 60 seconds on a slow machine
Keywords: performance triage slow server first minute checklist uptime vmstat mpstat pidstat iostat sar free load saturation bottleneck sysstat retransmits throughput interface usage

Run these in order; each takes a few seconds. Most need the `sysstat` package (`mpstat`, `pidstat`, `iostat`, `sar`).

1. `uptime`: load averages for 1, 5 and 15 minutes. Rising (1-minute much higher than 15) means it's getting worse right now; compare with `nproc`.
2. `sudo dmesg -T | tail -n 20`: out-of-memory kills, disk I/O errors, "possible SYN flooding" network warnings.
3. `vmstat -w 1 5`:
   - `r` above the CPU count: CPU saturated (processes queue for a CPU).
   - `si`/`so` not zero: swapping (memory shortage).
   - `wa` high and sustained: waiting for disk.
   - `sy` above about 20%: lots of kernel work (system calls, I/O, interrupts), worth a closer look.
4. `mpstat -P ALL 1 3`: one CPU at 100% while others idle means a single-threaded program is the limit.
5. `pidstat 1 5`: which processes use CPU, per second (%CPU adds up across cores, so 400% = four cores).
6. `iostat -xz 1 3`: per disk: `%util` above about 60% starts to hurt and near 100% is saturated; high `await` (ms) means requests queue or the device is struggling.
7. `free -h`: the `available` column is what programs can still use without swapping.
8. `sar -n DEV 1 3`: network traffic per interface. Is a link at its limit (for example about 110 MB/s on gigabit)?
9. `sar -n TCP,ETCP 1 3`: `active/s` new outgoing connections, `passive/s` incoming, **`retrans/s` retransmissions**: a bad network or an overloaded server.

## Then
Follow what stood out: the high-CPU, memory, disk I/O or network guides. Fix the biggest bottleneck first, then measure again.

## Undo notes
All of these are read-only and light enough to run on a busy machine.
