# shellcheck shell=bash
# =============================================================================
# rag ingest — Ingest documents from config or specified paths
# =============================================================================
# run() is the `cmd_ingest` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "ingest||both|Ingest documents from config or specified paths"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    parse_config

    # Check if API is running
    local port
    port="$(resolved_port)"
    if ! curl -sf "http://localhost:${port}/api/health" >/dev/null 2>&1; then
        fatal "API is not running. Start services first with: ./rag up"
    fi

    do_ingest "$@"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag ingest${NC} — Ingest documents

${CYAN}Usage:${NC}
  rag ingest [path...]

Ingests documents from the config.yaml ingestion.directories, or from the
given path(s). The ingest is idempotent (unchanged files skip re-embedding).
Requires the stack to be running.
EOF
}
