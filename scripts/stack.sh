#!/usr/bin/env bash
# stack.sh — one entry point for this project's retrieval stack.
# Touches the hub? No. Every step hard-bounded by a timeout.
#
#   ./scripts/stack.sh up       ollama (+ embedding model) -> docs-rag -> ResearchHub tunnel
#   ./scripts/stack.sh status   what is actually WORKING, proved not assumed
#   ./scripts/stack.sh down     stop it all and give the RAM back
#
# Why one script: ollama does NOT start at boot (deliberately -- it is a user-local binary with no
# systemd unit), so the stack needs bringing up by hand, and the three pieces have a strict order:
# docs-rag search 503s without ollama, and the tunnel is independent of both.
#
# Exit codes: 0 all WORKING · 1 something is not · 64 usage
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RAG_URL="http://127.0.0.1:10060"

log()  { printf '%s\n' "$*"; }
ok()   { printf '  OK       %s\n' "$*"; }
bad()  { printf '  FAIL     %s\n' "$*"; }
warn() { printf '  DEGRADED %s\n' "$*"; }

ollama_up() { timeout 8 curl -sSf -o /dev/null "http://127.0.0.1:11434/api/tags" 2>/dev/null; }
vpn_up()    { ip -br addr 2>/dev/null | grep -qE '^(tun|vpn)[0-9]'; }

# A 200 from /api/health is NOT proof: it reports embedding_service:true while ollama is dead.
# The only honest check is a real search returning a real hit.
# Assert a real ANSWER, not a 200. A 500 here is the normal failure when no LLM is pulled.
# TIMEOUT: 300s, not 90s. MEASURED 2026-08-27: a WARM qwen3:14b on skytracker answers
# in ~79 s over the VPN, but the FIRST call after the model is evicted must load 9.3 GB
# into GPU memory and takes longer. A 90 s ceiling therefore passed when warm and failed
# exactly when someone was checking after an idle period -- reporting the LLM as broken
# when it was merely cold. Slow is not the same as broken; say which one it is.
rag_ask_works() {
  local body
  body="$(timeout 300 curl -sS --max-time 300 -X POST "$RAG_URL/api/ask" \
            -H 'Content-Type: application/json' \
            -d '{"question":"what is the lane pitch formula"}' 2>/dev/null)" || return 1
  case "$body" in *'answer'*) return 0 ;; *) return 1 ;; esac
}

rag_search_works() {
  local body
  body="$(timeout 40 curl -sS --max-time 40 -X POST "$RAG_URL/api/v1/search" \
            -H 'Content-Type: application/json' \
            -d '{"query":"lane pitch","limit":1}' 2>/dev/null)" || return 1
  case "$body" in *'document_filepath'*) return 0 ;; *) return 1 ;; esac
}

cmd_up() {
  log "1/3 ollama + embedding model"
  timeout 240 "$ROOT/docs-rag/ollama-serve.sh" | sed 's/^/  /'

  log "2/3 docs-rag"
  if timeout 8 curl -sSf -o /dev/null "$RAG_URL/api/health" 2>/dev/null; then
    ok "already up"
  else
    (cd "$ROOT/docs-rag" && timeout 180 ./rag up) | sed 's/^/  /'
  fi

  log "3/4 ResearchHub tunnel (pwnstar, over ZeroTier)"
  timeout 150 "$HERE/rh-query.sh" --check 2>&1 | sed 's/^/  /' || true

  log "4/4 skytracker ollama (optional — needs the ERAU VPN)"
  if vpn_up; then
    timeout 200 "$HERE/sky-ollama.sh" up 2>&1 | sed 's/^/  /' || true
  else
    log "  skipped — ERAU VPN not connected. Local ollama is serving embeddings."
    log "  To enable:  sudo openconnect --background --script=/usr/share/vpnc-scripts/vpnc-script \\"
    log "                  --user=<netid> dbvpn1.erau.edu"
    log "  Then:       ./scripts/sky-ollama.sh up && ./scripts/sky-ollama.sh models"
  fi

  log ""
  cmd_status
}

