# sudo doesn't work: "not in the sudoers file" or "parse error in /etc/sudoers"
Keywords: sudo sudoers "is not in the sudoers file" "parse error" "syntax error" visudo admin rights administrator group sudo wheel pkexec "no valid sudoers sources found"

## Check (read-only)
1. Your groups: `id` (on Ubuntu/Debian you need the `sudo` group; on Fedora/Arch, `wheel`)
2. The exact error message from `sudo -v`

## Fixes
- **"<you> is not in the sudoers file"**: an administrator must add you to the group. If no account on the PC has admin rights, use rescue mode on your own PC: `/rescue`, `/rescue repair`, then
  `sudo chroot /mnt/willy-target usermod -aG sudo <your username>` (use `wheel` on Fedora/Arch). Then `/rescue off` and restart.
- **"parse error in /etc/sudoers" or "no valid sudoers sources found"**: a typo in `/etc/sudoers` or a file in `/etc/sudoers.d/` stops sudo completely.
  - On the running system, `pkexec visudo` may still work (it asks for your password). Fix the line it shows.
  - Otherwise use rescue mode: `/rescue`, `/rescue repair`, then check with `sudo chroot /mnt/willy-target visudo -c`. It names the bad file and line. Back the file up, then fix or remove the bad line. A bad extra file in `sudoers.d` can be moved away with `sudo mv /mnt/willy-target/etc/sudoers.d/<file> /root/`.
  - Always check again with `visudo -c` before restarting.

## Undo notes
Group changes and file moves are recorded so /undo can reverse file changes. Group membership is removed with `gpasswd -d <user> sudo`.
