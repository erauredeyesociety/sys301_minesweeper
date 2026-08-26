# shellcheck shell=bash
# =============================================================================
# commands/prune.sh — module for `rag prune`  (audience: both)
# =============================================================================
# THIN wrapper around POST /api/admin/purge. All the logic — resolving KBs,
# counting ghost rows, hard-deleting Documents + Chunks — lives in the app
# (app/admin_api.py + app/purge.py). This script only AUTOMATES calling that
# endpoint: it builds the JSON body from CLI flags, curls the running instance,
# and pretty-prints the response. NO business logic here.
#
# Purge acts on INDEXED DATA ONLY (postgres rows). It NEVER touches files on
# disk. Default is DRY-RUN (report only); an explicit --apply is REQUIRED to
# delete anything.
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "prune|purge|both|Hard-delete soft-expired ghost rows from the index (dry-run by default)"
}

run() {
    # Pull in shared helpers (parse_config/resolved_port/info/warn/fatal) if the
    # module was sourced standalone (dispatcher already sources common.sh).
    if ! command -v resolved_port >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local apply=0 older_than="" kb="" orphans=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; return 0 ;;
            --apply)        apply=1; shift ;;
            --dry-run)      apply=0; shift ;;
            --orphans)      orphans=1; shift ;;
            --older-than)   [[ $# -ge 2 ]] || fatal "prune: --older-than needs a value (e.g. 7d, 12h, 3600s)"; older_than="$2"; shift 2 ;;
            --older-than=*) older_than="${1#*=}"; shift ;;
            --kb)           [[ $# -ge 2 ]] || fatal "prune: --kb needs a value (a KB name, 'primary', or 'all')"; kb="$2"; shift 2 ;;
            --kb=*)         kb="${1#*=}"; shift ;;
            -*) fatal "prune: unknown option: $1 (use --help)" ;;
            *)  fatal "prune: unexpected argument: $1 (use --help)" ;;
        esac
    done

    # --- translate a human duration (7d/12h/30m/3600s or bare seconds) → seconds
    local older_seconds=""
    if [[ -n "$older_than" ]]; then
        older_seconds="$(_prune_to_seconds "$older_than")" \
            || fatal "prune: invalid --older-than '$older_than' (use e.g. 7d, 12h, 30m, 3600s)"
    fi

    parse_config
    local port url
    port="$(resolved_port)"
    url="http://localhost:${port}/api/admin/purge"

    # --- build the JSON request body (dry_run true unless --apply) ------------
    local body
    body="$(_prune_json_body "$apply" "$older_seconds" "$kb" "$orphans")" \
        || fatal "prune: could not build request body"

    if [[ "$apply" == "1" ]]; then
        warn "APPLY mode — will HARD-DELETE expired index rows (postgres only; files on disk are untouched)."
    else
        info "DRY-RUN — reporting ghost/orphan counts only; nothing will be deleted. Re-run with --apply to delete."
    fi
    info "POST ${url}"

    local resp
    resp="$(curl -sf -X POST "$url" -H 'Content-Type: application/json' -d "$body")" \
        || fatal "prune: request failed (is the instance up? try './rag status'). Endpoint: ${url}"

    _prune_render "$resp" || { printf '%s\n' "$resp"; fatal "prune: could not parse response (raw body above)"; }
}

# --- helpers (module-local; underscore-prefixed) -----------------------------

# Convert 7d / 12h / 30m / 45s / bare-seconds → integer seconds on stdout.
_prune_to_seconds() {
    local v="$1" n unit
    if [[ "$v" =~ ^([0-9]+)([smhdSMHD]?)$ ]]; then
        n="${BASH_REMATCH[1]}"; unit="${BASH_REMATCH[2],,}"
        case "$unit" in
            s|"") printf '%s' "$n" ;;
            m)    printf '%s' "$(( n * 60 ))" ;;
            h)    printf '%s' "$(( n * 3600 ))" ;;
            d)    printf '%s' "$(( n * 86400 ))" ;;
            *)    return 1 ;;
        esac
        return 0
    fi
    return 1
}

