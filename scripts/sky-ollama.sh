#!/usr/bin/env bash
# sky-ollama.sh — forward skytracker's ollama to this machine, so docs-rag can use a remote
# embedding model (and a larger LLM) instead of loading ~1.9 GB locally.
# Touches the hub? No. Every network call hard-bounded.
#
#   ./scripts/sky-ollama.sh up        establish the forward
#   ./scripts/sky-ollama.sh status    WORKING / STALE / DOWN / NO_VPN, proved not assumed
#   ./scripts/sky-ollama.sh models    list what skytracker actually has pulled
#   ./scripts/sky-ollama.sh discover  find ollama's port on skytracker
#   ./scripts/sky-ollama.sh down      tear down
#   ./scripts/sky-ollama.sh restart
#
# skytracker (155.31.130.52, user skytracker-dev) is behind the **ERAU VPN** and blocks every port
# except SSH, so a forward is the only route. See ~/llm-project-bootstrap/context/skytracker_server.md
# and ERAU_vpn.md.
#
# Exit codes: 0 WORKING · 2 STALE · 3 DOWN · 4 UNKNOWN · 5 NO_VPN · 64 usage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKY_HOST="${SKY_HOST:-155.31.130.52}"
SKY_USER="${SKY_USER:-skytracker-dev}"
LOCAL_PORT="${SKY_OLLAMA_LOCAL_PORT:-11435}"   # 11434 is LOCAL ollama; do not collide
BRIDGE_IP="${DOCKER_BRIDGE_IP:-172.17.0.1}"    # docker0; what host.docker.internal resolves to
PORT_FILE="$HERE/.sky-ollama-port"             # remote port, cached after discovery
PID_FILE="$HERE/.sky-ollama.pid"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)

EX_WORKING=0; EX_STALE=2; EX_DOWN=3; EX_UNKNOWN=4; EX_NO_VPN=5; EX_USAGE=64
log() { printf '%s\n' "$*" >&2; }

# --- VPN gate ---------------------------------------------------------------
# Without the ERAU VPN, SSH just times out after 10 s and every symptom looks like "server down".
# Check the cheap thing first and say the useful sentence.
vpn_up() { ip -br addr 2>/dev/null | grep -qE '^(tun|vpn)[0-9]'; }

require_vpn() {
  if ! vpn_up; then
    log "STATUS: NO_VPN — no tun interface is up."
    log "  skytracker is only reachable over the ERAU VPN (split tunnel, dbvpn1.erau.edu)."
    log "  Connect it, then re-run. ZeroTier being up is NOT the same thing — that is how"
    log "  pwnstar is reached, and it does not route to skytracker."
    log "  See ~/llm-project-bootstrap/context/ERAU_vpn.md"
    exit $EX_NO_VPN
  fi
}

sky_ssh() { timeout 25 ssh "${SSH_OPTS[@]}" "${SKY_USER}@${SKY_HOST}" "$@"; }

# --- discover ---------------------------------------------------------------
cmd_discover() {
  require_vpn
  log "asking skytracker what is listening (read-only)…"
  local listening
  listening="$(sky_ssh 'ss -tlnH 2>/dev/null | awk "{print \$4}" | sed "s/.*://" | sort -un')" || {
    log "STATUS: DOWN — cannot reach ${SKY_USER}@${SKY_HOST} over SSH even with a VPN interface up"
    exit $EX_DOWN; }

  local found=""
  for p in 11434 $listening; do
    if sky_ssh "timeout 6 curl -sf -o /dev/null http://127.0.0.1:${p}/api/tags" 2>/dev/null; then
      found="$p"; break
    fi
  done

  if [[ -z $found ]]; then
    log "STATUS: UNKNOWN — nothing on skytracker answered /api/tags. Do NOT guess a port."
    log "  ports listening there: $(echo "$listening" | tr '\n' ' ')"
    exit $EX_UNKNOWN
  fi
  printf '%s\n' "$found" > "$PORT_FILE"
  log "discovered ollama on skytracker port ${found} (cached in $PORT_FILE)"
  printf '%s\n' "$found"
}

remote_port() {
  [[ -s $PORT_FILE ]] && { cat "$PORT_FILE"; return; }
  cmd_discover >/dev/null
  cat "$PORT_FILE"
}

