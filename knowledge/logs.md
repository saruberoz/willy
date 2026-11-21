# Reading logs: journalctl, dmesg and log files
Keywords: logs log files where are the logs read logs reading log files journalctl dmesg syslog messages auth.log secure kern.log where are the logs error messages previous boot crash follow log tail grep zgrep since until priority err

## systemd journal (all modern distros)
- Errors from this boot: `journalctl -b -p err --no-pager`
- The **previous** boot (after a crash or freeze): `journalctl -b -1 -p warning --no-pager | tail -n 50`; list boots with `journalctl --list-boots`
- One service: `journalctl -u <service> -n 100 --no-pager`; since a time: `--since "1 hour ago"` or `--since "2026-01-01 10:00" --until "2026-01-01 11:00"`
- One process: `journalctl _PID=<PID> --no-pager`
- Kernel messages: `journalctl -k -b --no-pager | tail -n 50`
- Last messages with explanations: `journalctl -xe --no-pager | tail -n 60`
- Follow live (you watch, then stop with Ctrl+C): `journalctl -f`
- Journal size: `journalctl --disk-usage` (to shrink it, see the "Disk full" guide)

## Kernel ring buffer
`sudo dmesg -T | tail -n 50` (human-readable times); just problems: `sudo dmesg -T --level=err,warn | tail -n 30`

## Classic log files
| What | Debian / Ubuntu | Fedora / RHEL / Alma |
|------|-----------------|----------------------|
| General | /var/log/syslog | /var/log/messages |
| Logins, sudo, SSH | /var/log/auth.log | /var/log/secure |
| Kernel | /var/log/kern.log | `journalctl -k` |
| Cron | /var/log/syslog | /var/log/cron |
| Apache | /var/log/apache2/ | /var/log/httpd/ |
| Nginx | /var/log/nginx/ | /var/log/nginx/ |
| MySQL / MariaDB | /var/log/mysql/ | /var/log/mariadb/ |
| PostgreSQL | /var/log/postgresql/ | /var/lib/pgsql/data/log/ |
| Packages | /var/log/apt/history.log, /var/log/dpkg.log | /var/log/dnf.log |

## Searching
- Recent problems: `grep -iE 'error|fail|warn' /var/log/syslog | tail -n 50`
- With surrounding lines: `grep -B 5 -A 5 -i 'fatal' <log>`
- Rotated, compressed logs: `zgrep -i error /var/log/syslog.2.gz`

## Undo notes
Reading logs changes nothing.
