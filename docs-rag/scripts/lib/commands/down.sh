# shellcheck shell=bash
# =============================================================================
# rag down — Stop all services (canonical: down; alias: stop)
# =============================================================================
# run() is the `cmd_stop` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "down|stop|both|Stop all services and release the port claim"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    info "Stopping RAG Bootstrap..."
    docker compose down
    registry_release
    success "Services stopped"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag down${NC} — Stop all services  (alias: ${GREEN}stop${NC})

${CYAN}Usage:${NC}
  rag down

Stops the compose stack and releases this instance's host port-registry claim.
EOF
}
