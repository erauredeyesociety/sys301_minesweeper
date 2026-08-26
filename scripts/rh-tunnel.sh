#!/usr/bin/env bash
# rh-tunnel.sh — SSH port-forward from this host to the ResearchHub API on pwnstar.
# Touches the LEGO hub: NO. Network only. Every SSH/HTTP call is bounded by an explicit timeout
# (ssh ConnectTimeout=10 + outer `timeout`; curl --max-time). Never runs a git mutation.
#
# Subcommands: up | down | status | restart | discover
# status prints WORKING / STALE / DOWN / UNKNOWN and exits non-zero for anything but WORKING.
#
# The point of this script is STALENESS DETECTION: an ssh PID being alive proves nothing. The
# forward is only WORKING when a real HTTP request through the local port returns a known-correct
# response (HTTP 200 + {"status":"healthy"}). A half-open socket, a dead remote container, or a
# dropped ZeroTier link all leave the ssh process happily running.

set -euo pipefail

# ---------------------------------------------------------------- configuration (env-overridable)
RH_SSH_HOST="${RH_SSH_HOST:-10.231.80.91}"       # pwnstar, over ZeroTier
RH_SSH_USER="${RH_SSH_USER:-devel}"
RH_SSH_KEY="${RH_SSH_KEY:-$HOME/.ssh/id_git}"
RH_LOCAL_PORT="${RH_LOCAL_PORT:-5347}"           # preferred local port; auto-bumped if taken
RH_HEALTH_PATH="${RH_HEALTH_PATH:-/health}"
RH_HEALTH_MATCH="${RH_HEALTH_MATCH:-\"status\":\"healthy\"}"

# Ports worth looking at on the remote when nothing is cached. The probe, not this list, decides.
PLAUSIBLE_PORTS=(5347 8000 8001 8080 8081 8443 3000 3001 5000 9000 10100)

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PORT_CACHE="$SCRIPT_DIR/.rh-port"                # discovered REMOTE port
PID_FILE="$SCRIPT_DIR/.rh-tunnel.pid"            # our ssh PID, and only ours
LOCAL_FILE="$SCRIPT_DIR/.rh-tunnel.local"        # "<local-port> <remote-port>" of the live tunnel

# Exit codes, so callers can branch without parsing text.
EX_WORKING=0; EX_STALE=2; EX_DOWN=3; EX_UNKNOWN=4; EX_USAGE=64

SSH_OPTS=(
  -o BatchMode=yes            # never prompt for a password; fail instead of hanging
  -o ConnectTimeout=10
  -o ServerAliveInterval=15   # notice a dropped link instead of holding a dead socket open
  -o ServerAliveCountMax=3
  -o ExitOnForwardFailure=yes # if the forward cannot bind, ssh must not sit there pretending
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=accept-new
)
[[ -r "$RH_SSH_KEY" ]] && SSH_OPTS+=(-i "$RH_SSH_KEY") || true

