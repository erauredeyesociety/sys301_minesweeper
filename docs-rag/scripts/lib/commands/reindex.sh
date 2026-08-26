# =============================================================================
# commands/reindex.sh — `rag reindex` module (thin wrapper; audience: both)
# =============================================================================
# Convenience wrapper around the UNCHANGED search-index migration tool
# scripts/migrate_indexes.py (consumer scaffolds carry it at ops/). This module
# only LOCATES and EXECs that tool, forwarding every argument verbatim; the tool
# itself is never modified. Running `scripts/migrate_indexes.py --all-kbs`
# directly keeps working exactly as documented.
#
# The tool self-inserts its parent.parent into sys.path (imports app.config),
# so cwd is irrelevant to import resolution here.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect
# free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "reindex||both|Add/refresh FTS+HNSW search indexes on existing DBs (migrate_indexes.py)"
}

help() {
    cat <<'RAG_REINDEX_HELP'
rag reindex — add/refresh the search indexes on EXISTING rag-bootstrap databases

Thin wrapper around scripts/migrate_indexes.py (consumer: ops/migrate_indexes.py).
All arguments are forwarded verbatim to that tool. Idempotent + safe to re-run;
fresh databases already get these indexes at init time.

Common invocations (flags belong to migrate_indexes.py):
  rag reindex --database ragdb          # a single database
  rag reindex --all-kbs                 # every ragdb* logical KB on the server
  rag reindex --all-kbs --host 127.0.0.1 --port 15499 --maintenance-work-mem 256MB

Full flag reference: `python scripts/migrate_indexes.py --help`.
RAG_REINDEX_HELP
}

run() {
    local root tool py cand
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    # Show module help for a bare -h/--help (avoids surfacing an import error
    # from the tool when app deps are not on this host's PATH).
    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    # template layout: scripts/migrate_indexes.py ; consumer scaffold: ops/…
    for cand in "${root}/scripts/migrate_indexes.py" "${root}/ops/migrate_indexes.py"; do
        if [[ -f "$cand" ]]; then tool="$cand"; break; fi
    done
    [[ -n "${tool:-}" ]] \
        || { echo "ERROR: reindex: migrate_indexes.py not found (looked in scripts/ and ops/)" >&2; return 1; }

    if command -v python3 >/dev/null 2>&1; then
        py="python3"
    elif command -v python >/dev/null 2>&1; then
        py="python"
    else
        echo "ERROR: reindex: no python3/python interpreter on PATH" >&2
        return 1
    fi

    exec "$py" "$tool" "$@"
}
