# =============================================================================
# commands/ingest-kb.sh — `rag ingest-kb` module (thin wrapper; consumer/multikb)
# =============================================================================
# Convenience wrapper around the UNCHANGED per-KB ingest tool ingest_kb.py,
# which is designed to run INSIDE the api container (the corpus is mounted there
# same-path :ro and the compose env supplies POSTGRES_PASSWORD / embedding
# settings). This module reproduces the documented in-container invocation:
#
#   docker compose run --rm --no-deps -v "<ops>:/src/scripts:ro" \
#       api python /src/scripts/ingest_kb.py --kb <name>
#
# It only LOCATES the tool + EXECs docker compose; the tool is never modified.
# Every argument after `ingest-kb` (e.g. `--kb NAME`) is forwarded verbatim.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect
# free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "ingest-kb||consumer|Ingest one KB in-container (ingest_kb.py --kb NAME)"
}

help() {
    cat <<'RAG_INGESTKB_HELP'
rag ingest-kb — ingest ONE knowledge base inside the api container (multi-KB)

Thin wrapper that runs the documented in-container ingest:
  docker compose run --rm --no-deps -v "<ops>:/src/scripts:ro" \
      api python /src/scripts/ingest_kb.py <args>

All arguments are forwarded verbatim to ingest_kb.py. Run from the consumer /
instance directory (the one holding .env + docker-compose.yml).

Usage:
  rag ingest-kb --kb <name>       # <name> is a knowledge_base from config.yaml
                                  # ('primary' is refused — owned by v1 ingest)
RAG_INGESTKB_HELP
}

run() {
    local root opsdir cand
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    command -v docker >/dev/null 2>&1 \
        || { echo "ERROR: ingest-kb: 'docker' not found on PATH" >&2; return 1; }

    # consumer scaffold: ops/ingest_kb.py ; template checkout: scripts/ingest_kb.py
    for cand in "${root}/ops" "${root}/scripts"; do
        if [[ -f "${cand}/ingest_kb.py" ]]; then opsdir="$cand"; break; fi
    done
    [[ -n "${opsdir:-}" ]] \
        || { echo "ERROR: ingest-kb: ingest_kb.py not found (looked in ops/ and scripts/)" >&2; return 1; }

    # docker compose reads its compose file + .env from the instance dir; the
    # dispatcher root IS that dir for a consumer scaffold.
    cd "$root"
    exec docker compose run --rm --no-deps \
        -v "${opsdir}:/src/scripts:ro" \
        api python /src/scripts/ingest_kb.py "$@"
}
