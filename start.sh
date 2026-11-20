#!/usr/bin/env bash
# Start Willy from the USB stick: launch the local model server, then the assistant.
# Usage:  bash /path/to/usb/willy/start.sh ["optional problem description"]
# Env overrides: WILLY_MODEL=/path/model.gguf  WILLY_PORT=8080  WILLY_CTX=8192  WILLY_THREADS=N
set -euo pipefail

USB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${WILLY_PORT:-8080}"
CTX="${WILLY_CTX:-8192}"
API="http://127.0.0.1:${PORT}/v1/chat/completions"

die() { echo "error: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 is required (it ships with almost every Linux distro)."
[[ -f "$USB_DIR/bin/willy-engine" ]] || die "missing $USB_DIR/bin/willy-engine. Run setup-usb.sh first."

# Pick a model: WILLY_MODEL if set, else the largest model that fits in RAM.
MODEL="${WILLY_MODEL:-}"
if [[ -z "$MODEL" ]]; then
  mem_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  # Leave ~1.5 GB headroom for the context and the system.
  budget=$(( mem_kb * 1024 - 1610612736 ))
  best=""; best_size=0
  for f in "$USB_DIR"/models/*.gguf; do
    [[ -e "$f" ]] || continue
    size=$(stat -c %s "$f")
    if (( size < budget && size > best_size )); then best="$f"; best_size=$size; fi
  done
  if [[ -z "$best" ]]; then
    # Nothing fits comfortably: fall back to the smallest model and hope for swap.
    best=$(ls -1rS "$USB_DIR"/models/*.gguf 2>/dev/null | head -n 1 || true)
    [[ -n "$best" ]] && echo "warning: low free RAM; using the smallest model, it may be slow." >&2
  fi
  MODEL="$best"
fi
[[ -n "$MODEL" && -f "$MODEL" ]] || die "no .gguf model found in $USB_DIR/models"

health() {
  python3 - "$PORT" <<'PY'
import sys, urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:%s/health" % sys.argv[1], timeout=2)
except Exception:
    sys.exit(1)
PY
}

SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" 2>/dev/null || true; fi
  if [[ -n "${RUN_DIR:-}" ]]; then rm -rf "$RUN_DIR"; fi
}
trap cleanup EXIT

if health; then
  echo "Model server already running on port $PORT, reusing it."
else
  # USB sticks are often mounted noexec, so copy the binary somewhere executable.
  RUNNER=()
  for base in "${XDG_RUNTIME_DIR:-}" /tmp /dev/shm "$HOME/.cache"; do
    [[ -n "$base" && -d "$base" && -w "$base" ]] || continue
    RUN_DIR=$(mktemp -d "$base/willy.XXXXXX")
    cp "$USB_DIR/bin/willy-engine" "$RUN_DIR/willy-engine"
    chmod +x "$RUN_DIR/willy-engine"
    # willy-engine is also a valid Windows .exe. On WSL (and some systems with WINE)
    # a binfmt handler hands it to Windows, which can't see Linux paths.
    # Starting it through `sh` forces the native Linux route.
    if grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null \
       || [[ -e /proc/sys/fs/binfmt_misc/WSLInterop || -e /proc/sys/fs/binfmt_misc/wine ]]; then
      if sh "$RUN_DIR/willy-engine" --version >/dev/null 2>&1; then
        RUNNER=(sh "$RUN_DIR/willy-engine"); break
      fi
    fi
    if "$RUN_DIR/willy-engine" --version >/dev/null 2>&1; then
      RUNNER=("$RUN_DIR/willy-engine"); break
    fi
    if sh "$RUN_DIR/willy-engine" --version >/dev/null 2>&1; then
      RUNNER=(sh "$RUN_DIR/willy-engine"); break
    fi
    rm -rf "$RUN_DIR"; RUN_DIR=""
  done
  (( ${#RUNNER[@]} )) || die "could not run willy-engine on this system. See guidance.md, 'Troubleshooting'."

  THREAD_ARGS=()
  [[ -n "${WILLY_THREADS:-}" ]] && THREAD_ARGS=(-t "$WILLY_THREADS")

  mkdir -p "$USB_DIR/logs" 2>/dev/null || true
  SERVER_LOG="${RUN_DIR}/server.log"
  label=$(basename "$MODEL" .gguf); label=${label#willy-}
  echo "Starting Willy (${label} brain, this can take a minute from USB)..."
  "${RUNNER[@]}" --server --nobrowser -m "$MODEL" --host 127.0.0.1 --port "$PORT" \
      -c "$CTX" ${THREAD_ARGS[@]+"${THREAD_ARGS[@]}"} >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  for _ in $(seq 1 300); do
    if health; then break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      tail -n 20 "$SERVER_LOG" >&2
      die "model server exited during startup (log above)."
    fi
    sleep 1
  done
  health || die "model server did not become ready in 5 minutes. Log: $SERVER_LOG"
fi

python3 "$USB_DIR/willy.py" --api "$API" --log-dir "$USB_DIR/logs" "$@"
