#!/usr/bin/env bash
# rh-query.sh — query ResearchHub with a preflight that CANNOT report a false success.
# Touches the hub? No. Timeout: 20 s preflight + 45 s query, both hard-bounded.
#
# Why this exists: firing queries at a stale tunnel wastes time and, worse, an empty result
# from a dead tunnel looks exactly like an empty result from a healthy corpus. This wrapper
# separates the two, and separates both from "the tunnel is fine but ResearchHub itself is
# down or being updated" — three different problems with three different fixes.
#
#   ./scripts/rh-query.sh "coverage path planning"          # search the corpus
#   ./scripts/rh-query.sh --json "gyro drift"               # raw JSON instead of titles
#   ./scripts/rh-query.sh --check                           # preflight only, no query
#   ./scripts/rh-query.sh --no-repair "..."                 # fail instead of auto-repairing
#
# Exit codes — each names a DIFFERENT fault, so a caller can branch on them:
#   0  OK
#   3  TUNNEL_DOWN      tunnel is not up and could not be repaired  -> check pwnstar/ZeroTier
#   4  REMOTE_UNHEALTHY tunnel is fine, ResearchHub is not          -> it is down or updating; wait
#   5  QUERY_FAILED     preflight passed, the query itself failed   -> check the endpoint/params
#   64 usage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL="$HERE/rh-tunnel.sh"
LOCAL_PORT_FILE="$HERE/.rh-tunnel.local"

EX_OK=0; EX_TUNNEL_DOWN=3; EX_REMOTE_UNHEALTHY=4; EX_QUERY_FAILED=5; EX_USAGE=64

PREFLIGHT_TIMEOUT=20
QUERY_TIMEOUT=45
REPAIR=1
MODE=query
FORMAT=titles
QUERY=""

log() { printf '%s\n' "$*" >&2; }

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit $EX_USAGE
}

while (( $# )); do
  case "$1" in
    --check)     MODE=check ;;
    --json)      FORMAT=json ;;
    --no-repair) REPAIR=0 ;;
    -h|--help)   usage ;;
    -*)          log "unknown option: $1"; usage ;;
    *)           QUERY="${QUERY:+$QUERY }$1" ;;
  esac
  shift
done

[[ -x "$TUNNEL" ]] || { log "ERROR: $TUNNEL missing or not executable"; exit $EX_TUNNEL_DOWN; }
[[ $MODE == check || -n $QUERY ]] || usage

# --- 1. Tunnel preflight -----------------------------------------------------
# rh-tunnel.sh status already proves the forward end-to-end (a real HTTP request through
# the local port returning a known-correct response), so we do not re-implement that here.
# Never `|| true` this: a status we could not obtain is a failure, not a pass.
tunnel_state() {
  local out rc
  set +e
  out="$(timeout "$PREFLIGHT_TIMEOUT" "$TUNNEL" status 2>&1)"; rc=$?
  set -e
  printf '%s' "$out" >&2
  printf '\n' >&2
  return $rc
}

if ! tunnel_state; then
  if (( REPAIR )); then
    log "PREFLIGHT: tunnel not WORKING — repairing once before giving up"
    set +e
    timeout 90 "$TUNNEL" restart >&2; rc=$?
    set -e
    if (( rc != 0 )); then
      log "PREFLIGHT: FAILED — repair did not bring the tunnel up (rc=$rc)"
      log "           -> is pwnstar reachable? check ZeroTier and ~/.ssh/id_git"
      exit $EX_TUNNEL_DOWN
    fi
    if ! tunnel_state; then
      log "PREFLIGHT: FAILED — tunnel still not WORKING after repair"
      exit $EX_TUNNEL_DOWN
    fi
    log "PREFLIGHT: tunnel repaired"
  else
    log "PREFLIGHT: FAILED — tunnel not WORKING and --no-repair was given"
    exit $EX_TUNNEL_DOWN
  fi
fi

# .rh-tunnel.local holds "<local-port> <remote-port>" -- take the FIRST field only.
read -r PORT _ < "$LOCAL_PORT_FILE" 2>/dev/null || PORT=""
[[ $PORT =~ ^[0-9]+$ ]] || { log "PREFLIGHT: FAILED — tunnel reports WORKING but no usable local port in $LOCAL_PORT_FILE"; exit $EX_TUNNEL_DOWN; }
BASE="http://127.0.0.1:${PORT}"

# --- 2. Remote-service preflight ---------------------------------------------
# A WORKING tunnel means bytes reach pwnstar. It does NOT mean ResearchHub is ready to
# answer -- it may be restarting, migrating, or mid-update. Assert the known-correct
# health payload, not merely that something answered.
set +e
HEALTH="$(timeout "$PREFLIGHT_TIMEOUT" curl -sS --max-time "$PREFLIGHT_TIMEOUT" "$BASE/health" 2>&1)"; hrc=$?
set -e
if (( hrc != 0 )); then
  log "PREFLIGHT: REMOTE_UNHEALTHY — tunnel is up but $BASE/health did not answer (curl rc=$hrc)"
  log "           -> ResearchHub is down or restarting on pwnstar. This is NOT a tunnel fault."
  exit $EX_REMOTE_UNHEALTHY
fi
case "$HEALTH" in
  *'"status":"healthy"'*) : ;;
  *)
    log "PREFLIGHT: REMOTE_UNHEALTHY — tunnel is up, ResearchHub answered but is not healthy:"
    log "           $HEALTH"
    log "           -> likely down for maintenance or mid-update. Wait and retry; do not repair the tunnel."
    exit $EX_REMOTE_UNHEALTHY ;;
esac

if [[ $MODE == check ]]; then
  log "PREFLIGHT: OK — tunnel WORKING, ResearchHub healthy at $BASE"
  exit $EX_OK
fi

# --- 3. The query itself -----------------------------------------------------
# ResearchHub's discovery search is GET with `q` (POST returns 405; `query` returns 422).
set +e
BODY="$(timeout "$QUERY_TIMEOUT" curl -sS --max-time "$QUERY_TIMEOUT" -G \
          "$BASE/api/discover/search" --data-urlencode "q=$QUERY" 2>&1)"; qrc=$?
set -e
if (( qrc != 0 )); then
  log "QUERY_FAILED — request errored after a passing preflight (curl rc=$qrc)"
  log "  $BODY"
  exit $EX_QUERY_FAILED
fi

if [[ $FORMAT == json ]]; then
  printf '%s\n' "$BODY"
  exit $EX_OK
fi

# Titles view. A parse failure is a failure -- never fall through to a cheerful empty result.
python3 - "$BODY" <<'PY' || exit 5
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception as e:
    sys.stderr.write("QUERY_FAILED - response was not JSON: {0}\n".format(e))
    sys.stderr.write(sys.argv[1][:400] + "\n")
    sys.exit(5)
if isinstance(d, dict) and "error_code" in d:
    sys.stderr.write("QUERY_FAILED - ResearchHub returned an error: {0}\n".format(d))
    sys.exit(5)
papers = d.get("papers", []) if isinstance(d, dict) else []
print("total_found={0}  returned={1}".format(d.get("total_found", "?"), len(papers)))
for p in papers:
    ident = p.get("arxiv_id") or p.get("doi") or "-"
    print("  [{0}] {1} ({2})".format(ident, p.get("title", "?"), p.get("year", "?")))
    auth = p.get("authors") or []
    if auth:
        print("        " + ", ".join(auth[:3]) + ("..." if len(auth) > 3 else ""))
if not papers:
    print("  (no papers -- this is a REAL empty result: preflight passed, ResearchHub was healthy)")
PY
