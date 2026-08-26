# shellcheck shell=bash
# =============================================================================
# rag logs — Show logs (optionally for one service)
# =============================================================================
# run() is the `cmd_logs` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "logs||both|Show logs (optionally for a service)"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local service="${1:-}"

    if [[ -n "$service" ]]; then
        docker compose logs -f "$service"
    else
        docker compose logs -f
    fi
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag logs${NC} — Follow service logs

${CYAN}Usage:${NC}
  rag logs [service]

Follows logs for all services, or just the named service
(e.g. ${GREEN}api${NC}, ${GREEN}postgres${NC}, ${GREEN}redis${NC}, ${GREEN}frontend${NC}).
EOF
}