cmd_status() {
  local rc=0
  log "stack status"

  # Whether a dead LOCAL ollama matters depends on where docs-rag is pointed. Since
  # 2026-08-27 it points at skytracker (OLLAMA_BASE_URL in docs-rag/.env), so a local
  # ollama is not required at all and calling it a failure is simply wrong.
  local rag_ollama
  rag_ollama="$(grep -E '^OLLAMA_BASE_URL=' "$ROOT/docs-rag/.env" 2>/dev/null | head -1 | cut -d= -f2- | awk '{print $1}')"
  if ollama_up; then
    ok "ollama              http://127.0.0.1:11434 (local)"
  elif [ -n "$rag_ollama" ] && ! printf '%s' "$rag_ollama" | grep -q '11434'; then
    ok "ollama              local is down, and NOT NEEDED -- docs-rag uses $rag_ollama"
  else
    bad "ollama              NOT RESPONDING -> docs-rag search will 503"; rc=1
  fi

  if timeout 8 curl -sSf -o /dev/null "$RAG_URL/api/health" 2>/dev/null; then
    if rag_search_works; then
      ok "docs-rag search     $RAG_URL"
    else
      bad "docs-rag search     API is up but SEARCH FAILS (usually ollama) -- health lies here"; rc=1
    fi
    # /api/ask is the POINT of the docs-rag: it answers a question so the caller does not have to
    # read and synthesise chunks itself. Search alone does NOT offload that work. Report it separately
    # and count it as a real failure -- "search works" is not "docs-rag works".
    if rag_ask_works; then
      ok "docs-rag ask        $RAG_URL/api/ask (token offload available)"
    else
      bad "docs-rag ask        NOT WORKING -- no LLM. Callers must read chunks themselves (costly)"; rc=1
    fi
  else
    bad "docs-rag            NOT RESPONDING"; rc=1
  fi

  set +e
  timeout 150 "$HERE/rh-query.sh" --check >/dev/null 2>&1; local trc=$?
  set -e
  case $trc in
    0) ok   "ResearchHub         tunnel WORKING, remote healthy" ;;
    3) bad  "ResearchHub         TUNNEL DOWN -> check ZeroTier / pwnstar"; rc=1 ;;
    4) warn "ResearchHub         tunnel fine, REMOTE UNHEALTHY (updating?) -- not a tunnel fault"; rc=1 ;;
    *) bad  "ResearchHub         UNKNOWN (rc=$trc)"; rc=1 ;;
  esac

  # skytracker is optional -- it is the REMOTE ollama alternative, gated on the ERAU VPN.
  if vpn_up; then
    set +e
    timeout 60 "$HERE/sky-ollama.sh" status >/dev/null 2>&1; local src=$?
    set -e
    case $src in
      0) ok   "skytracker ollama   forwarded (remote embeddings/LLM available)" ;;
      5) warn "skytracker ollama   VPN interface up but script says NO_VPN" ;;
      *) warn "skytracker ollama   not forwarded (optional) -- ./scripts/sky-ollama.sh up" ;;
    esac
  else
    warn "skytracker ollama   ERAU VPN not connected (optional -- local ollama is in use)"
  fi

  log ""
  log "RAM: $(free -h | awk '/^Mem:/{print $7" available of "$2}')"
  return $rc
}

cmd_down() {
  log "stopping ResearchHub tunnel"; timeout 60 "$HERE/rh-tunnel.sh" down 2>&1 | sed 's/^/  /' || true
  log "stopping docs-rag";           (cd "$ROOT/docs-rag" && timeout 120 ./rag down) 2>&1 | sed 's/^/  /' || true
  log "stopping ollama (frees ~1.9 GB -- the model runner, not the containers)"
  # Only OUR socket owners, never a blanket pkill: the operator has their own processes.
  for pid in $(ss -ltnpH 'sport = :11434' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u); do
    kill "$pid" 2>/dev/null && log "  killed pid $pid" || true
  done
  log "done"
}

case "${1:-}" in
  up)     cmd_up ;;
  status) cmd_status ;;
  down)   cmd_down ;;
  *)      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 64 ;;
esac
