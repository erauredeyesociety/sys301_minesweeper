# shellcheck shell=bash
# =============================================================================
# rag sync — Force an immediate reconcile (canonical: sync; alias: reconcile)
# =============================================================================
# run() is the `cmd_sync` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "sync|reconcile|both|Force an immediate reconcile without a redeploy"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    # Reconcile the running corpus WITHOUT a redeploy and WITHOUT the watcher:
    # re-run the ALREADY-idempotent ingest_directory pass over the configured
    # docs root (or a given path). Because that pass reconciles, it:
    #   - adds new files,
    #   - replaces modified files (superseded chunks purged — Increment 1),
    #   - soft-expires deleted files (filtered from search immediately).
    # Unchanged files short-circuit on content-hash (cheap no-op, no re-embed).
    # This is the "pick up file changes without redeploy" path.
    parse_config

    # Reconcile drives the live API, so the stack must be up (same as ingest).
    local port
    port="$(resolved_port)"
    if ! curl -sf "http://localhost:${port}/api/health" >/dev/null 2>&1; then
        fatal "API is not running. Start services first with: ./rag up"
    fi

    info "Reconciling corpus (adds / modifies / deletes; no redeploy, no watcher)..."
    do_ingest "$@"
    echo ""
    info "Note: this manual reconcile is USUALLY unnecessary — the app runs the same"
    info "idempotent pass automatically on a periodic loop (default-ON, every"
    info "RECONCILE_INTERVAL_SECONDS=300s), so file changes self-heal within one"
    info "interval with no redeploy. Use 'sync' to force an immediate reconcile, or"
    info "when RECONCILE_ENABLED=false. ('./rag status' shows the live cadence.)"
    echo ""
    info "Per-knowledge-base reconcile (multi-KB deploys) uses the same idempotent"
    info "ingest_directory pass, scoped to one KB's logical database:"
    info "  docker compose run --rm --no-deps -v \"\$PWD/scripts:/src/scripts:ro\" \\"
    info "      api python /src/scripts/ingest_kb.py --kb <name>"
    info "Or trigger the primary reconcile over HTTP: POST /api/reconcile (202 + job_id)."
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag sync${NC} — Force an immediate reconcile  (alias: ${GREEN}reconcile${NC})

${CYAN}Usage:${NC}
  rag sync [path...]

Re-runs the idempotent ingest to pick up added / modified / deleted files
without a redeploy or the watcher. Usually optional — the app self-heals on a
periodic reconcile loop (default-ON, RECONCILE_INTERVAL_SECONDS=300). Requires
the stack to be running.
EOF
}
