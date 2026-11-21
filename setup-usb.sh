#!/usr/bin/env bash
# Build a Willy USB stick. Run on a Linux machine (or WSL) with internet access.
#
#   Willy only, on a stick that is already formatted (exFAT recommended):
#     bash setup-usb.sh /media/$USER/MYUSB [small|large|both]
#
#   Complete rescue stick in one go: ERASES the stick, installs the Ventoy boot
#   menu, adds the Ubuntu live system for rescue mode, then Willy:
#     sudo bash setup-usb.sh --rescue /dev/sdX [small|large|both]
#
#   Add --dry-run to either form to see every step without changing anything.
#   Add --share when the stick is for someone else: it includes the third-party
#   licences (required when giving or selling sticks).
#
#   small = small brain (~2.2 GB, needs ~4 GB free RAM, for older PCs)
#   large = large brain (~5.2 GB, needs ~7 GB free RAM, better answers)
#   both  = default; Willy picks whichever fits the PC's RAM
#
# Created by Wilson Sumanang.
set -euo pipefail

LLAMAFILE_VERSION="0.10.6"
LLAMAFILE_URL="https://github.com/mozilla-ai/llamafile/releases/download/${LLAMAFILE_VERSION}/llamafile-${LLAMAFILE_VERSION}"
LLAMAFILE_SHA256="d579f61dcd3a306f518e6d90e599d77793ed5f09543023d09c96ad35fcfa63f0"
# Brains chosen with bench/brain_bench.py on 21 Nov 2026 (see CREATOR-NOTES.md).
SMALL_URL="https://huggingface.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF/resolve/main/mistralai_Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
SMALL_SHA256="fec9d28c7f8dab7c6857d54b56c8264cce57d6f6d9003bd4110f6457f071c65a"
LARGE_URL="https://huggingface.co/bartowski/mistralai_Ministral-3-8B-Instruct-2512-GGUF/resolve/main/mistralai_Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"
LARGE_SHA256="7deb50ecb3afca928f0aa6dccdb87ed4ce4ab3991797e5fc0e0dedb92754802a"
VENTOY_VERSION="1.1.18"
VENTOY_URL="https://github.com/ventoy/Ventoy/releases/download/v${VENTOY_VERSION}/ventoy-${VENTOY_VERSION}-linux.tar.gz"
VENTOY_SHA256="d86ff9de63d94c8b8f1f6b14d23c55af4b88e8207bf2893890892a6a97b1ad54"
UBUNTU_VERSION="26.04.1"
UBUNTU_ISO="ubuntu-${UBUNTU_VERSION}-desktop-amd64.iso"
UBUNTU_BASE="https://releases.ubuntu.com/26.04"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE="${WILLY_CACHE:-${SUDO_USER:+$(getent passwd "$SUDO_USER" | cut -d: -f6)}/.cache/willy-build}"
[[ "$CACHE" == /.cache/willy-build ]] && CACHE="$HOME/.cache/willy-build"
DRY=0
SHARE=0

die() { echo "error: $*" >&2; exit 1; }
say() { echo "==> $*"; }
run() { if (( DRY )); then echo "   [dry-run] $*"; else "$@"; fi }

usage() {
  sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-1}"
}

sha_ok() {  # file expected-sha256
  [[ -z "$2" ]] && return 0
  [[ "$(sha256sum "$1" | cut -d' ' -f1)" == "$2" ]]
}

fetch() {  # url dest [sha256]
  local url="$1" dest="$2" sum="${3:-}"
  if [[ -s "$dest" ]]; then
    if sha_ok "$dest" "$sum"; then echo "   have $(basename "$dest") (checksum OK)"; return; fi
    echo "   $(basename "$dest") is damaged; downloading again"
    run rm -f "$dest"
  fi
  echo "   downloading $(basename "$dest")"
  if (( DRY )); then echo "   [dry-run] curl $url -> $dest"; return; fi
  # Partial downloads stay in .part, so rerunning the script resumes them.
  curl -fL --retry 3 -C - -o "$dest.part" "$url" || die "download failed (rerun to resume): $url"
  if ! sha_ok "$dest.part" "$sum"; then
    rm -f "$dest.part"
    die "checksum mismatch for $(basename "$dest"); the download was corrupted or changed. Rerun to retry."
  fi
  mv -f "$dest.part" "$dest"
}

