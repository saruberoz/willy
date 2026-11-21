# Can't install updates: apt or dpkg errors
Keywords: apt dpkg update upgrade install error "dpkg was interrupted" "could not get lock" lock-frontend "unmet dependencies" "broken packages" "held broken packages" "NO_PUBKEY" "the following signatures couldn't be verified" "release file" 404 "sub-process /usr/bin/dpkg returned an error code" fix-broken ppa sources.list repository

## Check (read-only)
1. Read the exact error: `sudo apt update 2>&1 | tail -n 20`, or `sudo apt -s upgrade 2>&1 | tail -n 20` (`-s` only simulates)
2. Half-finished installs: `sudo dpkg --audit`
3. Is another installer running? `ps aux | grep -E '[a]pt|[d]pkg|[u]nattended'`, or exactly who holds the lock: `sudo lsof /var/lib/dpkg/lock-frontend`
4. Extra repositories: `ls /etc/apt/sources.list.d/`

## Match the error
- **"dpkg was interrupted, you must manually run 'sudo dpkg --configure -a'"**: run exactly that: `sudo dpkg --configure -a`, then `sudo apt --fix-broken install`.
- **"Could not get lock /var/lib/dpkg/lock-frontend"**: another apt (often automatic updates) is running. Wait a few minutes and re-check with step 3. **Do not delete lock files** while an apt or dpkg process exists. Only if no such process exists after a reboot is the lock stale.
- **"Unmet dependencies" / "broken packages"**: `sudo apt --fix-broken install`, then `sudo apt update && sudo apt upgrade`.
- **"held broken packages"**: usually a third-party repository (PPA) with mismatched versions. Find it with `apt-cache policy <package>`, then disable that repository (see below).
- **"NO_PUBKEY …" or "signatures couldn't be verified"**: a third-party repository's key is missing or expired. Disable that repository or reinstall its key from the vendor's official instructions.
- **"404 Not Found" / "does not have a Release file"**: the repository doesn't support this Ubuntu version (common with old PPAs after an upgrade). Disable it.
- **"Sub-process /usr/bin/dpkg returned an error code (1)"**: scroll up for the package that failed. A package's install script failed; `sudo dpkg --configure -a` often shows why.
- **Errors mention "No space left on device"**: see the "Disk full" or "/boot is full" guide.

## Disabling a repository safely
Make a backup copy first, `sudo cp /etc/apt/sources.list.d/<file> /root/<file>.bak`, then move the file out of the way: `sudo mv /etc/apt/sources.list.d/<file> /etc/apt/sources.list.d/<file>.disabled`. Then run `sudo apt update`.

## Undo notes
Moving a sources file is undoable with /undo. Package installs and removals are not.
