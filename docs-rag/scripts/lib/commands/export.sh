# =============================================================================
# commands/export.sh — module for `rag export`  (audience: template / maintainer)
# =============================================================================
# Option-A code-only source export (single-KB): copies ONLY the CODE surface of
# this canonical repo into a target dir, driven entirely by the CONSUMER_MANIFEST
# allowlist.
#
# Module contract: defines cmd_meta / help / run and nothing else at top level;
# sourcing is side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

# Locate the shared lib relative to this module (scripts/lib/commands/<cmd>.sh).
_RAG_CMD_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
# shellcheck source=../common.sh disable=SC1091
[[ -f "${_RAG_CMD_DIR}/../common.sh" ]] && source "${_RAG_CMD_DIR}/../common.sh"

# name | aliases(csv) | audience(both|consumer|template) | one-line summary
cmd_meta() {
    echo "export||template|Code-only source export of a single-KB consumer (manifest-driven)"
}

help() {
    cat <<'EOF'
=============================================================================
rag export — Option-A code-only source export (single-KB)
=============================================================================
Copies ONLY the CODE surface of this canonical repo into a target directory,
driven entirely by the CONSUMER_MANIFEST allowlist (the single source of truth
for "what is code"). Never copies docs/, tests/, results/, monitoring, local
state, or the multi-KB Dockerfile. The exported tree is a full-source SINGLE-KB
consumer (multi-KB is image-mode only — see docs/deployment/DISTRIBUTION.md).

Usage:
  rag export <target-dir> [--dry-run|--apply]

  --dry-run   (DEFAULT) list what WOULD be copied; change nothing.
  --apply     actually copy.
  -h,--help   this help.

The manifest lists INCLUDE paths (code) and "!"-prefixed EXCLUDE paths. This
script translates them into rsync filter rules, so editing CONSUMER_MANIFEST is
the ONLY place the export surface is defined.
=============================================================================

EOF
}

run() {
    local REPO_ROOT MANIFEST
    REPO_ROOT="$(cd -- "${_RAG_CMD_DIR}/../../.." >/dev/null 2>&1 && pwd -P)"
    MANIFEST="${REPO_ROOT}/CONSUMER_MANIFEST"

    die() { echo "ERROR: $*" >&2; exit 1; }

    local MODE="dry-run"
    local TARGET=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; exit 0 ;;
            --dry-run) MODE="dry-run"; shift ;;
            --apply)   MODE="apply"; shift ;;
            -*) die "unknown option: $1 (use --help)" ;;
            *)  [[ -z "$TARGET" ]] || die "unexpected extra argument: $1"; TARGET="$1"; shift ;;
        esac
    done

    [[ -n "$TARGET" ]] || { help; echo >&2; die "target directory required"; }
    case "$TARGET" in *".."*) die "invalid target: must not contain '..'";; esac
    [[ -f "$MANIFEST" ]] || die "manifest not found: ${MANIFEST}"

    # --- build rsync filter rules from the manifest --------------------------
    # ORDER (rsync first-match-wins): safety excludes → manifest excludes →
    # descend-all-dirs → manifest includes → exclude-the-rest. --prune-empty-dirs
    # drops any directory left with no allowlisted file.
    local RULES=()
    local d line pat
    # Safety excludes: VCS + runtime state that must never be exported and is not
    # worth walking (empty-prune would drop them anyway; this is faster + explicit).
    for d in /.git/ /data/ /.pytest_cache/ /consumers/; do
        RULES+=( "--exclude=$d" )
    done

    # Parse manifest EXCLUDES (must precede includes so they win).
    while IFS= read -r line; do
        line="${line%%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        [[ "$line" == !* ]] || continue
        pat="${line#!}"
        if [[ "$pat" == \*\** ]]; then
            RULES+=( "--exclude=$pat" )        # unanchored (e.g. **/__pycache__/)
        else
            RULES+=( "--exclude=/$pat" )       # anchor at transfer root
        fi
    done < "$MANIFEST"

    # Descend into all directories; unwanted ones are already excluded above or
    # pruned when empty.
    RULES+=( "--include=*/" )

    # Parse manifest INCLUDES.
    while IFS= read -r line; do
        line="${line%%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        [[ "$line" == !* ]] && continue
        if [[ "$line" == */ ]]; then
            RULES+=( "--include=/${line%/}/**" )   # directory (recursive)
        else
            RULES+=( "--include=/$line" )          # single file
        fi
    done < "$MANIFEST"

    # Exclude everything else.
    RULES+=( "--exclude=*" )

    local RSYNC=( rsync -a --prune-empty-dirs "${RULES[@]}" )
    [[ "$MODE" == "dry-run" ]] && RSYNC+=( -n -i )

    echo "== code-only consumer export (${MODE}) ==" >&2
    echo "   source: ${REPO_ROOT}" >&2
    echo "   target: ${TARGET}" >&2
    echo "   manifest: ${MANIFEST}" >&2
    echo >&2

    [[ "$MODE" == "apply" ]] && mkdir -p "$TARGET"
    "${RSYNC[@]}" "${REPO_ROOT}/" "${TARGET}/"

    echo >&2
    if [[ "$MODE" == "dry-run" ]]; then
        echo "DRY-RUN complete — nothing copied. Lines above are what WOULD copy." >&2
        echo "Re-run with --apply to execute." >&2
    else
        echo "Exported code-only single-KB consumer to: ${TARGET}" >&2
        echo "  next: create a .env (see .env.example) and run ./rag up" >&2
    fi
}
