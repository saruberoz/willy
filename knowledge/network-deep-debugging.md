# Deep network debugging: dropped connections, timeouts, retransmits
Keywords: connection timeout hangs syn syn-ack rst reset icmp unreachable dropped packets retransmits retransmission handshake tcpdump filter mtr tcp traceroute port 443 firewall drops where source port local port range ss syn-sent docker container network netshoot

## Which phase of the connection fails? (read-only captures)
Always bound captures with `-c`, and avoid capturing on a busy link for long.
- Only new connection attempts: `sudo tcpdump -ni any -c 30 'tcp[tcpflags] == tcp-syn'`. The same SYN repeating with no answer means packets are dropped somewhere.
- Attempts and their answers: `sudo tcpdump -ni any -c 50 'tcp[tcpflags] == tcp-syn or tcp[13] == 18'` (18 = SYN-ACK = the server accepted)
- Refused: `sudo tcpdump -ni any -c 50 'tcp[tcpflags] == tcp-syn or tcp[13] & 4 != 0'`. A RST answer means nothing listens on that port.
- Rejected by a firewall: `sudo tcpdump -ni any -c 50 'tcp[tcpflags] == tcp-syn or icmp[0] == 3'` (ICMP "unreachable")

## Make your own test traffic easy to find
Outgoing connections normally use a random source port from `cat /proc/sys/net/ipv4/ip_local_port_range`. Pick one below that range so your packets stand out:
- `curl --local-port 2001 -v http://<server>:<port>/` or `nc -v -p 2000 <server> <port>`
- Then capture only those: `sudo tcpdump -ni any -c 50 portrange 2000-3000`

## Other checks
- Where along the path TCP to a port is blocked: `sudo mtr --tcp -P 443 -rw -c 10 <server>`
- Retransmissions (lossy network or overloaded peer): `sar -n ETCP 1 5`, the `retrans/s` column
- Which program waits on a connection that never completes: `ss -tpn state syn-sent`
- Which program connects where: `ss -tanp`
- Inside a Docker container's network (same addresses, same traffic): `docker run --rm -it --network container:<name> nicolaka/netshoot` gives a shell with tcpdump, dig and more (downloads an image, so it needs internet).

## Capturing on a remote server
Save to a private file with `sudo tcpdump -ni any -c 2000 -w /root/capture.pcap port 53`, copy it back and open it in Wireshark. Experts can also stream a capture over SSH straight into Wireshark (`ssh server 'sudo tcpdump -ni any -U -w - port 53' | wireshark -k -i -`), which you run yourself.

## Undo notes
Captures change nothing, but they can contain private data: delete capture files when you're done.
