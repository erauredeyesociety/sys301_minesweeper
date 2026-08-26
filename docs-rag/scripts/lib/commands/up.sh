# shellcheck shell=bash
# =============================================================================
# rag up — Start all services (canonical: up; alias: start)
# =============================================================================
# Module contract: cmd_meta + run + help (see docs/findings/2026-07-05_modular_cli_design.md).
# run() is the `cmd_start` body verbatim; shared helpers come from
# ../common.sh; cross-module invocations (reset/up/ingest for the --reindex
# flow, and the closing status) dispatch back through the `rag` entry point so
# output/flags/exit codes stay byte-for-byte identical.

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "up|start|both|Start the stack (preflight, compose up, dim guard)"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    local rag="${RAG_ENTRYPOINT:-$(rag_root)/rag}"

    local build_flag=""
    local allow_defaults=0
    local skip_preflight=0
    local reindex=0
    local passthrough=()

    for arg in "$@"; do
        case "$arg" in
            --build|-b)       build_flag="--build"; passthrough+=("$arg") ;;
            --defaults)       allow_defaults=1;     passthrough+=("$arg") ;;
            --skip-preflight) skip_preflight=1;     passthrough+=("$arg") ;;
            --reindex)        reindex=1 ;;
        esac
    done

    info "Starting RAG Bootstrap..."
    require_config "$allow_defaults"
    generate_env

    # Ensure data directories exist (bind mount targets)
    ensure_data_directories

    # Validate security configuration
    validate_port_exposure

    # Preflights: free port + reachable Ollama with the embedding model pulled
    port_preflight
    if [[ "$skip_preflight" == "1" ]]; then
        warn "Skipping Ollama preflight (--skip-preflight)"
    else
        ollama_preflight
    fi

    # Echo effective resolved config right before bringing the stack up
    echo_effective_config

    trap start_failure_cleanup EXIT
    compose_up_with_port_retry "$build_flag"

    # Stored-vs-configured embedding dimension guard.
    # Default: fatal on mismatch. With --reindex (B2): offer to wipe and
    # re-embed in one flow instead of aborting with manual instructions.
    if [[ "$reindex" == "1" ]]; then
        if ! dim_guard report; then
            local stored want
            stored="$(stored_embedding_dimension)"
            want="$(env_get EMBEDDING_DIMENSION)"
            want="${want:-${CONFIG_EMBEDDING_DIM:-$DEFAULT_EMBEDDING_DIM}}"
            warn "Stale index detected (stored=${stored}, config=${want})."
            read -p "Wipe and re-embed? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                trap - EXIT
                "$rag" reset --yes
                "$rag" up ${passthrough[@]+"${passthrough[@]}"}
                "$rag" ingest
                return 0
            fi
            fatal "Reindex declined — stale index left in place.
       Manual path: ./rag reset && ./rag up && ./rag ingest"
        fi
    else
        dim_guard fatal
    fi

    wait_for_api
    trap - EXIT
    "$rag" status
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag up${NC} — Start all services  (alias: ${GREEN}start${NC})

${CYAN}Usage:${NC}
  rag up [--build|-b] [--defaults] [--skip-preflight] [--reindex]

${CYAN}Options:${NC}
  --build, -b       Rebuild containers before starting
  --defaults        Allow start without a config file (built-in defaults)
  --skip-preflight  Skip the Ollama reachability/model preflight
  --reindex         On a stale-dimension index: prompt once, then wipe,
                    restart, and re-ingest automatically

Runs config resolution + .env merge, data-dir + security preflight, port
preflight, Ollama preflight, dimension guard, then brings the stack up and
prints status.
EOF
}
