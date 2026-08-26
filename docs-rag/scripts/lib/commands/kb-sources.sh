# shellcheck shell=bash
# =============================================================================
# commands/kb-sources.sh — module for `rag kb-sources`  (both)
# =============================================================================
# THIN wrapper around GET /api/admin/kb-provenance. All the logic — the per-KB
# config-vs-DB provenance diff, the drift flags — lives in the app
# (app/admin_api.py). This script only AUTOMATES calling that endpoint: it curls
# the running instance and pretty-prints WHERE each KB's content comes from
# (declared source) vs what is ACTUALLY indexed (from the DB). NO business logic.
#
# READ-ONLY: the endpoint issues ONLY SELECTs — it never writes, marks, or
# deletes. This surfaces provenance + drift so an operator can de-risk a reindex
# and support the cite-not-copy initiative.
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "kb-sources|provenance,kb-provenance|both|Show per-KB declared source vs actually-indexed provenance (READ-ONLY)"
}

run() {
    if ! command -v resolved_port >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local kb="" as_json=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; return 0 ;;
            --kb)   [[ $# -ge 2 ]] || fatal "kb-sources: --kb needs a value (a KB name, 'primary', or 'all')"; kb="$2"; shift 2 ;;
            --kb=*) kb="${1#*=}"; shift ;;
            --json) as_json=1; shift ;;
            -*) fatal "kb-sources: unknown option: $1 (use --help)" ;;
            *)  fatal "kb-sources: unexpected argument: $1 (use --help)" ;;
        esac
    done

    parse_config
    local port url
    port="$(resolved_port)"
    url="http://localhost:${port}/api/admin/kb-provenance"
    # GET endpoint — pass the scope as a query string, never a POST body.
    [[ -n "$kb" ]] && url="${url}?kb=${kb}"

    info "GET ${url}  (READ-ONLY — no writes)"

    local resp
    resp="$(curl -sf "$url")" \
        || fatal "kb-sources: request failed (is the instance up? try './rag status'). Endpoint: ${url}"

    if [[ -n "$as_json" ]]; then
        printf '%s\n' "$resp"
        return 0
    fi

    _kbsources_render "$resp" || { printf '%s\n' "$resp"; fatal "kb-sources: could not parse response (raw body above)"; }
}

# --- helpers (module-local; underscore-prefixed) -----------------------------

# Pretty-print the KBProvenanceResponse JSON passed as $1 as an aligned table.
_kbsources_render() {
    RAG_RESP="$1" python3 - <<'PY'
import os, json, sys

try:
    r = json.loads(os.environ["RAG_RESP"])
except Exception:
    sys.exit(1)

targets = r.get("targets", []) or []

def shorten(s, n=40):
    s = str(s)
    return s if len(s) <= n else "…" + s[-(n - 1):]

def drift_flag(d):
    d = d or {}
    if d.get("error"):
        return "ERROR"
    tags = []
    if d.get("declared_but_empty"):
        tags.append("declared-empty")
    if d.get("indexed_outside_declared"):
        tags.append("outside-declared")
    return ",".join(tags) if tags else "ok"

print()
print("RAG KB Provenance — READ-ONLY  (declared source vs actually-indexed)")
print("=" * 78)

rows = []
for t in targets:
    declared = t.get("declared_sources") or []
    src = declared[0] if declared else "(none declared)"
    if len(declared) > 1:
        src = "{} (+{})".format(src, len(declared) - 1)
    counts = "{}d/{}c".format(t.get("documents", 0), t.get("chunks", 0))
    rows.append((
        str(t.get("kb", "?")),
        str(t.get("database") or "-"),
        shorten(src),
        counts,
        drift_flag(t.get("drift")),
    ))

headers = ("KB", "DATABASE", "DECLARED SOURCE", "INDEXED", "DRIFT")
widths = [len(h) for h in headers]
for row in rows:
    for i, cell in enumerate(row):
        widths[i] = max(widths[i], len(cell))

def fmt(cols):
    return "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols))

print(fmt(headers))
print("  ".join("-" * w for w in widths))
for row in rows:
    print(fmt(row))

# Per-KB detail: declared roots that are empty + DB-discovered indexed roots,
# so container-vs-host path mismatches are visible (not just a bare drift flag).
for t in targets:
    drift = t.get("drift") or {}
    err = drift.get("error")
    declared = t.get("declared_sources") or []
    indexed = t.get("indexed_roots") or []
    interesting = err or drift.get("declared_but_empty") or drift.get("indexed_outside_declared")
    if not interesting:
        continue
    print()
    print("• {} [{}]".format(t.get("kb", "?"), t.get("database") or "-"))
    if err:
        print("    ERROR (unreachable — reported, response not failed): {}".format(err))
        continue
    if declared:
        print("    declared sources:")
        for d in declared:
            print("      - {}".format(d))
    else:
        print("    declared sources: (none — all {} docs are unmatched)".format(t.get("documents", 0)))
    if drift.get("declared_but_empty"):
        print("    ! declared source(s) present but 0 indexed docs fall under them")
    if drift.get("indexed_outside_declared"):
        print("    ! {} indexed doc(s) outside declared roots (possible path drift)".format(
            t.get("unmatched_documents", 0)))
    if indexed:
        print("    actually-indexed roots (from DB):")
        for ir in indexed[:10]:
            print("      {:>7}  {}".format(ir.get("documents", 0), ir.get("root")))

totals = r.get("totals") or {}
print()
print("-" * 78)
print("total: {} KB(s), {} document(s), {} chunk(s)".format(
    totals.get("total_kbs", len(targets)),
    totals.get("total_documents", 0),
    totals.get("total_chunks", 0)))
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

${BOLD}rag kb-sources${NC} — where each KB's content comes from (declared vs indexed)

Thin wrapper around ${CYAN}GET /api/admin/kb-provenance${NC}. For each knowledge base it
shows the ${BOLD}declared source${NC} (config \`ingest_dirs\`; for \`primary\` the v1
\`ingestion.directories\`/\`DOCS_PATH\`) next to what is ${BOLD}actually indexed${NC} in that
KB's postgres DB (document + chunk counts, real filepath roots), with drift flags.

${YELLOW}READ-ONLY — the endpoint issues only SELECTs. Nothing is written or deleted.${NC}

${CYAN}Usage:${NC}
  rag kb-sources [--kb <name>] [--json]

${CYAN}Options:${NC}
  ${GREEN}--kb <name>${NC}  Scope to one KB. Also 'primary' (v1 corpus) or 'all' (default: primary + every KB).
  ${GREEN}--json${NC}       Print the raw JSON response instead of the table.
  ${GREEN}-h, --help${NC}   This help.

${CYAN}Drift flags:${NC}
  ${GREEN}declared-empty${NC}    a source is declared but 0 indexed docs fall under it.
  ${GREEN}outside-declared${NC}  indexed docs exist whose path is not under any declared source.
  ${GREEN}ERROR${NC}             this KB's DB was unreachable (reported per-KB; response not failed).

${CYAN}Examples:${NC}
  rag kb-sources                 # every KB — declared vs indexed provenance table
  rag kb-sources --kb primary    # just the v1 corpus
  rag kb-sources --kb cwm_research --json
EOF
}
