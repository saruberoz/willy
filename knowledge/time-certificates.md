# Wrong time or date, or "certificate not valid" errors everywhere
Keywords: time date clock wrong timezone ntp timedatectl "certificate is not yet valid" "certificate has expired" ssl errors https errors dual boot windows time off by hours rtc local time

## Check (read-only)
`timedatectl` shows the local time, time zone, whether NTP sync is active, and "RTC in local TZ".

## Causes and fixes
- **Clock wrong and NTP sync inactive:** `sudo timedatectl set-ntp true`. It corrects itself within a minute when online.
- **Wrong time zone** (time off by exactly whole hours): `timedatectl list-timezones | grep -i <city>`, then `sudo timedatectl set-timezone <Region/City>`.
- **Dual boot with Windows, and the time jumps by hours after using the other system:** Windows stores local time in the hardware clock and Linux stores UTC. Easiest fix on the Linux side: `sudo timedatectl set-local-rtc 1 --adjust-system-clock`. (The cleaner fix is to make Windows use UTC, which is a Windows registry setting.)
- **Certificate errors on every website:** almost always the clock. Fix the time first.
- **Clock resets to an old date after every power-off:** the motherboard's coin battery (CR2032) is flat. Replace it.

## Undo notes
Time settings are easy to change back with the same commands.
