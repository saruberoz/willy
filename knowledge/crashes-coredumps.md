# A program crashes: segmentation fault, core dumps, gdb backtraces
Keywords: crash crashes segfault segmentation fault core dumped core dump coredumpctl gdb backtrace bt abort signal sigsegv sigabrt debug symbols debuginfod valgrind memory leak program closes suddenly

## Find the crash (read-only)
1. Recent crashes: `coredumpctl list --no-pager | tail -n 10` (time, PID, signal, program)
2. Details and a short stack trace: `coredumpctl info <PID> --no-pager | head -n 60`
3. Kernel's view: `journalctl -k -b --no-pager | grep -iE 'segfault|general protection|traps:' | tail`
4. Are dumps enabled? `cat /proc/sys/kernel/core_pattern` (a pipe to systemd-coredump is typical) and `ulimit -c` (0 = off for this shell)

## Read the backtrace
- Open the crash in gdb: `coredumpctl debug <PID>`, then type `bt` (interactive, so you run it yourself). The top frames show where it died.
- **Missing function names** ("??") mean no debug symbols. Many distros fetch them on demand: `export DEBUGINFOD_URLS="https://debuginfod.ubuntu.com"` (Fedora: `https://debuginfod.fedoraproject.org`) before running gdb. Needs internet.
- Check whether a program has symbols: `file $(which <program>)` says "stripped" or "with debug_info".
- Export the dump to share with developers: `coredumpctl dump <PID> --output /tmp/<program>.core`

## Common causes and what to do
- Crashes right after an update: a library mismatch or regression. Check `tail -n 40 /var/log/apt/history.log`; try the previous version or wait for a fix.
- Crashes only with one file, plugin or setting: move the program's config folder aside (`mv ~/.config/<program> ~/.config/<program>.bak`) and test with defaults.
- Out of memory looks like a crash too: check the memory guide (`killed process` in the log).
- Your own program: build with `-g` (`-ggdb3` for most detail), and look for memory errors with `valgrind --leak-check=full --track-origins=yes ./<program>` (very slow).
- Trace what it did just before dying: `strace -f -o /tmp/trace.txt <program>`, then `tail -n 30 /tmp/trace.txt`.

## Privacy
Core dumps contain the program's memory: possibly passwords, keys and documents. Share them only with people you trust, and delete them afterwards (`/var/lib/systemd/coredump/`).

## Undo notes
Reading crashes changes nothing. Moving a config folder aside is reversed by moving it back, and /undo can do that.
