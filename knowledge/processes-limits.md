# Investigating a process, and "Too many open files"
Keywords: "too many open files" emfile many open files open file limit process pid pgrep pidof pstree /proc status cmdline environ fd file descriptors lsof fuser ulimit limits nofile nproc limitnofile limits.conf which process uses file parent process zombie

## Find and identify a process (read-only)
- By name: `pgrep -a <name>` or `pidof <name>`
- Its family tree: `pstree -p <PID>`; the whole system: `pstree -p | head -n 40`
- What it is: `cat /proc/<PID>/cmdline | tr '\0' ' '`, `cat /proc/<PID>/status | head -n 15`, `ls -l /proc/<PID>/exe /proc/<PID>/cwd`
- Its environment: `sudo cat /proc/<PID>/environ | tr '\0' '\n'`. **This can show passwords and tokens**, so share the output carefully.
- Files and sockets it has open: `sudo lsof -p <PID> | head -n 40`; count them: `sudo ls /proc/<PID>/fd | wc -l`
- Who uses a file? `sudo lsof <file>` or `sudo fuser -v <file>`. Who uses a folder or mount? `sudo lsof +D <folder>` (slow on big folders) or `sudo fuser -vm <mountpoint>`.
- Zombie processes (`Z` in `ps aux`) are already dead; they disappear when their parent (`ps -o ppid= -p <PID>`) collects them or exits.

## "Too many open files" (EMFILE)
1. The process's limit: `grep 'open files' /proc/<PID>/limits`, compared with the count from `ls /proc/<PID>/fd | wc -l`
2. For a service: `systemctl show <service> -p LimitNOFILE`
3. If the count keeps growing, the program leaks file handles. Restarting helps for now; report it upstream.
4. Raise the limit for a **service**: `sudo systemctl edit <service>`, add `LimitNOFILE=65536` under `[Service]` (interactive, so you type it yourself), then `sudo systemctl restart <service>`.
5. Raise it for **login sessions**: add lines like `<user> soft nofile 65536` and `<user> hard nofile 65536` to `/etc/security/limits.conf` (back it up first), then log out and back in. Check with `ulimit -n`.

## Undo notes
/undo restores limits.conf. Remove a systemd override with `sudo systemctl revert <service>`.
