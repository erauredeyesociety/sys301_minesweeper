# =============================================================================
# commands/update.sh — module for `rag update`  (audience: template / maintainer)
# =============================================================================
# Pulls the CODE surface of the canonical rag-bootstrap template (UPSTREAM_PATH)
# into the fork this runs in. Reads the upstream only. Flags + env knobs
# (--apply/--dry-run, UPSTREAM_PATH, STALE_IDENTITY_PATTERNS) are supported.
#
# The synced surface = `rag` + `scripts/lib/` (the unified CLI) + app/frontend/
# client/agent_hints + the standalone ops tools + docker-compose.yml. The
# self-drift NOTE compares this module against the upstream module.
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
    echo "update||template|Sync the code surface from the canonical upstream template"
}

help() {
    cat <<'EOF'
=============================================================================
rag-bootstrap - Standard Upstream Sync (canonical template copy)
=============================================================================
Pulls the CODE surface of the canonical rag-bootstrap template
  ${UPSTREAM_PATH:-/home/devel/exudeai/rag-bootstrap}
into the fork this script lives in. READS the upstream only — never writes
to it. Ships with the template: every team's fork gets this script and can
point it at wherever their upstream copy lives via UPSTREAM_PATH.

Synced (code surface):
  app/                       (excl. __pycache__/, Dockerfile.multi-kb)
  frontend/
  client/                    (fallback_policy.py, ragq.py — consumer contract)
  agent_hints/               (HOW_TO_QUERY.md — agent-facing usage)
  rag, scripts/lib/          (unified `rag` CLI dispatcher + command modules)
  scripts/bootstrap.sh, scripts/health-check.sh
  scripts/ingest_kb.py, scripts/migrate_indexes.py, scripts/relocate_data.sh
  docker-compose.yml
  config/requirements/requirements-rerank.txt

NEVER touched (local state):
  .env                       (instance identity + runtime values)
  config/config.yaml         (local corpus list / port / name)
  .env.example               (fork-rewritten identity template)
  docs/, VERSION, README.md, .gitignore, tests/
  any fork-only scripts
  data volumes (wherever your fork's compose points them)

Usage:
  rag update            # DRY-RUN (default): show changes
  rag update --apply    # actually sync
  UPSTREAM_PATH=/path/to/rag-bootstrap rag update --apply

Optional stale-identity check: set STALE_IDENTITY_PATTERNS to a grep -E
pattern of legacy strings your fork must NOT regress to (e.g. your old port
or the upstream network name your fork renamed):
  STALE_IDENTITY_PATTERNS='10000|rag-bootstrap-net' rag update --apply

WARNING: docker-compose.yml / app|frontend files may carry FORK ADAPTATIONS
(instance identity, port band, volume indirection). A sync overwrites them
with upstream content — re-apply your adaptations before deploying (the
optional stale-identity check above helps flag regressions).
=============================================================================
EOF
}

run() {
    local UPSTREAM FORK VERSION_FILE
    UPSTREAM="${UPSTREAM_PATH:-/home/devel/exudeai/rag-bootstrap}"
    FORK="$(cd -- "${_RAG_CMD_DIR}/../../.." >/dev/null 2>&1 && pwd -P)"
    VERSION_FILE="${FORK}/VERSION"

    local MODE="dry-run"
    case "${1:-}" in
        --apply) MODE="apply" ;;
        --dry-run|"") MODE="dry-run" ;;
        -h|--help)
            help
            exit 0
            ;;
        *)
            echo "Unknown option: $1 (use --dry-run [default], --apply, or --help)" >&2
            exit 1
            ;;
    esac

    [[ -d "$UPSTREAM" ]] || { echo "ERROR: upstream not found: $UPSTREAM (set UPSTREAM_PATH)" >&2; exit 1; }
    UPSTREAM="$(cd "$UPSTREAM" && pwd)"
    if [[ "$UPSTREAM" == "$FORK" ]]; then
        echo "This copy IS the upstream (${FORK}) — nothing to sync." >&2
        echo "Run the fork's copy of this script, or set UPSTREAM_PATH to the canonical tree." >&2
        exit 0
    fi

    local RSYNC=(rsync -ai --checksum)
    [[ "$MODE" == "dry-run" ]] && RSYNC+=(--dry-run)

    echo "== $(basename "$FORK") upstream sync (${MODE}) =="
    echo "   upstream: ${UPSTREAM}"
    echo "   fork:     ${FORK}"
    echo

    echo "-- app/ (excl. __pycache__/, Dockerfile.multi-kb) --"
    "${RSYNC[@]}" --exclude='__pycache__/' --exclude='Dockerfile.multi-kb' \
        "${UPSTREAM}/app/" "${FORK}/app/"

    echo "-- frontend/ --"
    "${RSYNC[@]}" "${UPSTREAM}/frontend/" "${FORK}/frontend/"

    echo "-- client/ (excl. __pycache__/) --"
    "${RSYNC[@]}" --exclude='__pycache__/' "${UPSTREAM}/client/" "${FORK}/client/"

    echo "-- agent_hints/ --"
    "${RSYNC[@]}" "${UPSTREAM}/agent_hints/" "${FORK}/agent_hints/"

    # Unified `rag` CLI: dispatcher + command modules. Sync only if the upstream
    # carries them (graceful skip against an upstream that predates the CLI).
    echo "-- rag dispatcher + scripts/lib/ (unified CLI) --"
    if [[ -e "${UPSTREAM}/rag" ]]; then
        "${RSYNC[@]}" "${UPSTREAM}/rag" "${FORK}/"
    fi
    if [[ -d "${UPSTREAM}/scripts/lib" ]]; then
        "${RSYNC[@]}" --exclude='__pycache__/' "${UPSTREAM}/scripts/lib/" "${FORK}/scripts/lib/"
    fi

    echo "-- scripts (bootstrap.sh, health-check.sh) --"
    "${RSYNC[@]}" "${UPSTREAM}/scripts/bootstrap.sh" "${UPSTREAM}/scripts/health-check.sh" \
        "${FORK}/scripts/"

    # Standalone ops tools (called by the rag reindex/ingest-kb/relocate modules;
    # also usable directly inside a consumer). Sync only the ones present upstream.
    echo "-- scripts (ingest_kb.py, migrate_indexes.py, relocate_data.sh) --"
    for _tool in ingest_kb.py migrate_indexes.py relocate_data.sh; do
        [[ -e "${UPSTREAM}/scripts/${_tool}" ]] \
            && "${RSYNC[@]}" "${UPSTREAM}/scripts/${_tool}" "${FORK}/scripts/${_tool}"
    done

    echo "-- docker-compose.yml --"
    "${RSYNC[@]}" "${UPSTREAM}/docker-compose.yml" "${FORK}/docker-compose.yml"

    echo "-- config/requirements/ --"
    "${RSYNC[@]}" "${UPSTREAM}/config/requirements/requirements-rerank.txt" \
        "${FORK}/config/requirements/"

    # The update logic (this module) is never auto-synced by itself (rewriting a
    # running bash module is unsafe); surface drift so forks know when the
    # standard itself changed upstream.
    if [[ -f "${UPSTREAM}/scripts/lib/commands/update.sh" ]] && \
       ! cmp -s "${UPSTREAM}/scripts/lib/commands/update.sh" "${BASH_SOURCE[0]}"; then
        echo
        echo "NOTE: upstream ships a newer/different update module —"
        echo "      review and copy it manually after this run:"
        echo "      diff ${BASH_SOURCE[0]} ${UPSTREAM}/scripts/lib/commands/update.sh"
    fi

    echo
    if [[ "$MODE" == "dry-run" ]]; then
        echo "DRY-RUN complete — nothing was changed."
        echo "Lines above prefixed with '>f' are files that WOULD be updated."
        echo "Re-run with --apply to execute the sync."
        exit 0
    fi

    # --- post-apply bookkeeping + checks -------------------------------------

    # Record sync date + upstream commit in VERSION (best-effort)
    local upstream_commit upstream_dirty
    upstream_commit="$(git -C "$UPSTREAM" log -1 --format=%H 2>/dev/null || echo 'unknown')"
    upstream_dirty=""
    if [[ -n "$(git -C "$UPSTREAM" status --porcelain -- . 2>/dev/null | head -1)" ]]; then
        upstream_dirty=" + uncommitted working-tree changes"
    fi
    if [[ -f "$VERSION_FILE" ]] && grep -q '^last-upstream-sync:' "$VERSION_FILE"; then
        sed -i "s|^last-upstream-sync:.*|last-upstream-sync: $(date +%F) (commit ${upstream_commit}${upstream_dirty})|" "$VERSION_FILE"
    else
        echo "last-upstream-sync: $(date +%F) (commit ${upstream_commit}${upstream_dirty})" >> "$VERSION_FILE"
    fi
    echo "VERSION updated: last-upstream-sync -> $(date +%F)"

    # Stale-identity regression check (fork adaptations clobbered by upstream?)
    # Opt-in: forks set STALE_IDENTITY_PATTERNS to a grep -E pattern of legacy
    # strings (old port, upstream network name, ...) that must not reappear.
    echo
    echo "-- post-sync identity check --"
    if [[ -n "${STALE_IDENTITY_PATTERNS:-}" ]]; then
        local stale
        if stale=$(grep -rlnE "${STALE_IDENTITY_PATTERNS}" \
                "${FORK}/app" "${FORK}/frontend" "${FORK}/client" "${FORK}/agent_hints" \
                "${FORK}/scripts/bootstrap.sh" "${FORK}/scripts/health-check.sh" \
                "${FORK}/docker-compose.yml" 2>/dev/null); then
            echo "WARNING: upstream sync re-introduced STALE IDENTITY strings"
            echo "(pattern: ${STALE_IDENTITY_PATTERNS}) in the files below — re-apply"
            echo "your fork adaptations (identity, port band, volume indirection)"
            echo "before deploying:"
            echo "$stale" | sed 's/^/  - /'
        else
            echo "OK: no stale-identity strings in the synced surface."
        fi
    else
        echo "SKIPPED (set STALE_IDENTITY_PATTERNS='old-port|old-net-name' to enable)."
    fi

    cat << EOF

== POST-UPDATE CHECKLIST ==
 1. Review the WARNING above (if any) and re-apply fork adaptations:
    identity/port/volume indirection in docker-compose.yml,
    and any fork-local changes upstream does not carry.
 2. Read upstream UPGRADE notes for breaking changes:
      ls ${UPSTREAM}/docs/deployment/UPGRADE_*.md
 3. Validate compose resolution:   docker compose config -q
 4. Preflight:                     ./rag doctor
 5. Rebuild + restart when ready:  ./rag restart --build
 6. Re-run your kept diagnostics:  pytest tests/ (mocked suites, no docker)
EOF
}
