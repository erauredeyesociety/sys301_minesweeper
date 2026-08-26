# shellcheck shell=bash
# =============================================================================
# rag health — Check detailed system health
# =============================================================================
# run() is the `cmd_health` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "health||both|Check detailed system health"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    parse_config
    local port
    port="$(resolved_port)"
    local url="http://localhost:${port}/api/health"

    info "Checking health at $url"

    local health
    health=$(curl -sf "$url") || fatal "Could not reach API"

    echo "$health" | python3 -c "
import sys, json
h = json.load(sys.stdin)
print()
print('RAG Bootstrap Health')
print('=' * 40)
print(f\"Overall Status: {h['status'].upper()}\")
print()
print('Components:')
print(f\"  Database (PostgreSQL): {'✓ Connected' if h['database'] else '✗ Disconnected'}\")
print(f\"  Cache (Redis):         {'✓ Connected' if h['redis'] else '✗ Disconnected'}\")
print(f\"  Embedding Service:     {'✓ Ready' if h['embedding_service'] else '✗ Unavailable'}\")
print(f\"  LLM (Ollama):          {'✓ Connected' if h['llm'] else '✗ Unavailable'}\")
print()
"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag health${NC} — Check detailed system health

${CYAN}Usage:${NC}
  rag health

Queries the API /api/health endpoint and prints per-component status
(database, cache, embedding service, LLM). Fails if the API is unreachable.
EOF
}
