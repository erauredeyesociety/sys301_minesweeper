# shellcheck shell=bash
# =============================================================================
# commands/duplication-map.sh — module for `rag duplication-map`  (both)
# =============================================================================
# THIN wrapper around POST /api/admin/similarity-report. All the logic — the
# pgvector cosine over reused chunk embeddings, the pair/cluster building —
# lives in the app (app/admin_api.py + app/similarity_report.py). This script
# only AUTOMATES calling that endpoint: it builds the JSON body from CLI flags,
# curls the running instance, and pretty-prints the pair map. NO business logic.
#
# READ-ONLY: the report never writes, merges, or deletes anything. It is an
# advisory map so an operator can decide what to merge/cite/supersede ON DISK.
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "duplication-map|dupmap|both|Corpus-wide READ-ONLY near-duplicate document-pair map"
}

run() {
    if ! command -v resolved_port >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local threshold="" kb="" limit="" max_docs="" shingle_floor="" full="" copied_only=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; return 0 ;;
            --threshold)   [[ $# -ge 2 ]] || fatal "duplication-map: --threshold needs a value (0.0-1.0)"; threshold="$2"; shift 2 ;;
            --threshold=*) threshold="${1#*=}"; shift ;;
            --kb)          [[ $# -ge 2 ]] || fatal "duplication-map: --kb needs a value (a KB name, 'primary', or 'all')"; kb="$2"; shift 2 ;;
            --kb=*)        kb="${1#*=}"; shift ;;
            --limit)       [[ $# -ge 2 ]] || fatal "duplication-map: --limit needs a value (max pairs)"; limit="$2"; shift 2 ;;
            --limit=*)     limit="${1#*=}"; shift ;;
            --max-docs)    [[ $# -ge 2 ]] || fatal "duplication-map: --max-docs needs a value"; max_docs="$2"; shift 2 ;;
            --max-docs=*)  max_docs="${1#*=}"; shift ;;
            --shingle-floor)   [[ $# -ge 2 ]] || fatal "duplication-map: --shingle-floor needs a value (0.0-1.0)"; shingle_floor="$2"; shift 2 ;;
            --shingle-floor=*) shingle_floor="${1#*=}"; shift ;;
            --full)        full="1"; shift ;;
            --copied-only) copied_only="1"; shift ;;
            -*) fatal "duplication-map: unknown option: $1 (use --help)" ;;
            *)  fatal "duplication-map: unexpected argument: $1 (use --help)" ;;
        esac
    done

    parse_config
    local port url
    port="$(resolved_port)"
    url="http://localhost:${port}/api/admin/similarity-report"

    local body
    body="$(_dupmap_json_body "$threshold" "$kb" "$limit" "$max_docs" "$shingle_floor" "$full" "$copied_only")" \
        || fatal "duplication-map: could not build request body"

    info "POST ${url}  (READ-ONLY — no writes)"

    local resp
    resp="$(curl -sf -X POST "$url" -H 'Content-Type: application/json' -d "$body")" \
        || fatal "duplication-map: request failed (is the instance up? try './rag status'). Endpoint: ${url}"

    _dupmap_render "$resp" || { printf '%s\n' "$resp"; fatal "duplication-map: could not parse response (raw body above)"; }
}

# --- helpers (module-local; underscore-prefixed) -----------------------------

# Emit the similarity-report request JSON body.
# Args: threshold kb limit max_docs shingle_floor full copied_only.
_dupmap_json_body() {
    local threshold="$1" kb="$2" limit="$3" max_docs="$4" shingle_floor="$5" full="$6" copied_only="$7"
    THRESHOLD="$threshold" KB="$kb" LIMIT="$limit" MAX_DOCS="$max_docs" \
    SHINGLE_FLOOR="$shingle_floor" FULL="$full" COPIED_ONLY="$copied_only" python3 - <<'PY'
import json, os
body = {}
th = os.environ.get("THRESHOLD", "")
if th != "":
    try:
        body["threshold"] = float(th)
    except ValueError:
        raise SystemExit("duplication-map: --threshold must be a number 0.0-1.0")
kb = os.environ.get("KB", "")
if kb != "":
    body["kb"] = kb
for name, key in (("LIMIT", "limit"), ("MAX_DOCS", "max_docs")):
    val = os.environ.get(name, "")
    if val != "":
        try:
            body[key] = int(val)
        except ValueError:
            raise SystemExit(f"duplication-map: --{key.replace('_','-')} must be an integer")
sf = os.environ.get("SHINGLE_FLOOR", "")
if sf != "":
    try:
        body["shingle_floor"] = float(sf)
    except ValueError:
        raise SystemExit("duplication-map: --shingle-floor must be a number 0.0-1.0")
if os.environ.get("FULL", "") == "1":
    body["full"] = True
if os.environ.get("COPIED_ONLY", "") == "1":
    body["copied_only"] = True
print(json.dumps(body))
PY
}

