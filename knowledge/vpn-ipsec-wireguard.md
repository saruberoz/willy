# VPN won't connect or passes no traffic: IPsec, WireGuard, OpenVPN
Keywords: vpn ipsec strongswan swanctl racoon setkey xfrm ike esp udp 500 4500 nat-t phase 1 phase 2 security association sa wireguard wg handshake openvpn tunnel up but no traffic masquerade nat

## Check (read-only)
1. Do packets reach the other end and come back? `sudo tcpdump -ni any -c 40 host <vpn peer address>`
   - IPsec uses UDP 500 (IKE, the key exchange) and UDP 4500 or ESP (the data). WireGuard uses one UDP port (often 51820). OpenVPN usually UDP 1194 or TCP 443.
   - Requests leave but nothing returns: a firewall or NAT on the way, or the peer is down.
2. **IPsec**, phase 1 (IKE) then phase 2 (the tunnel):
   - strongSwan (modern): `sudo swanctl --list-sas` (or `sudo ipsec statusall` on older setups); established and installed SAs mean both phases worked.
   - racoon (legacy): `sudo racoonctl show-sa esp`, looking for `state=mature`.
   - Kernel view: `sudo ip xfrm policy` (which traffic should go through the tunnel) and `sudo ip xfrm state` (active tunnels with byte counters). **`ip xfrm state` can print secret keys**, so don't share its full output.
   - Many tunnels come up only when traffic flows: `ping -I <local inside address> <remote inside address>`
   - Logs: `journalctl -u strongswan --since "10 min ago" --no-pager` (or `charon`, `ipsec`, `racoon` in `/var/log/syslog`). Raise the log level temporarily for detail.
3. **WireGuard:** `sudo wg show`. A recent "latest handshake" means the tunnel works; none means keys, endpoint or firewall are wrong. Check `allowed ips` covers the traffic you send.
4. **OpenVPN:** `journalctl -u openvpn* --no-pager | tail -n 40`; look for TLS errors, auth failures or "route" problems.

## Common causes
- **Tunnel up but no traffic:** a NAT/masquerade rule rewrites tunnel traffic before IPsec sees it. Check `sudo iptables -t nat -L POSTROUTING -vn` and exempt the tunnel networks from masquerading. Also check `ip route` sends that traffic the right way, and that IP forwarding is on for gateways: `sysctl net.ipv4.ip_forward`.
- **Phase 1 fails:** mismatched pre-shared key, certificate or proposals (encryption and hash algorithms) between the two ends. Compare both configs; some old implementations handle SHA-256 badly, so test another hash if both sides allow it.
- **Firewall:** allow UDP 500 and 4500 and ESP (IPsec), or the WireGuard/OpenVPN port, on both ends.
- **Time wrong:** certificate-based VPNs fail with a bad clock (see the time guide).

## Undo notes
All checks are read-only. Config changes on VPN gateways should be backed up first; /undo restores edited files.
