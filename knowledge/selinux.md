# SELinux blocks something (Fedora, RHEL, AlmaLinux, Rocky)
Keywords: selinux avc denied enforcing permissive getenforce sestatus setenforce restorecon semanage ausearch audit2allow sealert context ls -Z httpd_t http_port_t permission denied despite correct permissions fedora rhel almalinux rocky

## Is SELinux the cause? (read-only)
1. Status: `getenforce` (Enforcing, Permissive or Disabled) and `sestatus`
2. Recent denials: `sudo ausearch -m avc -ts recent`. Readable explanations with suggested fixes (setroubleshoot package): `sudo sealert -a /var/log/audit/audit.log | head -n 60`
3. Security labels on files: `ls -Z <file>`. Compare with a file that works.

## Quick test (not a fix)
`sudo setenforce 0` switches to permissive mode until reboot. If the problem disappears, SELinux was the cause. **Switch it back right away** with `sudo setenforce 1`, then fix it properly below. Never leave SELinux disabled as the "fix".

## Proper fixes
- **Wrong labels** (common after moving or copying files into a web folder): `sudo restorecon -Rv <folder>` resets labels to the system's defaults.
- **A service on a non-standard port** (for example a web server on 8080): `sudo semanage port -a -t http_port_t -p tcp 8080`
- **A feature switch exists for it** (booleans, such as letting the web server make network connections): `getsebool -a | grep httpd`, then for example `sudo setsebool -P httpd_can_network_connect on`
- **Custom policy as a last resort:** `sudo ausearch -m avc -ts recent | audit2allow -M <name>` creates a module; read the generated `<name>.te` file before installing it with `sudo semodule -i <name>.pp`, since it can allow more than you intend.

## Undo notes
`setenforce` ends at reboot. Remove a port rule with `sudo semanage port -d -t http_port_t -p tcp 8080`, a module with `sudo semodule -r <name>`, and a boolean by setting it `off`.
