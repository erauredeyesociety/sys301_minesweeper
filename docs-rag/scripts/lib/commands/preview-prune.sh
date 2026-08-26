# =============================================================================
# commands/preview-prune.sh — `rag preview-prune` module (thin wrapper; both)
# =============================================================================
# Convenience wrapper around the UNCHANGED advisory doc-health tool
# preview_prune.py, which is designed to run INSIDE the api container (the app
# package + the sibling build_dup_clusters.py it reuses are on /src there, and
# the compose env supplies POSTGRES_PASSWORD / config). This module reproduces
# the documented in-container invocation (mirrors `rag ingest-kb`):
#
#   docker compose run --rm --no-deps \
#       -v "<scripts>:/src/scripts:ro" -v "<root>:/work:ro" \
#       api python /src/scripts/preview_prune.py <args>
#
# It only LOCATES the tool + EXECs docker compose; the tool is never modified.
# Every argument after `preview-prune` is forwarded verbatim to preview_prune.py.
#
# ADVISORY-ONLY / READ-ONLY: preview_prune.py writes nothing to the corpus, DB, or
# any doc — its only output is the manifest (stdout, or an operator-named --out).
# The `/work` mount is READ-ONLY, so use --source-dir /work/<subdir> for the
# FS-reconcile pass; a report --out that must persist wants the raw command with a
# writable mount.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "preview-prune|prune-preview|both|Advisory READ-ONLY prune MANIFEST over one KB (preview_prune.py)"
}

help() {
    cat <<'RAG_PREVIEWPRUNE_HELP'
rag preview-prune — advisory READ-ONLY prune MANIFEST over one KB (doc-health)

Thin wrapper that runs the documented in-container advisory:
  docker compose run --rm --no-deps \
      -v "<scripts>:/src/scripts:ro" -v "<root>:/work:ro" \
      api python /src/scripts/preview_prune.py <args>

READ-ONLY — moves / merges / deletes NOTHING. It enumerates a KB's live chunks and
prints a Phase-2 prune manifest (per doc / near-dup cluster: a prune-docs verdict —
keep / merge->canonical / supersede-in-place / archive->docs/archives/ / cite->path
— plus the canonical pick, INDEX.md gaps, and a PROTECT-IMMUTABLE flag). All
arguments are forwarded verbatim to preview_prune.py. Run from the instance dir
(the one holding .env + docker-compose.yml).

Note — a DEFAULT (no-flag) run emits a SUBSET of the verdict vocab: `supersede-in-place`
is RESERVED (doc EVOLUTION / conclusion-delta, a Phase-2+ signal — not emitted yet) and
`archive->docs/archives/` requires the usage-cold signal (`--heat`, which needs `--base-url`).

Usage:
  rag preview-prune --kb <name>                 # advisory manifest to stdout
  rag preview-prune --kb <name> --format json   # machine-readable
  rag preview-prune --kb <name> --star-validate # over-merge guard (recommended)
  rag preview-prune --kb <name> --source-dir /work/docs   # +ghosts/INDEX gaps

Full flag reference: `rag preview-prune --kb x` errors list them, or read
scripts/preview_prune.py. Advisory only — a human approves; git = human-only.
RAG_PREVIEWPRUNE_HELP
}

run() {
    local root opsdir cand
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    command -v docker >/dev/null 2>&1 \
        || { echo "ERROR: preview-prune: 'docker' not found on PATH" >&2; return 1; }

    # template checkout: scripts/preview_prune.py ; consumer scaffold: ops/…
    # (build_dup_clusters.py must be a sibling in the same dir — it is reused.)
    # A host-side copy is OPTIONAL: when present we overlay-mount it at /src/scripts
    # so an edited tool runs without a rebuild; when ABSENT (a fresh image-mode
    # consumer with no ops/ mount) we fall back to the copy BAKED into the image at
    # /src/scripts — the wrapper still runs out-of-box against the shipped tool.
    for cand in "${root}/scripts" "${root}/ops"; do
        if [[ -f "${cand}/preview_prune.py" ]]; then opsdir="$cand"; break; fi
    done

    # docker compose reads its compose file + .env from the instance dir; the
    # dispatcher root IS that dir. `/work:ro` lets --source-dir reference the tree.
    # The /src/scripts overlay is added ONLY when a host copy exists (below).
    #
    # MEMORY: this one-off loads chunk rows + embeddings, so it needs more headroom than
    # the SERVING api's mem cap (default 512m — which SIGKILLed the tool, rc 137). The
    # --rm one-off gets its OWN limit via RAG_ONEOFF_MEM_LIMIT (default 3g), overriding
    # the api service's deploy limit for THIS container only (the running api container is
    # untouched). Runs out-of-box — no manual `docker run --memory=…` needed.
    cd "$root"
    local -a run_args=(-v "${root}:/work:ro")
    [[ -n "${opsdir:-}" ]] && run_args+=(-v "${opsdir}:/src/scripts:ro")
    RAG_API_MEM_LIMIT="${RAG_ONEOFF_MEM_LIMIT:-3g}" exec docker compose run --rm --no-deps \
        "${run_args[@]}" \
        api python /src/scripts/preview_prune.py "$@"
}
