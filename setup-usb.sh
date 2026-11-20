#!/usr/bin/env bash
# Build a Willy USB stick. Run on any Linux machine with internet access.
# Usage:  bash setup-usb.sh /media/$USER/MYUSB [small|large|both]
#   small = 3B model (~2 GB, needs ~4 GB free RAM, fast on old PCs)
#   large = 7B model (~4.7 GB, needs ~7 GB free RAM, smarter)
#   both  = default; start.sh picks whichever fits the PC's RAM
set -euo pipefail

LLAMAFILE_VERSION="${LLAMAFILE_VERSION:-0.9.3}"
LLAMAFILE_URL="https://github.com/Mozilla-Ocho/llamafile/releases/download/${LLAMAFILE_VERSION}/llamafile-${LLAMAFILE_VERSION}"
SMALL_URL="https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
LARGE_URL="https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

die() { echo "error: $*" >&2; exit 1; }

[[ $# -ge 1 ]] || die "usage: bash setup-usb.sh <usb-mount-path> [small|large|both]"
USB="$1"; CHOICE="${2:-both}"
[[ -d "$USB" && -w "$USB" ]] || die "$USB is not a writable directory (is the USB mounted?)"
command -v curl >/dev/null || die "curl is required"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$USB/willy"
mkdir -p "$DEST/bin" "$DEST/models" "$DEST/logs"

fstype=$(findmnt -n -o FSTYPE --target "$USB" 2>/dev/null || echo unknown)
echo "USB filesystem: $fstype"
if [[ "$fstype" == "vfat" ]]; then
  echo "warning: FAT32 cannot hold files over 4 GB, so the 7B model will fail." >&2
  echo "         Reformat as exFAT (works on Linux, Windows and macOS) or use 'small'." >&2
  [[ "$CHOICE" == "small" ]] || die "aborting; rerun with 'small' or reformat as exFAT"
fi

fetch() {  # url dest
  if [[ -s "$2" ]]; then
    echo "  already have $(basename "$2")"
    return
  fi
  echo "  downloading $(basename "$2")"
  # Partial downloads stay in .part, so rerunning the script resumes them.
  curl -fL --retry 3 -C - -o "$2.part" "$1" || die "download failed (rerun to resume): $1"
  mv -f "$2.part" "$2"
}

echo "Copying scripts..."
if [[ "$(cd "$DEST" && pwd -P)" != "$(cd "$SRC" && pwd -P)" ]]; then
  cp "$SRC/willy.py" "$SRC/start.sh" "$SRC/README.md" "$SRC/guidance.md" "$DEST/"
fi

echo "Fetching engine (llamafile ${LLAMAFILE_VERSION})..."
fetch "$LLAMAFILE_URL" "$DEST/bin/willy-engine"

echo "Fetching model(s)..."
case "$CHOICE" in
  small) fetch "$SMALL_URL" "$DEST/models/willy-small.gguf" ;;
  large) fetch "$LARGE_URL" "$DEST/models/willy-large.gguf" ;;
  both)  fetch "$SMALL_URL" "$DEST/models/willy-small.gguf"
         fetch "$LARGE_URL" "$DEST/models/willy-large.gguf" ;;
  *) die "unknown choice '$CHOICE' (use small, large or both)" ;;
esac

sync
echo
echo "Done. On the PC you want to fix, plug in the USB and run:"
echo "  bash /path/to/usb/willy/start.sh"
