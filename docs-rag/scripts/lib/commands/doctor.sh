# shellcheck shell=bash
# =============================================================================
# rag doctor — Preflight diagnostics
# =============================================================================
# run() is the `cmd_doctor` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "doctor||both|Preflight diagnostics: config, ports, Ollama, disk, dims"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local failures=0
    parse_config

    echo ""
    printf "${BOLD}RAG Bootstrap Doctor${NC}\n"
    echo "===================="

    # 1. Config resolution
    if [[ -f "$CONFIG_FILE" ]]; then
        success "Config file: ${CONFIG_FILE}"
    else
        warn "Config file MISSING: ${CONFIG_FILE} (built-in defaults would be used)"
    fi

    # 2. .env presence
    if [[ -f "$ENV_FILE" ]]; then
        success ".env present: ${ENV_FILE}"
    else
        warn ".env missing (rag up will generate it)"
    fi

    # 3. Effective resolved config
    echo_effective_config

    # 4. Docker availability
    if docker info >/dev/null 2>&1; then
        success "Docker daemon reachable"
    else
        error "Docker daemon NOT reachable"
        failures=$((failures + 1))
    fi

    # 5. RAG_PORT free/occupied
    local port
    port="$(resolved_port)"
    if [[ "$port" == "8100" ]]; then
        legacy_port_warning "doctor: RAG_PORT resolves to 8100"
    fi
    if ! port_in_use "$port"; then
        success "RAG_PORT ${port} is free"
    elif port_held_by_this_stack; then
        success "RAG_PORT ${port} is occupied by THIS stack (running)"
    else
        error "RAG_PORT ${port} is occupied by ANOTHER process (start would auto-increment)"
        failures=$((failures + 1))
    fi

    # 6. Ollama reachability + models pulled
    if ! ollama_check; then
        failures=$((failures + 1))
    fi

    # 7. Disk space
    disk_space_check || true

    # 8. Fleet-resource headroom: inotify instances, host RAM vs this stack's
    #    summed memory caps, template-derived stack count, periodic-reconcile
    #    cadence advisory (warnings only)
    inotify_headroom_check
    ram_headroom_check
    stack_count_check
    reconcile_advisory_check

    # 9. Stored-vs-configured embedding dimension (best-effort, needs postgres up)
    dim_guard report || failures=$((failures + 1))

    echo ""
    if [[ $failures -eq 0 ]]; then
        success "Doctor: all checks passed"
    else
        error "Doctor: ${failures} check(s) failed"
        exit 1
    fi
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag doctor${NC} — Preflight diagnostics

${CYAN}Usage:${NC}
  rag doctor

Checks config resolution, .env presence, Docker reachability, RAG_PORT
availability, Ollama reachability + pulled models, disk space, fleet-resource
headroom (inotify / RAM / stack count / reconcile cadence), and the
stored-vs-configured embedding dimension. Exits non-zero if any hard check fails.
EOF
}
