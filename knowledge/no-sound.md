# No sound
Keywords: no sound audio speakers headphones muted "dummy output" pipewire wireplumber pulseaudio alsa hdmi audio output volume microphone mic sof firmware

## Check (read-only)
1. Outputs and their volume: `wpctl status` (PipeWire, the default on Ubuntu 22.10 and later) or `pactl list short sinks`
2. Muted? `pactl get-sink-mute @DEFAULT_SINK@` and `pactl get-sink-volume @DEFAULT_SINK@`
3. Does the kernel see sound cards? `aplay -l` (an empty list or only "Dummy output" means a driver or firmware problem)
4. Sound services: `systemctl --user status pipewire wireplumber --no-pager` (or `pulseaudio` on older systems)
5. Errors: `journalctl -b -k --no-pager | grep -iE 'snd|sof|hda|audio' | tail -n 20`

## Causes and fixes
- **Muted or volume at 0**: `pactl set-sink-mute @DEFAULT_SINK@ 0` and `pactl set-sink-volume @DEFAULT_SINK@ 70%`.
- **Wrong output selected** (HDMI instead of speakers): get the ID from `wpctl status` and run `wpctl set-default <id>`, or pick the output in Settings → Sound.
- **Sound service crashed**: `systemctl --user restart pipewire pipewire-pulse wireplumber`. Run this as yourself, without sudo.
- **"Dummy output" only, `aplay -l` empty** (common on newer laptops): missing sound firmware. With internet: `sudo apt install --reinstall linux-firmware` (Ubuntu), or install `sof-firmware` (Fedora/Arch), then reboot. Booting the previous kernel can confirm a kernel regression.
- **Headphones not detected**: plug them in again after boot. Some laptops need the output chosen manually in Settings → Sound.

## Undo notes
Volume and output changes are harmless and easy to change back. Package installs can't be undone with /undo.
