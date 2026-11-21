# Which firewall rule drops my packets? Counters, LOG and TRACE
Keywords: iptables nftables nft rule counters drops which rule trace log target raw table nf_log monitor trace packet path chain policy docker forward debugging firewall rules iptables-legacy iptables-nft

## Read-only first
- Rules with packet counters: `sudo iptables -L INPUT -vn --line-numbers` (or `FORWARD`, `OUTPUT`); nftables: `sudo nft list ruleset`
- Which backend? `sudo iptables -V` says `(nf_tables)` or `(legacy)`; `lsmod | grep nf_tables` loaded means nftables is in use.
- Watch counters climb while you retry the connection: run `sudo iptables -L INPUT -vn` before and after. A rule whose counter rises with each attempt is the one hit.

## Zero the counters for a clean test (changes counters only)
`sudo iptables -Z INPUT` (all rules in that chain) or `sudo iptables -Z INPUT 3` (rule 3)

## Log matching packets (adds a rule; keep it narrow)
`sudo iptables -I INPUT -p tcp --dport 443 -j LOG --log-prefix "willy-debug: "`, then read with `sudo dmesg -T | grep willy-debug`. Remove it afterwards: `sudo iptables -D INPUT -p tcp --dport 443 -j LOG --log-prefix "willy-debug: "`.

## Trace a packet through every rule
- **nftables systems (most modern distros):** add a trace flag in a test rule, then run `sudo nft monitor trace` (you watch it, then stop with Ctrl+C).
- **iptables:** load logging (`sudo modprobe nf_log_ipv4` and `sudo sysctl net.netfilter.nf_log.2=nf_log_ipv4`), then add TRACE rules in the raw table, narrowly, for example only your test port:
  `sudo iptables -t raw -I PREROUTING -p tcp --dport 443 -j TRACE` (incoming) and `sudo iptables -t raw -I OUTPUT -p tcp --sport 443 -j TRACE` (outgoing). Read with `sudo dmesg -T | grep TRACE: | tail -n 40`; each line shows table:chain:rule and the final policy.
- **Clean up:** `sudo iptables -t raw -D PREROUTING -p tcp --dport 443 -j TRACE` and the same for OUTPUT. Avoid a blanket `iptables -t raw -F` if other raw rules exist.
- No TRACE output? The system may use nftables (`nft monitor trace`), or the iptables-legacy tool must be used instead.

## Warnings
LOG and TRACE on a busy chain flood the logs; always match a specific port or address. On remote servers, test changes with a way back in (console access).

## Undo notes
/undo can't reverse firewall rules: delete each added rule with `-D` and the same arguments.