# --- probe: a real API call, never just "the PID is alive" ------------------
probe() { timeout 12 curl -sf -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/api/tags" 2>/dev/null; }

our_pid() { [[ -s $PID_FILE ]] && cat "$PID_FILE" || true; }

pid_is_ours() {
  local pid="$1"
  [[ -n $pid ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q -- "-L ${LOCAL_PORT}:"
}

# Containers reach ollama through the bridge, not loopback -- so check the bridge too, or
# `status` can say WORKING while docs-rag still cannot see it.
probe_bridge() { timeout 12 curl -sf -o /dev/null "http://${BRIDGE_IP}:${LOCAL_PORT}/api/tags" 2>/dev/null; }

cmd_status() {
  local pid; pid="$(our_pid)"
  if [[ -z $pid ]]; then log "STATUS: DOWN — no tracked forward"; return $EX_DOWN; fi
  if ! pid_is_ours "$pid"; then
    log "STATUS: DOWN — pid $pid is not our forward any more (exited, or PID reused)"; return $EX_DOWN; fi
  if probe; then
    if probe_bridge; then
      log "STATUS: WORKING — 127.0.0.1:${LOCAL_PORT} and ${BRIDGE_IP}:${LOCAL_PORT} -> ${SKY_HOST}:$(cat "$PORT_FILE" 2>/dev/null || echo '?') (pid $pid)"
      return $EX_WORKING
    fi
    log "STATUS: STALE — loopback answers but ${BRIDGE_IP}:${LOCAL_PORT} does not."
    log "  docs-rag containers cannot reach it. Repair with: $0 restart"
    return $EX_STALE
  fi
  # ssh alive but nothing answers: the classic stale forward.
  vpn_up || { log "STATUS: STALE — forward exists but the VPN dropped"; return $EX_STALE; }
  log "STATUS: STALE — pid $pid alive but /api/tags did not answer. Repair with: $0 restart"
  return $EX_STALE
}

kill_ours() {
  local pid; pid="$(our_pid)"
  if pid_is_ours "$pid"; then kill "$pid" 2>/dev/null && log "killed our forward pid $pid"; fi
  rm -f "$PID_FILE"
}

cmd_up() {
  if cmd_status >/dev/null 2>&1; then cmd_status; return $EX_WORKING; fi
  kill_ours
  require_vpn
  local rp; rp="$(remote_port)"
  # TWO bind addresses, and the second one is the whole point:
  #   127.0.0.1  -> reachable from the host (curl, scripts)
  #   172.17.0.1 -> reachable from INSIDE docker containers, which is how docs-rag gets to it.
  # ssh binds only to loopback by default, and a loopback-only forward is invisible to every
  # container -- docs-rag would fail with "All connection attempts failed" and look like a dead
  # remote rather than a binding mistake.
  log "ssh -f -N -L ${LOCAL_PORT}:localhost:${rp} -L ${BRIDGE_IP}:${LOCAL_PORT}:localhost:${rp} ${SKY_USER}@${SKY_HOST}"
  timeout 30 ssh -f -N "${SSH_OPTS[@]}" \
      -L "${LOCAL_PORT}:localhost:${rp}" \
      -L "${BRIDGE_IP}:${LOCAL_PORT}:localhost:${rp}" \
      "${SKY_USER}@${SKY_HOST}" || {
    log "STATUS: DOWN — ssh failed to establish the forward"
    log "  if it complains about binding ${BRIDGE_IP}, the docker bridge is absent — start docker first"
    exit $EX_DOWN; }
  # Record the PID of the forward we just made, matched on our own -L spec.
  local pid
  pid="$(pgrep -u "$USER" -f -- "-L ${LOCAL_PORT}:localhost:${rp}" | tail -1)"
  [[ -n $pid ]] && printf '%s\n' "$pid" > "$PID_FILE"
  sleep 1
  cmd_status
}

cmd_models() {
  cmd_status >/dev/null || { log "bring it up first: $0 up"; exit $EX_DOWN; }
  timeout 20 curl -sS "http://127.0.0.1:${LOCAL_PORT}/api/tags" \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
ms=d.get("models",[])
print("skytracker has {0} model(s):".format(len(ms)))
for m in ms:
    print("  {0:<40} {1:.2f} GB".format(m.get("name","?"), m.get("size",0)/1e9))
if not ms: print("  (none pulled)")'
}

case "${1:-}" in
  up)       cmd_up ;;
  status)   cmd_status ;;
  models)   cmd_models ;;
  discover) cmd_discover ;;
  down)     kill_ours; log "STATUS: DOWN" ;;
  restart)  kill_ours; cmd_up ;;
  *)        sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit $EX_USAGE ;;
esac
