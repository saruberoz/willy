# Firewall: which one is active, and opening or closing a port
Keywords: firewall ufw firewalld firewall-cmd iptables nftables nft open port allow port blocked port rule reject drop ssh lockout zone

## Check (read-only): which firewall is in charge?
- Ubuntu/Debian usually use **ufw**: `sudo ufw status verbose`
- Fedora/RHEL/AlmaLinux use **firewalld**: `sudo firewall-cmd --state` and `sudo firewall-cmd --list-all`
- The rules underneath: `sudo nft list ruleset | head -n 60` (modern) or `sudo iptables -L -n -v` (older)
Use only the tool that matches the active firewall; mixing them causes confusion.

## Open a port
- **ufw:** `sudo ufw allow 80/tcp`. Only from your local network: `sudo ufw allow from 192.168.1.0/24 to any port 22`. Rules in order: `sudo ufw status numbered`.
- **firewalld:** by service `sudo firewall-cmd --permanent --add-service=http`, or by port `sudo firewall-cmd --permanent --add-port=8080/tcp`, then `sudo firewall-cmd --reload`.
- **Plain iptables:** `sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT`. These rules are lost at reboot unless saved, for example with `sudo iptables-save | sudo tee /etc/iptables/rules.v4` (the iptables-persistent package loads that file at boot).

## Close a port
- ufw: `sudo ufw delete allow 80/tcp`. firewalld: `--remove-service` or `--remove-port`, then `--reload`.

## Warnings
- **Turning a firewall on over SSH can lock you out.** Allow SSH first (`sudo ufw allow OpenSSH`), then `sudo ufw enable`.
- Flushing all rules (`sudo iptables -F`) with a DROP default policy cuts every connection, including your SSH session. Don't do it remotely.
- A firewall is rarely why a *desktop* can't browse the web; check the network and DNS guides first.

## Undo notes
/undo can't reverse firewall rules. Remove a rule with the matching delete or remove command shown above.
