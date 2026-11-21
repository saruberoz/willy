# Network settings: static IP, DNS servers, netplan and NetworkManager
Keywords: static ip fixed ip address netplan yaml networkd networkmanager nmcli connection modify ipv4.method manual gateway dns servers ethernet eth0 enp interface down no-carrier link detected ethtool wifi connect ssid

## Check (read-only)
1. Interfaces and link: `ip link show` (`state UP`, or `NO-CARRIER` = no cable or signal), `ip -br addr`, `ip route`
2. Cable detected? `ethtool <iface> | grep 'Link detected'`
3. Who manages the network? `nmcli general status` (NetworkManager, typical on desktops). Netplan configs (Ubuntu): `ls /etc/netplan/`
4. Saved connections: `nmcli connection show`

## NetworkManager (desktops, most laptops)
- **Static IP:** `sudo nmcli connection modify "<name>" ipv4.method manual ipv4.addresses 192.168.1.100/24 ipv4.gateway 192.168.1.1 ipv4.dns "1.1.1.1 9.9.9.9"`, then `sudo nmcli connection up "<name>"`. Back to automatic: `sudo nmcli connection modify "<name>" ipv4.method auto ipv4.addresses "" ipv4.gateway ""`.
- **Join Wi-Fi without the password ending up in shell history:** `nmcli --ask device wifi connect "<SSID>"` (it asks for the password, so you type it yourself). See networks: `nmcli device wifi list`.
- `nmcli connection up` briefly drops the connection; over SSH, be careful.

## Netplan (Ubuntu servers)
Files in `/etc/netplan/*.yaml` (two-space indentation, no tabs). A DHCP example:
```
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      nameservers:
        addresses: [1.1.1.1, 9.9.9.9]
```
- Back up first: `sudo cp /etc/netplan/<file>.yaml /root/`
- **Safest way to apply:** `sudo netplan try`. It reverts automatically after 120 seconds unless you confirm, which protects remote machines. Then `sudo netplan apply`.
- Errors: `sudo netplan generate` checks the syntax.

## Undo notes
/undo restores edited netplan files. nmcli changes are reversed by setting the old values again, or by deleting a new connection with `nmcli connection delete "<name>"`.
