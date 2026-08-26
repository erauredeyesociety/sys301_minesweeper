# shellcheck shell=bash
# =============================================================================
# rag clean — Stop and remove all data
# =============================================================================
# run() is the `cmd_clean` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "clean||both|Stop and remove all data (volumes + data dirs)"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    warn "This will stop all services and DELETE ALL DATA!"
    warn "  - Docker containers and networks"
    warn "  - Database files (data/docker/postgres/)"
    warn "  - Redis cache (data/docker/redis/)"
    warn "  - All cached embeddings (data/cache/)"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Stopping services..."
        docker compose down -v
        registry_release

        wipe_data_dirs

        success "All data removed. Run './rag up --build' to start fresh."
    else
        info "Cancelled"
    fi
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag clean${NC} — Stop and remove all data

${CYAN}Usage:${NC}
  rag clean

Stops services, removes volumes, and wipes data directories. Prompts for
confirmation first. (See ${GREEN}rag reset${NC} for the root-owned-safe re-init path.)
EOF
}
