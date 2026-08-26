# =============================================================================
# commands/cite-check.sh — `rag cite-check` module (thin wrapper; both)
# =============================================================================
# Convenience wrapper around the UNCHANGED advisory doc-health tool cite_check.py,
# which is designed to run INSIDE the api container (it reuses the app package's
# embedding + search path, and the compose env supplies POSTGRES_PASSWORD /
# config / the Ollama endpoint). This module reproduces the documented
# in-container invocation (mirrors `rag ingest-kb`):
#
#   docker compose run --rm --no-deps \
#       -v "<scripts>:/src/scripts:ro" -v "<root>:/work:ro" \
#       api python /src/scripts/cite_check.py --doc /work/<path> --kb <name>
#
# It only LOCATES the tool + EXECs docker compose; the tool is never modified.
# Every argument after `cite-check` is forwarded verbatim to cite_check.py.
#
# ADVISORY-FIRST: the DEFAULT path writes nothing — it prints the proposed
# cross-references + bibliography block. Reference --doc by its in-container path
# under the READ-ONLY /work mount (e.g. --doc /work/docs/findings/new.md).
# `--apply` (the ONE write mode — it touches ONLY the Sources: bib block, never
# the body) needs a WRITABLE mount, so run --apply via the raw docker command with
# `-v "$PWD/docs:/docs"` (no :ro). NO SELF-POISONING: cite_check.py never ingests
# --doc into any KB.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "cite-check|citecheck|both|Advisory cross-reference + bibliography machine over one KB (cite_check.py)"
}

help() {
    cat <<'RAG_CITECHECK_HELP'
rag cite-check — advisory cross-reference + bibliography machine (doc-health)

Thin wrapper that runs the documented in-container advisory:
  docker compose run --rm --no-deps \
      -v "<scripts>:/src/scripts:ro" -v "<root>:/work:ro" \
      api python /src/scripts/cite_check.py <args>

ADVISORY-FIRST — the default PRINTS proposed cross-references (in the existing
[text](path) + [[RAG:<path>#<chunk>]] grammar) folded into a machine-managed
Sources: bibliography block; it writes NOTHING. For each substantive claim in
--doc it retrieves top-k chunks from --kb (query-only embed) and confirms a real
cross-reference via a pluggable confirmer. All arguments are forwarded verbatim to
cite_check.py. Reference --doc by its in-container path under /work.

Usage (advisory, read-only):
  rag cite-check --doc /work/docs/findings/new.md --kb primary
  rag cite-check --doc /work/docs/findings/new.md --kb primary --format json

--apply (the one write mode: appends/replaces ONLY the Sources: bib block, never
the body; refused on immutable/triad docs) needs a writable mount — run it raw:
  docker compose run --rm --no-deps -v "$PWD/scripts:/src/scripts:ro" \
      -v "$PWD/docs:/docs" \
      api python /src/scripts/cite_check.py --doc /docs/findings/new.md --kb primary --apply

FAIL-OPEN (never blocks a write) · NO SELF-POISONING (reads the KB only) ·
ROUTE-BY-TAXONOMY. Advisory only — git = human-only.
RAG_CITECHECK_HELP
}

run() {
    local root opsdir cand
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    command -v docker >/dev/null 2>&1 \
        || { echo "ERROR: cite-check: 'docker' not found on PATH" >&2; return 1; }

    # template checkout: scripts/cite_check.py ; consumer scaffold: ops/…
    for cand in "${root}/scripts" "${root}/ops"; do
        if [[ -f "${cand}/cite_check.py" ]]; then opsdir="$cand"; break; fi
    done
    [[ -n "${opsdir:-}" ]] \
        || { echo "ERROR: cite-check: cite_check.py not found (looked in scripts/ and ops/)" >&2; return 1; }

    # docker compose reads its compose file + .env from the instance dir; the
    # dispatcher root IS that dir. `/work:ro` exposes the doc tree for --doc; the
    # advisory default writes nothing (see help for the --apply raw command).
    #
    # MEMORY: this one-off embeds claims + retrieves corpus chunks, so it needs more
    # headroom than the SERVING api's mem cap (default 512m — which SIGKILLed the tool,
    # rc 137). The --rm one-off gets its OWN limit via RAG_ONEOFF_MEM_LIMIT (default 3g),
    # overriding the api service's deploy limit for THIS container only (the running api
    # container is untouched). Runs out-of-box — no manual `docker run --memory=…` needed.
    cd "$root"
    RAG_API_MEM_LIMIT="${RAG_ONEOFF_MEM_LIMIT:-3g}" exec docker compose run --rm --no-deps \
        -v "${opsdir}:/src/scripts:ro" \
        -v "${root}:/work:ro" \
        api python /src/scripts/cite_check.py "$@"
}