install_willy() {  # usb-mount-path choice
  local usb="$1" choice="$2" dest="$1/willy"
  [[ "$choice" =~ ^(small|large|both)$ ]] || die "unknown choice '$choice' (use small, large or both)"
  run mkdir -p "$dest/bin" "$dest/models" "$dest/logs"
  local fstype
  fstype=$(findmnt -n -o FSTYPE --target "$usb" 2>/dev/null || echo unknown)
  echo "   USB filesystem: $fstype"
  if [[ "$fstype" == "vfat" && "$choice" != "small" ]]; then
    die "FAT32 can't hold files over 4 GB (the large brain). Reformat as exFAT or use 'small'."
  fi

  say "Copying Willy"
  if [[ "$(cd "$dest" 2>/dev/null && pwd -P)" != "$(cd "$SRC" && pwd -P)" ]]; then
    run cp "$SRC/willy.py" "$SRC/willy_rescue.py" "$SRC/willy_undo.py" "$SRC/willy_knowledge.py" \
           "$SRC/start.sh" "$SRC/README.md" "$SRC/guidance.md" "$dest/"
    run mkdir -p "$dest/knowledge"
    run cp "$SRC"/knowledge/*.md "$dest/knowledge/"
  fi

  say "Fetching Willy's engine"
  fetch "$LLAMAFILE_URL" "$dest/bin/willy-engine" "$LLAMAFILE_SHA256"
  say "Fetching Willy's brain(s)"
  case "$choice" in
    small) fetch "$SMALL_URL" "$dest/models/willy-small.gguf" "$SMALL_SHA256" ;;
    large) fetch "$LARGE_URL" "$dest/models/willy-large.gguf" "$LARGE_SHA256" ;;
    both)  fetch "$SMALL_URL" "$dest/models/willy-small.gguf" "$SMALL_SHA256"
           fetch "$LARGE_URL" "$dest/models/willy-large.gguf" "$LARGE_SHA256" ;;
  esac
  if (( SHARE )); then
    say "Adding third-party licences (--share)"
    run mkdir -p "$dest/licenses"
    run cp "$SRC"/licenses/* "$dest/licenses/"
    run cp "$SRC/LICENSE" "$dest/licenses/Willy-MIT-LICENSE.txt"
  fi
}

write_start_here() {  # usb-mount-path
  (( DRY )) && { echo "   [dry-run] write $1/START-HERE.txt"; return; }
  cat > "$1/START-HERE.txt" <<'TXT'
WILLY: OFFLINE AI TROUBLESHOOTER FOR LINUX
Created by Wilson Sumanang

ON A LINUX PC THAT STARTS NORMALLY
  1. Plug in this USB stick.
  2. Open a terminal (Ctrl+Alt+T).
  3. Type:   bash /media/$USER/*/willy/start.sh
  4. Describe your problem in plain words. Type ? for help.

ON A PC THAT WON'T START (RESCUE MODE)
  1. Plug in this USB stick and turn the PC on.
  2. Press the boot-menu key straight away (often F12, F11, F8 or Esc).
  3. Choose this USB stick, then the Ubuntu entry, then "Try Ubuntu".
  4. Open a terminal (Ctrl+Alt+T) and type:   bash /media/*/Ventoy/willy/start.sh
  5. Type /rescue and Willy will find the PC's own Linux and read why it failed.

Willy never runs anything without your approval.
Full guide: willy/guidance.md
TXT
}

rescue_build() {  # device choice
  local dev="$1" choice="$2"
  (( DRY )) || [[ $EUID -eq 0 ]] || die "the --rescue build needs root: sudo bash setup-usb.sh --rescue $dev"
  [[ -b "$dev" ]] || die "$dev is not a disk device (example: /dev/sdb)"
  local devtype
  devtype=$(lsblk -dno TYPE "$dev")
  if [[ "$devtype" != "disk" ]] && ! [[ "$devtype" == "loop" && "${WILLY_ALLOW_INTERNAL:-0}" == "1" ]]; then
    die "$dev is a $devtype, not a whole disk; give the whole disk (e.g. /dev/sdb, not /dev/sdb1)"
  fi
  for c in curl sha256sum tar lsblk findmnt mount umount partprobe; do
    command -v "$c" >/dev/null || die "$c is required"
  done

  # Never touch the disk this Linux is running from.
  if lsblk -nro MOUNTPOINT "$dev" | grep -qE '^(/|/boot|/boot/efi|/home|/usr|/var)$'; then
    die "$dev holds this computer's own system. Refusing to erase it."
  fi
  local rm tran
  rm=$(lsblk -dno RM "$dev" | tr -d ' ')
  tran=$(lsblk -dno TRAN "$dev" | tr -d ' ')
  if [[ "$rm" != "1" && "$tran" != "usb" && "${WILLY_ALLOW_INTERNAL:-0}" != "1" ]]; then
    die "$dev doesn't look like a USB stick (removable=$rm, connection=$tran). Refusing. Set WILLY_ALLOW_INTERNAL=1 only if you are sure."
  fi

  echo
  lsblk -o NAME,SIZE,MODEL,TRAN,LABEL,MOUNTPOINT "$dev"
  echo
  echo "!!  EVERYTHING ON $dev ($(lsblk -dno SIZE "$dev" | tr -d ' ') $(lsblk -dno MODEL "$dev" | sed 's/ *$//')) WILL BE ERASED  !!"
  if (( DRY )); then
    echo "   [dry-run] would ask you to type '$(basename "$dev")' to confirm"
  else
    read -r -p "Type the device name ($(basename "$dev")) to erase it and continue, or Enter to stop: " answer
    [[ "$answer" == "$(basename "$dev")" ]] || die "stopped; nothing was changed."
  fi

  run mkdir -p "$CACHE"
  say "Fetching Ventoy ${VENTOY_VERSION} (boot menu)"
  fetch "$VENTOY_URL" "$CACHE/ventoy-${VENTOY_VERSION}-linux.tar.gz" "$VENTOY_SHA256"
  say "Fetching Ubuntu ${UBUNTU_VERSION} (rescue system, 6 GB)"
  local ubuntu_sum=""
  if (( ! DRY )); then
    ubuntu_sum=$(curl -fsSL "$UBUNTU_BASE/SHA256SUMS" | grep " \*\?${UBUNTU_ISO}\$" | cut -d' ' -f1) \
      || die "could not get Ubuntu's official checksums"
    [[ -n "$ubuntu_sum" ]] || die "Ubuntu ${UBUNTU_VERSION} is not listed in the official checksums"
  fi
  fetch "$UBUNTU_BASE/$UBUNTU_ISO" "$CACHE/$UBUNTU_ISO" "$ubuntu_sum"

  say "Installing Ventoy on $dev (this erases it)"
  local part
  for part in $(lsblk -lnpo NAME "$dev" | tail -n +2); do
    run umount "$part" 2>/dev/null || true
  done
  run tar -xzf "$CACHE/ventoy-${VENTOY_VERSION}-linux.tar.gz" -C "$CACHE"
  if (( DRY )); then
    echo "   [dry-run] Ventoy2Disk.sh -I $dev"
  else
    # You already confirmed by typing the device name; answer Ventoy's own two prompts.
    (cd "$CACHE/ventoy-${VENTOY_VERSION}" && printf 'y\ny\n' | sh Ventoy2Disk.sh -I "$dev") \
      || die "Ventoy installation failed"
    partprobe "$dev" 2>/dev/null || true
    sleep 3
  fi

  local p1 mnt
  p1=$(lsblk -lnpo NAME "$dev" | sed -n '2p')   # first partition: Ventoy's data partition
  [[ -n "$p1" ]] || { if [[ "$dev" =~ [0-9]$ ]]; then p1="${dev}p1"; else p1="${dev}1"; fi; }
  mnt=$(mktemp -d /tmp/willy-usb.XXXXXX)
  if ! run mount "$p1" "$mnt" 2>/dev/null; then
    # Some kernels (WSL, very old distros) have no exFAT driver; try the FUSE one.
    if command -v mount.exfat-fuse >/dev/null; then
      run mount.exfat-fuse "$p1" "$mnt" || die "couldn't open the stick's exFAT partition ($p1)"
    else
      die "this system can't open exFAT drives. Install exFAT support (for example
       sudo apt install exfat-fuse) and run the same command again."
    fi
  fi
  # Make sure the stick gets unmounted even if a later step fails.
  trap 'sync; umount "'"$mnt"'" 2>/dev/null; rmdir "'"$mnt"'" 2>/dev/null' EXIT

  say "Copying the Ubuntu rescue system to the stick"
  run cp "$CACHE/$UBUNTU_ISO" "$mnt/"
  if (( ! DRY )); then
    sha_ok "$mnt/$UBUNTU_ISO" "$ubuntu_sum" || die "the Ubuntu image on the stick is damaged; try another stick"
  fi
  install_willy "$mnt" "$choice"
  write_start_here "$mnt"
  say "Finishing (writing everything to the stick)"
  run sync
  echo
  echo "Done. The stick is ready. Rescue mode: boot from it and choose Ubuntu ${UBUNTU_VERSION}."
  echo "On a running Linux PC: bash /media/\$USER/Ventoy/willy/start.sh"
}

# --- arguments -----------------------------------------------------------------
ARGS=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --share) SHARE=1 ;;
    -h|--help) usage 0 ;;
    *) ARGS+=("$a") ;;
  esac
done
set -- ${ARGS[@]+"${ARGS[@]}"}
[[ $# -ge 1 ]] || usage
command -v curl >/dev/null || die "curl is required"

if [[ "$1" == "--rescue" ]]; then
  [[ $# -ge 2 ]] || die "usage: sudo bash setup-usb.sh --rescue /dev/sdX [small|large|both]"
  rescue_build "$2" "${3:-both}"
else
  USB="$1"
  [[ -d "$USB" && -w "$USB" ]] || die "$USB is not a writable folder (is the USB mounted?)"
  install_willy "$USB" "${2:-both}"
  write_start_here "$USB"
  run sync
  echo
  echo "Done. On the PC you want to fix, plug in the USB and run:"
  echo "  bash /path/to/usb/willy/start.sh"
fi
