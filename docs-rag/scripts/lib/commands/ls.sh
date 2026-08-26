# shellcheck shell=bash
# =============================================================================
# rag ls — list this host's docs-rag stacks + published ports (read-only)
# =============================================================================
# Enumerates the rag-bootstrap stacks running on THIS host from durable docker
# state (docker ps → compose project + published web port), via registry_list()
# in ../common.sh. READ-ONLY: claims/releases/writes nothing.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "ls|stacks|both|List this host's docs-rag stacks + published ports (read-only)"
}

run() {
    if ! command -v registry_list >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    command -v docker >/dev/null 2>&1 \
        || { error "ls: 'docker' not found on PATH"; return 1; }

    local rows
    rows="$(registry_list)"

    if [[ -z "$rows" ]]; then
        echo "No docs-rag stacks are running on this host."
        return 0
    fi

    printf "${BOLD}%-30s %-7s %s${NC}\n" "STACK" "PORT" "VERSION"
    local proj port tag
    while IFS=$'\t' read -r proj port tag; do
        [[ -n "$proj" ]] || continue
        printf "%-30s %-7s %s\n" "$proj" "$port" "$tag"
    done <<<"$rows"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat <<EOF

${BOLD}rag ls${NC} — list this host's docs-rag stacks + published ports

${CYAN}Usage:${NC}
  rag ls

READ-ONLY. Reads durable docker state (\`docker ps\`, filtered to rag-bootstrap
images) and prints one row per running docs-rag stack on THIS host: the compose
project name, its published web port, and the image version. Touches nothing.
EOF
}
