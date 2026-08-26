# shellcheck shell=bash
# =============================================================================
# rag restart — Restart all services
# =============================================================================
# run() mirrors `cmd_restart` (cmd_stop then cmd_start "$@"). The two
# steps dispatch back through the `rag` entry point so the down/up bodies stay
# single-sourced in their own modules; output/exit codes are byte-identical.

cmd_meta() {
    echo "restart||both|Restart all services (accepts up options)"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    local rag="${RAG_ENTRYPOINT:-$(rag_root)/rag}"

    "$rag" down
    "$rag" up "$@"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag restart${NC} — Restart all services

${CYAN}Usage:${NC}
  rag restart [up options...]

Stops the stack, then starts it again. Accepts the same options as
${GREEN}rag up${NC} (e.g. --build, --defaults, --skip-preflight, --reindex).
EOF
}
