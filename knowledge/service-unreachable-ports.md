# Can't reach a server, website or port; what is using a port?
Keywords: can't connect connection refused connection timed out port open closed listening ss netstat lsof fuser nc netcat telnet curl traceroute mtr nmap unreachable server ssh port 22 80 443 3306 5432 remote service

## Check (read-only), from the outside in
1. Can we reach the machine? `ping -c 3 <server>`. If the IP works but the name doesn't, it's DNS (see the internet/DNS guide).
2. Is the port open from here? `nc -zv <server> <port>` (TCP; add `-u` for UDP), or `curl -v http://<server>:<port>/`
   - **"Connection refused"**: the machine answered, but nothing listens on that port, or a firewall rejects it.
   - **"Timed out"**: a firewall silently drops it, or there's a routing problem.
3. Where does the path break? `traceroute <server>` or `mtr -rw <server>` (mtr gives a report with per-hop loss).
4. **On the server itself**, is the program listening, and on which address? `sudo ss -tulnp` (TCP and UDP listening sockets with the program). For one port: `sudo ss -tlnp 'sport = :<port>'`, `sudo lsof -i :<port>` or `sudo fuser -v <port>/tcp`.
   - Listening on `127.0.0.1` only means it accepts local connections only; change the program's listen/bind address to reach it from other machines.
5. Is the service running at all? `systemctl status <service> --no-pager`
6. Firewall on the server: see the firewall guide.
7. Port scanning: `nmap -p 22,80,443 <server>` shows which ports are open. **Only scan machines you own or are allowed to test.**

## Fixes
- Not listening: start or fix the service (see the "service won't start" guide).
- Listening only on localhost: change the bind address in its config, then restart it.
- Port taken by another program: stop or reconfigure that program, or move one of them to a different port.
- Firewall blocks it: open the port (firewall guide).

## Undo notes
All the checks here are read-only. Config and firewall changes have their own undo notes.
