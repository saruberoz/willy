# Login loop: the password is accepted but you're sent back to the login screen
Keywords: login loop can't log in back to login screen gdm lightdm sddm session crashes desktop won't start xauthority iceauthority home permissions disk full gnome extensions tty ctrl+alt+f3

## Get a text login first
Press **Ctrl+Alt+F3**, log in with your username and password, and start Willy there: `bash /media/$USER/*/willy/start.sh`. Ctrl+Alt+F1 or F2 goes back to the login screen.

## Check (read-only)
1. Out of space? `df -h / /home` (the most common cause)
2. Files in your home owned by root? `ls -la ~ | grep -E 'Xauthority|ICEauthority|\.config|\.cache|\.local'`, then `find ~ -maxdepth 2 -user root 2>/dev/null | head`
3. Why the session ended: `journalctl -b --no-pager -p warning | grep -iE 'gdm|gnome-shell|session|xorg|wayland' | tail -n 30`
4. Home folder ownership: `ls -ld ~`

## Fixes
- **No space left:** free some (see the space clean-up guide), then log in again.
- **Files owned by root** (often after running a graphical app with `sudo`): `sudo chown $USER:$USER ~/.Xauthority ~/.ICEauthority`. For whole folders: `sudo chown -R $USER:$USER ~/.config ~/.cache ~/.local`.
- **A GNOME extension crashes the shell:** turn them all off with `gsettings set org.gnome.shell disable-user-extensions true`, log in, then re-enable them one by one.
- **Graphics driver problem:** try the other session type on the login screen (the gear icon: "Ubuntu on Xorg" or Wayland). Otherwise see the graphics guide.

## Undo notes
Ownership changes are restored with /undo, which backs up the files' permissions first. The extension setting is reversed with `gsettings set org.gnome.shell disable-user-extensions false`.
