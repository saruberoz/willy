# App blocked by a sandbox: AppArmor, Firejail, snap or flatpak confinement
Keywords: apparmor denied aa-status aa-complain aa-enforce firejail sandbox profile blacklist whitelist private snap confinement flatpak permissions app can't open files app can't access folder works without sandbox

## Is a sandbox the cause? (read-only)
1. Run the app **without** its sandbox if possible: a Firejail app as `/usr/bin/<app>`, or check whether it's a snap (`snap list | grep <app>`) or flatpak (`flatpak list | grep <app>`). Works unsandboxed = the sandbox profile blocks something.
2. AppArmor denials: `journalctl -k -b --no-pager | grep -i 'apparmor="DENIED"' | tail -n 20` (the `profile=` and `name=` fields show who was blocked from what). Status: `sudo aa-status | head -n 30`
3. Firejail: running sandboxes `firejail --list`. Log blocked access: start with `firejail --tracelog <app>` and watch `journalctl -f` (you watch, then stop with Ctrl+C). A syscall-level trace: `firejail --trace=/tmp/fj.log <app>`. Verbose: `firejail --debug <app>`.

## Fixes
- **AppArmor:** test with the profile in complain mode (logs instead of blocking): `sudo aa-complain <profile>`. If that fixes it, add the needed path to the profile's local override in `/etc/apparmor.d/local/`, reload with `sudo apparmor_parser -r /etc/apparmor.d/<profile>`, then return to enforcing: `sudo aa-enforce <profile>`.
- **Firejail:** never edit the system profile; put overrides in `~/.config/firejail/<app>.local` (for example `noblacklist ${HOME}/Documents` or `whitelist ${HOME}/Projects`). To find the blocking line, comment out half the profile's lines in a copy and test, then halve again. A starting profile for a new app: `firejail --build <app>`.
- Look inside a running Firejail sandbox: `firejail --join=<name or PID>`; copy files in or out with `firejail --put=` and `--get=`.
- **Snap:** check its permissions with `snap connections <app>`; connect a missing one, for example `sudo snap connect <app>:removable-media`.
- **Flatpak:** `flatpak info --show-permissions <app-id>`; grant a folder with `flatpak override --user --filesystem=~/Projects <app-id>`.

## Undo notes
`aa-complain` is reversed with `aa-enforce`. Remove .local overrides and flatpak overrides (`flatpak override --user --reset <app-id>`) to go back. /undo restores edited profile files.
