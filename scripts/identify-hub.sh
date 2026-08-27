#!/usr/bin/env bash
# identify-hub.sh — the only entry point an agent invokes for hub identification.
# READ-ONLY: writes nothing to the hub. Belt and braces: pyserial timeouts inside,
# an outer timeout(1) here. Runbook: docs/runbooks/hub-identification.md
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"

PORT=""
for c in /dev/spike /dev/ttyACM0; do [ -e "$c" ] && { PORT="$c"; break; }; done
if [ -z "$PORT" ]; then
  echo "UNKNOWN: no /dev/spike or /dev/ttyACM0 — hub not enumerated"; exit 3
fi

OUT="$REPO/docs/findings/_hub-identify-$(date +%Y%m%dT%H%M%S).transcript.txt"
timeout --signal=INT 45 python3 "$HERE/identify_hub.py" 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}
echo
echo "transcript: $OUT"
exit "$rc"
