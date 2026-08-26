#!/usr/bin/env bash
# Start the embedding backend for the sys301-docs docs-rag. No hub, no timeout needed
# (nothing blocks): starts `ollama serve` on 127.0.0.1:11434 and a socat forwarder on
# the docker bridge 172.17.0.1:11434 so the api CONTAINER can reach it via
# host.docker.internal. Idempotent — says what it started vs. what was already up.
set -euo pipefail

OLLAMA_BIN="${OLLAMA_BIN:-$HOME/.local/bin/ollama}"
BRIDGE_IP="${BRIDGE_IP:-172.17.0.1}"
LOG_DIR="${LOG_DIR:-$HOME/.local/share/sys301-docs-rag/logs}"
mkdir -p "$LOG_DIR"

[ -x "$OLLAMA_BIN" ] || { echo "FAIL: no ollama binary at $OLLAMA_BIN"; exit 1; }

if curl -sf --max-time 5 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "ollama serve: already up on 127.0.0.1:11434 (no change)"
else
  setsid "$OLLAMA_BIN" serve >>"$LOG_DIR/ollama-serve.log" 2>&1 < /dev/null &
  disown || true
  for _ in $(seq 1 20); do
    curl -sf --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1 \
    || { echo "FAIL: ollama did not come up; see $LOG_DIR/ollama-serve.log"; exit 1; }
  echo "ollama serve: STARTED on 127.0.0.1:11434"
fi

if curl -sf --max-time 5 "http://${BRIDGE_IP}:11434/api/version" >/dev/null 2>&1; then
  echo "bridge forwarder: already up on ${BRIDGE_IP}:11434 (no change)"
else
  setsid socat "TCP-LISTEN:11434,bind=${BRIDGE_IP},fork,reuseaddr" TCP:127.0.0.1:11434 \
    >>"$LOG_DIR/socat-ollama.log" 2>&1 < /dev/null &
  disown || true
  sleep 2
  curl -sf --max-time 3 "http://${BRIDGE_IP}:11434/api/version" >/dev/null 2>&1 \
    || { echo "FAIL: socat bridge did not come up; see $LOG_DIR/socat-ollama.log"; exit 1; }
  echo "bridge forwarder: STARTED on ${BRIDGE_IP}:11434 -> 127.0.0.1:11434"
fi

echo -n "model check: "
if curl -sf --max-time 5 http://127.0.0.1:11434/api/tags | grep -q "nomic-embed-text"; then
  echo "nomic-embed-text present"
else
  echo "MISSING nomic-embed-text — run: ollama pull nomic-embed-text"; exit 1
fi
