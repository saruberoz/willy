# Looking at network traffic with tcpdump
Keywords: tcpdump packet capture pcap sniff traffic wireshark network traffic port 53 port 80 capture host analyze packets dns queries

## When to use
When the other checks (ping, DNS, ports) don't explain a network problem: is traffic leaving the PC at all, do answers come back, which DNS server is asked?

## Commands (read-only, but captures can contain private data such as passwords sent over unencrypted connections, cookies and visited sites)
- Interfaces: `ip -br link`
- A short, bounded capture: `sudo tcpdump -i <iface> -c 50 -nn` (stops after 50 packets)
- Only DNS: `sudo tcpdump -i <iface> -c 30 -nn port 53`
- Only one machine: `sudo tcpdump -i <iface> -c 50 -nn host 192.168.1.100`
- Only web: `sudo tcpdump -i <iface> -c 50 -nn port 80 or port 443`
- Save for Wireshark: `sudo tcpdump -i <iface> -c 2000 -w /tmp/capture.pcap`, then read with `tcpdump -nn -r /tmp/capture.pcap | head -n 50`
- Show contents (unencrypted traffic only): add `-A`

Always use `-c <count>` (or stop with Ctrl+C yourself): an unbounded capture never ends on its own.

## Reading it
- Requests go out but nothing comes back: blocked further along (firewall, router, server down).
- Nothing goes out: a local problem (wrong interface, route or firewall).
- DNS queries go to an unexpected server: check DNS settings (see the internet/DNS guide).

## Undo notes
Capturing changes nothing. Delete saved capture files afterwards, since they may hold private data.
