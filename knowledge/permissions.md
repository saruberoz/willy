# "Permission denied", can't write a file, ownership, immutable files and ACLs
Keywords: permission denied cannot write can't save file access denied chmod chown chgrp owner group rwx 755 644 600 ls -la lsattr chattr immutable append-only acl getfacl setfacl operation not permitted id groups

## Check (read-only), in this order
1. Disk full? `df -h <folder>` and `df -i <folder>` (full disks and full inodes give confusing errors)
2. Who owns it and what's allowed? `ls -la <file>` and `ls -ld <folder>`. Reading `-rw-r--r-- 1 alice staff`: the first character is the type (`-` file, `d` folder, `l` link), then three triples (rwx) for owner, group, and others.
3. Who am I, and in which groups? `id`
4. Locked with a special attribute? `lsattr <file>`: `i` = immutable (nobody, not even root, can change it), `a` = append-only
5. Extra ACL rules (a `+` at the end of the `ls -l` permissions)? `getfacl <file>`
6. On Fedora/RHEL, SELinux may block it even with correct permissions (see the SELinux guide).
7. A read-only filesystem? See the disk-errors guide.

## Permission numbers
r=4, w=2, x=1, added per triple. `644` = rw-r--r-- (normal files), `755` = rwxr-xr-x (folders and programs), `600` = rw------- (private files such as SSH keys), `700` = rwx------ (private folders).

## Fixes
- Give yourself back your own files: `sudo chown $USER:$USER <file>`. For a folder you own: `sudo chown -R $USER:$USER <your folder>`.
- Make a script runnable: `chmod u+x <script>`. Normal file permissions: `chmod 644 <file>`; folders: `chmod 755 <folder>`.
- Remove write access for others: `chmod go-w <file>`
- Remove an immutable flag (only if you know why it was set): `sudo chattr -i <file>`
- Grant one extra user access with an ACL: `setfacl -m u:<user>:rw <file>`
- Shared folder for a group: `sudo chgrp <group> <folder>` and `sudo chmod 2775 <folder>`

## Never
Don't run recursive chmod or chown on system folders (`/`, `/etc`, `/usr`, `/var`) or `chmod 777` anything; that breaks the system and security. Willy blocks the worst of these outright.

## Undo notes
/undo backs up the files' previous permissions and owners and restores them. ACL changes are removed with `setfacl -b <file>` (this removes all ACLs).
