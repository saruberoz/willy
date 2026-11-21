# Packages on Fedora, RHEL, AlmaLinux and Rocky (dnf, rpm), and which package owns a file
Keywords: dnf yum rpm fedora rhel almalinux rocky centos install remove update upgrade clean which package owns file dpkg -S rpm -qf dnf provides apt-cache policy package version history rollback

## Which package owns a file, and what's in a package (read-only)
- Debian/Ubuntu: `dpkg -S /usr/bin/<program>`; files in a package: `dpkg -L <package>`; details: `apt show <package>`; installed vs available version: `apt-cache policy <package>`
- Fedora/RHEL: `rpm -qf /usr/bin/<program>`; files: `rpm -ql <package>`; which package *would* provide a file: `dnf provides /usr/bin/<program>`

## dnf basics (Fedora/RHEL)
- Install / remove: `sudo dnf install <package>`, `sudo dnf remove <package>`
- Update everything: `sudo dnf upgrade --refresh`
- Clean the download cache (frees space, harmless): `sudo dnf clean all`
- Recent transactions: `sudo dnf history`; details of one: `sudo dnf history info <id>`
- **Undo a bad update:** `sudo dnf history undo <id>`, or `sudo dnf downgrade <package>`. Check what it will do before confirming.
- Broken or duplicate packages after an interrupted update: `sudo dnf distro-sync` and `sudo dnf check`

## Common dnf errors
- "Error: Failed to download metadata for repo": network problem, or a third-party repo is down. Check with `dnf repolist`, and disable a broken repo temporarily with `--disablerepo=<id>`.
- "GPG check FAILED": the repository's key is missing. Import it only from the vendor's official instructions.
- "Problem: conflicting requests" / "nothing provides": a third-party repo for a different Fedora version. Remove or update that repo.

## Undo notes
/undo can't reverse package changes. On Fedora/RHEL, `dnf history undo` is the way back. On Debian/Ubuntu see the apt guide.