# Emit the purge request JSON body. Args: apply older_seconds kb orphans.
_prune_json_body() {
    local apply="$1" older_seconds="$2" kb="$3" orphans="$4"
    APPLY="$apply" OLDER="$older_seconds" KB="$kb" ORPHANS="$orphans" python3 - <<'PY'
import json, os
body = {
    "dry_run": os.environ["APPLY"] != "1",
    "orphans": os.environ["ORPHANS"] == "1",
}
older = os.environ.get("OLDER", "")
if older != "":
    body["older_than_seconds"] = int(older)
kb = os.environ.get("KB", "")
if kb != "":
    body["kb"] = kb
print(json.dumps(body))
PY
}

# Pretty-print the PurgeResponse JSON passed as $1.
_prune_render() {
    RAG_RESP="$1" python3 - <<'PY'
import os, json, sys
try:
    r = json.loads(os.environ["RAG_RESP"])
except Exception:
    sys.exit(1)
dry = r.get("dry_run", True)
print()
print("RAG Prune — {}".format("DRY RUN (nothing deleted)" if dry else "APPLIED (rows hard-deleted)"))
print("=" * 60)
for t in r.get("targets", []):
    print("KB: {}".format(t.get("kb", "?")))
    print("  expired documents : {}".format(t.get("expired_documents", 0)))
    print("  expired chunks    : {}".format(t.get("expired_chunks", 0)))
    if t.get("orphans_detected") or t.get("orphans_marked"):
        print("  orphans detected  : {}".format(t.get("orphans_detected", 0)))
        if not dry:
            print("  orphans marked    : {}".format(t.get("orphans_marked", 0)))
    if not dry:
        print("  deleted documents : {}".format(t.get("deleted_documents", 0)))
        print("  deleted chunks    : {}".format(t.get("deleted_chunks", 0)))
    sample = t.get("sample_filepaths") or []
    if sample:
        print("  sample paths:")
        for p in sample:
            print("    - {}".format(p))
    print()
print("-" * 60)
print("totals: expired_docs={}  deleted_docs={}  deleted_chunks={}  orphans_detected={}".format(
    r.get("total_expired_documents", 0),
    r.get("total_deleted_documents", 0),
    r.get("total_deleted_chunks", 0),
    r.get("total_orphans_detected", 0),
))
note = r.get("note")
if note:
    print()
    print(note)
PY
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat <<EOF

${BOLD}rag prune${NC} — hard-delete soft-expired ghost rows from the search index

Thin wrapper around ${CYAN}POST /api/admin/purge${NC}. Deleted-on-disk files leave
"ghost" rows in the index (soft-expired, metadata.expired=true); reconcile
only marks them, never removes them. This reclaims that index space.

${YELLOW}Purge acts on INDEXED DATA ONLY (postgres rows) — it NEVER touches files on disk.${NC}

${CYAN}Usage:${NC}
  rag prune [--apply] [--older-than <dur>] [--kb <name>] [--orphans]

${CYAN}Options:${NC}
  ${GREEN}(default)${NC}          DRY-RUN — report expired/orphan counts + sample paths, delete nothing.
  ${GREEN}--apply${NC}            REQUIRED to actually hard-delete (safety). Without it, nothing is removed.
  ${GREEN}--older-than <dur>${NC} Only purge rows expired longer than <dur>. Accepts 7d, 12h, 30m, 45s, or bare seconds.
  ${GREEN}--kb <name>${NC}        Scope to one KB. Also 'primary' (v1 corpus) or 'all' (default: primary + every KB).
  ${GREEN}--orphans${NC}          Reconcile first — mark chunks whose source file has vanished — then purge.
  ${GREEN}-h, --help${NC}         This help.

${CYAN}Examples:${NC}
  rag prune                          # see what WOULD be purged (safe)
  rag prune --older-than 7d          # dry-run, only ghosts expired > 7 days
  rag prune --apply --older-than 7d  # actually delete those
  rag prune --apply --orphans        # reconcile vanished files, then delete their rows
EOF
}
