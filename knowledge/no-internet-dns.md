# No internet, or websites don't load although Wi-Fi or cable is connected
Keywords: internet dns resolve "temporary failure in name resolution" "could not resolve host" ping gateway route resolvectl systemd-resolved resolv.conf captive portal vpn proxy websites don't load ethernet connected no internet

## Check (read-only), in this order
1. Do we have an address and a route? `ip -br addr` and `ip route` (a `default via …` line is needed)
2. Can we reach the router? `ping -c 3 <gateway from ip route>`
3. Can we reach the internet by number? `ping -c 3 1.1.1.1`
4. Does name lookup work? `resolvectl query ubuntu.com` (or `getent hosts ubuntu.com`)
5. DNS settings: `resolvectl status | head -n 30` and `ls -l /etc/resolv.conf`
6. VPN or proxy left on? `nmcli connection show --active` and `env | grep -i proxy`

## Reading the results
- Step 1 fails (no IPv4 address or no default route): DHCP problem. Reconnect with `nmcli device disconnect <dev>` then `nmcli device connect <dev>`, or restart the router.
- Step 2 fails: the problem is between the PC and the router (wrong Wi-Fi network, weak signal, cable).
- Step 3 fails but 2 works: the router or provider has no internet. A hotel or café network may need its login page (captive portal): open a browser to `http://neverssl.com`.
- Steps 3 works but 4 fails: **DNS problem**:
  - Restart the resolver: `sudo systemctl restart systemd-resolved`
  - Use public DNS for this connection: `nmcli connection modify "<name>" ipv4.dns "1.1.1.1 9.9.9.9" ipv4.ignore-auto-dns yes`, then `nmcli connection up "<name>"` (get `<name>` from `nmcli connection show --active`).
  - On Ubuntu, `/etc/resolv.conf` should be a link to `../run/systemd/resolve/stub-resolv.conf`. A VPN tool may have replaced it.
  - Is it the DNS server or this PC? Ask a public server directly: `dig ubuntu.com @1.1.1.1 +short` (or `nslookup ubuntu.com 1.1.1.1`). That works but plain `dig ubuntu.com` fails = the configured DNS server is the problem.
  - Clear stale answers: `sudo resolvectl flush-caches`.
  - System-wide fallback DNS (not tied to one connection): set `DNS=1.1.1.1 9.9.9.9` under `[Resolve]` in `/etc/systemd/resolved.conf`, then `sudo systemctl restart systemd-resolved`.
- Everything works except one site: the site itself, or a stale entry in `/etc/hosts` (`grep -v '^#' /etc/hosts`).

## Undo notes
`nmcli connection modify` changes saved settings. To reverse: `nmcli connection modify "<name>" ipv4.dns "" ipv4.ignore-auto-dns no`.