log()  { printf '%s\n' "$*" >&2; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------------- remote helper
# remote_sh <seconds> <command>  — read-only commands only. Nothing on pwnstar is ever modified.
remote_sh() {
  local secs="$1"; shift
  timeout "$secs" ssh "${SSH_OPTS[@]}" "${RH_SSH_USER}@${RH_SSH_HOST}" "$@"
}

# ------------------------------------------------------------------------------------- local port
port_in_use() {  # 0 = something is listening locally on $1
  ss -tlnH "sport = :$1" 2>/dev/null | grep -q .
}

pick_local_port() {
  local p="$RH_LOCAL_PORT"
  for _ in $(seq 1 40); do
    port_in_use "$p" || { printf '%s' "$p"; return 0; }
    p=$((p + 1))
  done
  die "no free local port found in ${RH_LOCAL_PORT}..$((RH_LOCAL_PORT + 39))"
}

# ------------------------------------------------------------------------------------- the probe
# THE staleness test. Not "did TCP connect" — an actual request with an asserted response body.
# probe_local <local-port>
probe_local() {
  local port="$1" out code body
  command -v curl >/dev/null 2>&1 || return 3   # cannot test => UNKNOWN, never a pass
  out="$(timeout 15 curl -sS --max-time 10 -o - -w $'\n%{http_code}' \
         "http://127.0.0.1:${port}${RH_HEALTH_PATH}" 2>/dev/null)" || return 1
  code="${out##*$'\n'}"
  body="${out%$'\n'*}"
  [[ "$code" == "200" ]] || return 1
  grep -qF "$RH_HEALTH_MATCH" <<<"$body" || return 1
  return 0
}

# ------------------------------------------------------------------------ our-ssh-process tracking
# Kill ONLY the process we started. Never `pkill ssh` — the operator has their own sessions open.
tunnel_cmdline_pattern() { printf -- '-L %s:localhost:%s' "$1" "$2"; }

pid_is_our_tunnel() {  # pid_is_our_tunnel <pid> <local-port> <remote-port>
  local pid="$1" want; want="$(tunnel_cmdline_pattern "$2" "$3")"
  [[ -n "$pid" && -d "/proc/$pid" ]] || return 1
  local cmd; cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmd" == ssh\ * ]] || return 1          # argv[0] must BE ssh, not a `timeout ssh ...` wrapper
  [[ "$cmd" == *"$want"* ]] || return 1
  [[ "$cmd" == *"${RH_SSH_USER}@${RH_SSH_HOST}"* ]] || return 1
  return 0
}

read_state() {  # sets TUN_PID / TUN_LOCAL / TUN_REMOTE (empty when unknown)
  TUN_PID=""; TUN_LOCAL=""; TUN_REMOTE=""
  [[ -s "$PID_FILE" ]] && TUN_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  # the live tunnel records its OWN remote port, so a later re-discovery cannot make us
  # mis-identify (and therefore refuse to kill, or worse, kill the wrong thing) our own process
  if [[ -s "$LOCAL_FILE" ]]; then
    read -r TUN_LOCAL TUN_REMOTE < "$LOCAL_FILE" || true
  fi
  TUN_LOCAL="${TUN_LOCAL:-}"; TUN_REMOTE="${TUN_REMOTE:-}"
}

kill_our_tunnel() {
  read_state
  if [[ -z "$TUN_PID" ]]; then
    log "no pidfile — nothing of ours to kill"
    rm -f "$LOCAL_FILE"
    return 0
  fi
  if pid_is_our_tunnel "$TUN_PID" "$TUN_LOCAL" "$TUN_REMOTE"; then
    log "killing our ssh tunnel pid=$TUN_PID (-L ${TUN_LOCAL}:localhost:${TUN_REMOTE})"
    kill -TERM "$TUN_PID" 2>/dev/null || true
    for _ in $(seq 1 10); do [[ -d "/proc/$TUN_PID" ]] || break; sleep 0.5; done
    [[ -d "/proc/$TUN_PID" ]] && { warn "pid $TUN_PID ignored SIGTERM; sending SIGKILL"; kill -KILL "$TUN_PID" 2>/dev/null || true; }
  else
    warn "pid $TUN_PID in $PID_FILE is NOT our tunnel (gone, or PID reused) — leaving it alone"
  fi
  rm -f "$PID_FILE" "$LOCAL_FILE"
}

# ------------------------------------------------------------------------------------- discover
# Find the ResearchHub port on the remote. Read-only over SSH: `docker ps`, `ss -tlnH`, and a
# `curl` of each candidate's /health FROM the remote host. The port is only accepted when the
# candidate answers with the known-correct ResearchHub health response.
cmd_discover() {
  local force="${1:-}"
  if [[ "$force" != "--force" && -s "$PORT_CACHE" ]]; then
    log "cached remote port $(cat "$PORT_CACHE") (${PORT_CACHE}) — re-run with: $0 discover --force"
    cat "$PORT_CACHE"; return 0
  fi

  log "discover: ssh ${RH_SSH_USER}@${RH_SSH_HOST} (read-only)"
  local docker_out="" ss_out="" candidates=()

  if docker_out="$(remote_sh 40 'docker ps --format "{{.Names}}|{{.Image}}|{{.Ports}}" 2>/dev/null' || true)"; [[ -n "$docker_out" ]]; then
    log "--- remote containers matching /researchhub/i ---"
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      log "  $line"
      # published host ports look like 0.0.0.0:5347->8000/tcp or 127.0.0.1:10100->80/tcp
      while IFS= read -r p; do [[ -n "$p" ]] && candidates+=("$p") || true; done < <(
        grep -oE '(^|[^0-9])([0-9]{2,5})->' <<<"$line" | grep -oE '[0-9]{2,5}' || true)
    done < <(grep -i researchhub <<<"$docker_out" || true)
  else
    warn "no docker output from the remote (docker absent, no permission, or ssh failed)"
  fi

  if ss_out="$(remote_sh 30 'ss -tlnH 2>/dev/null' || true)"; [[ -n "$ss_out" ]]; then
    local listening
    listening="$(awk '{print $4}' <<<"$ss_out" | sed 's/.*://' | sort -un)"
    for p in "${PLAUSIBLE_PORTS[@]}"; do
      grep -qx "$p" <<<"$listening" && candidates+=("$p") || true
    done
  else
    warn "no ss output from the remote"
  fi

  if ((${#candidates[@]} == 0)); then
    log "STATUS: UNKNOWN — no candidate ports found. Do NOT guess one."
    log "  Try by hand: ssh ${RH_SSH_USER}@${RH_SSH_HOST} 'docker ps; ss -tlnp'"
    return $EX_UNKNOWN
  fi

  # dedupe, keep order
  local uniq=() c
  for c in "${candidates[@]}"; do [[ " ${uniq[*]-} " == *" $c "* ]] || uniq+=("$c"); done
  log "candidate remote ports: ${uniq[*]}"

  for c in "${uniq[@]}"; do
    log "  probing remote 127.0.0.1:${c}${RH_HEALTH_PATH} ..."
    local out code body
    out="$(remote_sh 30 "curl -sS -m 8 -o - -w '\n%{http_code}' 'http://127.0.0.1:${c}${RH_HEALTH_PATH}' 2>/dev/null" || true)"
    code="${out##*$'\n'}"; body="${out%$'\n'*}"
    if [[ "$code" == "200" ]] && grep -qF "$RH_HEALTH_MATCH" <<<"$body"; then
      log "  MATCH: port $c answered ${RH_HEALTH_PATH} with $body"
      printf '%s\n' "$c" > "$PORT_CACHE"
      log "cached to $PORT_CACHE"
      printf '%s\n' "$c"
      return 0
    fi
    log "  no: http=${code:-none}"
  done

  log "STATUS: UNKNOWN — candidates ${uniq[*]} exist but none returned the ResearchHub health response."
  log "  A port number is NOT being guessed. Inspect by hand, then: echo <port> > $PORT_CACHE"
  return $EX_UNKNOWN
}

resolve_remote_port() {
  if [[ -s "$PORT_CACHE" ]]; then cat "$PORT_CACHE"; return 0; fi
  log "no cached remote port — running discovery first"
  cmd_discover >/dev/null || return $?
  cat "$PORT_CACHE"
}

# ------------------------------------------------------------------------------------------- up
cmd_up() {
  local rc=0
  cmd_status --quiet || rc=$?
  if (( rc == EX_WORKING )); then
    read_state
    log "already WORKING on http://127.0.0.1:${TUN_LOCAL} (pid $TUN_PID) — nothing changed"
    return $EX_WORKING
  fi
  if (( rc == EX_STALE )); then
    log "existing tunnel is STALE — tearing it down before re-establishing"
    kill_our_tunnel
  else
    read_state
    [[ -n "${TUN_PID:-}" ]] && kill_our_tunnel || true
  fi

  local remote local_port
  remote="$(resolve_remote_port)" || die "remote ResearchHub port is UNKNOWN — run: $0 discover"
  local_port="$(pick_local_port)"
  [[ "$local_port" == "$RH_LOCAL_PORT" ]] || log "local port $RH_LOCAL_PORT was busy; using $local_port"

  log "ssh -f -N -L ${local_port}:localhost:${remote} ${RH_SSH_USER}@${RH_SSH_HOST}"
  timeout 30 ssh -f -N -L "${local_port}:localhost:${remote}" "${SSH_OPTS[@]}" \
      "${RH_SSH_USER}@${RH_SSH_HOST}" \
    || die "ssh failed to establish the forward (host unreachable, key rejected, or port in use)"

  # `ssh -f` forks, so $! is useless. Find OUR process by its exact forward spec + destination.
  local pid=""
  for _ in $(seq 1 10); do
    # ^ssh anchors the match to the ssh process itself. Without it the pattern also matches the
    # `timeout ... ssh ...` wrapper (observed 2026-08-25), and we would track/kill the wrong PID.
    pid="$(pgrep -u "$(id -u)" -f "^ssh .*-L ${local_port}:localhost:${remote} .*${RH_SSH_USER}@${RH_SSH_HOST}" | head -n1 || true)"
    [[ -n "$pid" ]] && break
    sleep 0.5
  done
  [[ -n "$pid" ]] || die "forward launched but its PID could not be identified — refusing to track an unknown process"

  printf '%s\n' "$pid" > "$PID_FILE"
  printf '%s %s\n' "$local_port" "$remote" > "$LOCAL_FILE"

  if probe_local "$local_port"; then
    log "STATUS: WORKING — http://127.0.0.1:${local_port} -> ${RH_SSH_HOST}:${remote} (pid $pid)"
    return $EX_WORKING
  fi
  warn "forward came up but the health probe FAILED — tearing it down rather than reporting a pass"
  kill_our_tunnel
  log "STATUS: DOWN"
  return $EX_DOWN
}

# ----------------------------------------------------------------------------------------- down
cmd_down() { kill_our_tunnel; log "STATUS: DOWN"; return 0; }

# --------------------------------------------------------------------------------------- status
# WORKING = probe asserted a known-correct response through the local port.
# STALE   = our ssh process is alive but the probe failed. Repair with `restart`.
# DOWN    = no tunnel of ours.
# UNKNOWN = cannot tell (state files inconsistent, no curl, port not on record).
cmd_status() {
  local quiet="${1:-}"
  read_state
  local say=log; [[ "$quiet" == "--quiet" ]] && say=:

  if [[ -z "${TUN_PID:-}" || -z "${TUN_LOCAL:-}" ]]; then
    $say "STATUS: DOWN — no tracked tunnel (${PID_FILE} absent or empty)"
    [[ "$quiet" == "--quiet" ]] || echo "DOWN"
    return $EX_DOWN
  fi
  if ! pid_is_our_tunnel "$TUN_PID" "$TUN_LOCAL" "${TUN_REMOTE:-}"; then
    $say "STATUS: DOWN — pid ${TUN_PID} is not our tunnel any more (exited, or PID reused)"
    [[ "$quiet" == "--quiet" ]] || echo "DOWN"
    return $EX_DOWN
  fi

  local rc=0
  probe_local "$TUN_LOCAL" || rc=$?
  case "$rc" in
    0) $say "STATUS: WORKING — pid ${TUN_PID}, http://127.0.0.1:${TUN_LOCAL}${RH_HEALTH_PATH} returned 200 + ${RH_HEALTH_MATCH}"
       [[ "$quiet" == "--quiet" ]] || echo "WORKING"
       return $EX_WORKING ;;
    3) $say "STATUS: UNKNOWN — curl is missing, so the tunnel cannot be proven. Liveness of pid ${TUN_PID} is NOT proof."
       [[ "$quiet" == "--quiet" ]] || echo "UNKNOWN"
       return $EX_UNKNOWN ;;
    *) $say "STATUS: STALE — pid ${TUN_PID} is alive but nothing usable answers on 127.0.0.1:${TUN_LOCAL}. Repair: $0 restart"
       [[ "$quiet" == "--quiet" ]] || echo "STALE"
       return $EX_STALE ;;
  esac
}

cmd_restart() { kill_our_tunnel; cmd_up; }

usage() {
  cat >&2 <<EOF
usage: $0 {up|down|status|restart|discover [--force]}

  up        establish the forward (idempotent; repairs a STALE tunnel first)
  down      kill ONLY our tracked ssh process and clear state
  status    print WORKING / STALE / DOWN / UNKNOWN; exit 0 only for WORKING
  restart   down + up
  discover  find the ResearchHub port on the remote and cache it in $PORT_CACHE

env: RH_SSH_HOST=$RH_SSH_HOST RH_SSH_USER=$RH_SSH_USER RH_SSH_KEY=$RH_SSH_KEY
     RH_LOCAL_PORT=$RH_LOCAL_PORT RH_HEALTH_PATH=$RH_HEALTH_PATH
exit codes: 0 WORKING · 2 STALE · 3 DOWN · 4 UNKNOWN · 64 usage
EOF
  exit $EX_USAGE
}

case "${1:-}" in
  up)       shift; cmd_up "$@" ;;
  down)     shift; cmd_down "$@" ;;
  status)   shift; cmd_status "$@" ;;
  restart)  shift; cmd_restart "$@" ;;
  discover) shift; cmd_discover "${1:-}" ;;
  *)        usage ;;
esac
