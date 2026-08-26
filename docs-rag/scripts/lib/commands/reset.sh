# shellcheck shell=bash
# =============================================================================
# rag reset — Wipe ALL data for a fresh re-init
# =============================================================================
# run() is the `cmd_reset` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "reset||both|Wipe ALL data for a fresh re-init (root-owned safe)"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    # --yes / -y / --force (B2): non-interactive wipe for CI/automation and
    # the `start --reindex` flow (no TTY prompt).
    local assume_yes=0
    for arg in "$@"; do
        case "$arg" in
            --yes|-y|--force) assume_yes=1 ;;
        esac
    done

    warn "This will stop all services and WIPE ALL DATA for a fresh re-init:"
    warn "  - Docker containers, networks, volumes"
    warn "  - Database files (data/docker/postgres/) — even if root-owned"
    warn "  - Redis cache, cached embeddings, logs, exports, registry"
    if [[ "$assume_yes" == "1" ]]; then
        info "Proceeding without prompt (--yes)"
        REPLY=y
    else
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
    fi

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Stopping services..."
        docker compose down -v --remove-orphans 2>/dev/null || true
        registry_release

        wipe_data_dirs
        ensure_data_directories

        success "Reset complete. Run './rag up --build' then './rag ingest' to re-index."
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

${BOLD}rag reset${NC} — Wipe ALL data for a fresh re-init

${CYAN}Usage:${NC}
  rag reset [--yes|-y|--force]

Stops services and wipes containers/networks/volumes and data directories
(handles root-owned bind-mount files via a throwaway root container).
${GREEN}--yes${NC} / ${GREEN}-y${NC} / ${GREEN}--force${NC} skips the confirmation prompt (CI/automation).
EOF
}