# Pretty-print the SimilarityResponse JSON passed as $1.
_dupmap_render() {
    RAG_RESP="$1" python3 - <<'PY'
import os, json, sys
try:
    r = json.loads(os.environ["RAG_RESP"])
except Exception:
    sys.exit(1)
print()
print("RAG Duplication Map — READ-ONLY (threshold >= {})".format(r.get("threshold")))
print("=" * 66)
for rep in r.get("reports", []):
    print("KB: {}   docs_sampled={}  pairs_found={}".format(
        rep.get("kb", "?"), rep.get("docs_sampled", 0), rep.get("pairs_found", 0)))
    pairs = rep.get("pairs") or []
    if not pairs:
        print("  (no document pairs at or above threshold)")

    def _verdict_col(p):
        # None → classifier not run (classify=false). Else map to a short label.
        v = p.get("verdict")
        if v is None:
            return None
        return {"copy-paste": "COPY", "citation": "cite", "same-topic": "topic"}.get(v, str(v))

    for p in pairs:
        a = p.get("doc_a", {}) or {}
        b = p.get("doc_b", {}) or {}
        score = p.get("score")
        mean = p.get("mean_score")
        overlap = p.get("overlap_count")
        hint = p.get("shared_topic_hint")
        vcol = _verdict_col(p)
        head = "  [score {:<6} mean {:<6} overlaps {}".format(
            "{:.4f}".format(score) if isinstance(score, (int, float)) else str(score),
            "{:.4f}".format(mean) if isinstance(mean, (int, float)) else str(mean),
            overlap if overlap is not None else "?")
        if vcol is not None:
            marker = p.get("matched_marker")
            jac = p.get("shingle_jaccard")
            head += "  verdict {:<5}".format(vcol)
            if isinstance(jac, (int, float)):
                head += " jaccard {:.2f}".format(jac)
            if marker:
                head += " ({})".format(marker)
        head += "]"
        print(head)
        print("      A: {}".format(a.get("filepath") or a.get("filename") or a.get("document_id")))
        print("      B: {}".format(b.get("filepath") or b.get("filename") or b.get("document_id")))
        if hint:
            print("      shared topic hint: {}".format(hint))
    print()
print("-" * 66)
print("total pairs found: {}".format(r.get("total_pairs_found", 0)))
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

${BOLD}rag duplication-map${NC} — corpus-wide READ-ONLY near-duplicate document-pair map

Thin wrapper around ${CYAN}POST /api/admin/similarity-report${NC}. Reuses the existing
chunk embeddings + pgvector cosine to surface overly-similar document PAIRS, so
you can decide what to merge / cite / supersede ${BOLD}on disk${NC}.

${YELLOW}READ-ONLY — nothing is written, merged, or deleted. Advisory only.${NC}

Each pair also carries a ${BOLD}VERDICT${NC} from the cited-vs-copied classifier:
${GREEN}COPY${NC} = verbatim copy-paste w/ no provenance (prune/merge candidate),
${GREEN}cite${NC} = a legit reference (keep), ${GREEN}topic${NC} = same topic, independently written.

${CYAN}Usage:${NC}
  rag duplication-map [--threshold <0.0-1.0>] [--kb <name>] [--limit N]
                      [--max-docs N] [--full] [--copied-only] [--shingle-floor <0.0-1.0>]

${CYAN}Options:${NC}
  ${GREEN}--threshold <n>${NC}     Min doc-pair (max cross-doc chunk) cosine to report a pair. Default 0.85.
  ${GREEN}--kb <name>${NC}         Scope to one KB. Also 'primary' (v1 corpus) or 'all' (default: primary + every KB).
  ${GREEN}--limit N${NC}           Max pairs returned per KB (strongest first). Default 100.
  ${GREEN}--max-docs N${NC}        Max documents sampled per KB (default 500 / SIMILARITY_REPORT_MAX_DOCS).
  ${GREEN}--full${NC}              Cover the WHOLE corpus, not the max-docs sample (bounded; slower).
  ${GREEN}--copied-only${NC}       Show only COPY (copy-paste) pairs — the prune candidates.
  ${GREEN}--shingle-floor <n>${NC} Copy-candidate lexical-overlap floor (default 0.6). Higher = stricter.
  ${GREEN}-h, --help${NC}          This help.

${CYAN}Examples:${NC}
  rag duplication-map                    # pairs at cosine >= 0.85, with verdicts
  rag duplication-map --threshold 0.92   # tighter — only very close pairs
  rag duplication-map --kb primary       # just the v1 corpus
  rag duplication-map --full --copied-only  # every copy-paste in the whole corpus
EOF
}
