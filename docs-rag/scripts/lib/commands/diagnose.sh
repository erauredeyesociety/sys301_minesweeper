# shellcheck shell=bash
# =============================================================================
# rag diagnose — one-shot health + placement diagnostics for a live instance
# =============================================================================
# A lightweight companion to `rag doctor`. Where `doctor` is a PRE-flight (is
# this host fit to START a stack?), `diagnose` is a POST-deploy checkup of a
# RUNNING instance and its data placement:
#
#   * API /api/health liveness + component status
#   * corpus counts (/api/status) + per-KB doc/chunk counts + KB health
#   * root disk usage vs the 80% ceiling
#   * DATA LOCATION: mounted drive vs root partition, and symlinks in the path
#   * inotify instances used vs the per-user cap (reuses doctor's check)
#   * self-healing reconcile posture (RECONCILE_ENABLED / interval)
#   * distribution mode: image-mode consumer vs source fork
#   * Ollama reachability
#
# It reuses common.sh / lifecycle.sh helpers (resolved_port, host_ollama_url,
# inotify_headroom_check, env_get, …) and prints a PASS/WARN/FAIL summary.
# Auto-registers via the dispatcher's scripts/lib/commands/*.sh glob.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "diagnose|diag|both|Post-deploy checkup: API, KBs, disk, data location, ollama"
}

# --- PASS/WARN/FAIL tally (module-local; reset at the top of run) -------------
_DIAG_PASS=0
_DIAG_WARN=0
_DIAG_FAIL=0

_diag_pass() { _DIAG_PASS=$((_DIAG_PASS + 1)); success "$*"; }
_diag_warn() { _DIAG_WARN=$((_DIAG_WARN + 1)); warn "$*"; }
_diag_fail() { _DIAG_FAIL=$((_DIAG_FAIL + 1)); error "$*"; }

_diag_section() { printf '\n%s%s%s\n' "${BOLD}" "$1" "${NC}"; }

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    _DIAG_PASS=0; _DIAG_WARN=0; _DIAG_FAIL=0

    # --verbose / -v appends section 10 (Metrics). Plain diagnose is unchanged.
    local verbose=0 _a
    for _a in "$@"; do
        case "$_a" in
            --verbose|-v) verbose=1 ;;
        esac
    done

    parse_config

    local port url
    port="$(resolved_port)"
    url="http://localhost:${port}"

    echo ""
    printf "${BOLD}RAG Bootstrap Diagnose${NC}  (instance: %s)\n" "${SCRIPT_DIR}"
    echo "======================"

    # -----------------------------------------------------------------------
    # 1. API liveness + component health
    # -----------------------------------------------------------------------
    _diag_section "1. API health"
    local health api_up=0
    if health=$(curl -sf --max-time 5 "${url}/api/health" 2>/dev/null); then
        api_up=1
        local overall
        overall=$(echo "$health" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
        case "${overall}" in
            healthy) _diag_pass "API healthy at ${url}" ;;
            degraded) _diag_warn "API reachable but DEGRADED at ${url}" ;;
            *) _diag_warn "API reachable; status='${overall}' at ${url}" ;;
        esac
        # Per-component lines (best-effort parse).
        echo "$health" | python3 -c "
import sys, json
h = json.load(sys.stdin)
for label, key in (('Database','database'),('Redis','redis'),('Embedding','embedding_service'),('LLM','llm')):
    v = h.get(key)
    print(f'    {label:<10} {\"OK\" if v else \"FAIL\"}')
" 2>/dev/null || true
    else
        _diag_fail "API NOT reachable at ${url}/api/health (is the stack up? './rag up')"
    fi

    # -----------------------------------------------------------------------
    # 2. Corpus counts + per-KB doc/chunk counts + KB health
    # -----------------------------------------------------------------------
    _diag_section "2. Corpus + knowledge bases"
    if [[ "$api_up" == "1" ]]; then
        # Primary/aggregate corpus counts + staleness from /api/status.
        local status_json
        if status_json=$(curl -sf --max-time 5 "${url}/api/status" 2>/dev/null); then
            echo "$status_json" | python3 -c "
import sys, json
s = json.load(sys.stdin)
print(f\"    project      : {s.get('project_name','?')}\")
print(f\"    documents    : {s.get('documents','?')}\")
print(f\"    chunks       : {s.get('chunks','?')}\")
print(f\"    embed model  : {s.get('embedding_model','?')} / dim {s.get('dimension','?')}\")
print(f\"    indexed_at   : {s.get('indexed_at') or '(never)'}\")
" 2>/dev/null && _diag_pass "Corpus status read from /api/status" \
              || _diag_warn "Could not parse /api/status payload"
        else
            _diag_warn "/api/status not reachable (older single-KB build?)"
        fi

        # KB enumeration + capability health via the multi-KB gateway.
        local kb_json
        if kb_json=$(curl -sf --max-time 5 "${url}/api/v2/knowledge-bases" 2>/dev/null) && [[ -n "$kb_json" ]]; then
            local kb_count
            kb_count=$(echo "$kb_json" | python3 -c "
import sys, json
kbs = json.load(sys.stdin)
if not isinstance(kbs, list):
    print(0); sys.exit()
for k in kbs:
    emb = 'emb' if k.get('supports_embedding') else 'no-emb'
    kw  = 'kw' if k.get('supports_keyword_search') else 'no-kw'
    print(f\"    - {k.get('name','?'):<20} type={k.get('kb_type','?'):<12} {emb},{kw}\", file=sys.stderr)
print(len(kbs))
" 2>/tmp/_diag_kb_lines) || kb_count=0
            cat /tmp/_diag_kb_lines 2>/dev/null; rm -f /tmp/_diag_kb_lines
            if [[ "${kb_count:-0}" -gt 0 ]]; then
                _diag_pass "${kb_count} knowledge base(s) registered and reachable"
            else
                _diag_warn "Multi-KB gateway returned no KBs (single-KB deploy?)"
            fi
        else
            info "    (no /api/v2 multi-KB gateway — single-KB deploy)"
        fi

        # Per-KB doc/chunk counts (best-effort): each KB is its own logical
        # postgres database. Skips cleanly when postgres is not up or a DB has
        # no documents/chunks tables. Read-only COUNT()s — safe on a live stack.
        _diag_perkb_counts
    else
        _diag_warn "Skipping corpus/KB checks — API is down"
    fi

    # -----------------------------------------------------------------------
    # 3. Root disk usage vs the 80% ceiling
    # -----------------------------------------------------------------------
    _diag_section "3. Root disk vs 80% ceiling"
    local root_use root_avail
    root_use=$(df -P / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
    root_avail=$(df -Ph / 2>/dev/null | awk 'NR==2 {print $4}')
    if [[ -z "$root_use" || ! "$root_use" =~ ^[0-9]+$ ]]; then
        _diag_warn "Could not read root (/) disk usage"
    elif (( root_use >= 90 )); then
        _diag_fail "Root (/) disk ${root_use}% used (>=90%; ${root_avail} free) — well over the 80% ceiling"
    elif (( root_use > 80 )); then
        _diag_warn "Root (/) disk ${root_use}% used (>80% ceiling; ${root_avail} free) — free space or relocate data"
    else
        _diag_pass "Root (/) disk ${root_use}% used (${root_avail} free; under 80% ceiling)"
    fi

    # -----------------------------------------------------------------------
    # 4. DATA LOCATION — mounted drive vs root partition, symlinks in the path
    # -----------------------------------------------------------------------
    _diag_section "4. Data location"
    # Inspect where the data ACTUALLY lives under the current model. The biggest,
    # most important volume is postgres (RAG_POSTGRES_VOLUME), which --data-root
    # places under RAG_DATA_ROOT on a mounted drive. The instance-relative ./data
    # is only the legacy/portable fallback and may not exist at all on a relocated
    # instance — so probe the configured volumes first and never df a path that
    # isn't there (df exits non-zero on a missing path and, under `set -euo
    # pipefail`, would abort the whole checkup before it prints its summary).
    local pg_vol data_root data_dir data_probe cand
    pg_vol="$(env_get RAG_POSTGRES_VOLUME)"
    data_root="$(env_get RAG_DATA_ROOT)"
    data_dir="${SCRIPT_DIR}/data"
    data_probe=""
    for cand in "$pg_vol" "$data_root" "$data_dir"; do
        [[ -n "$cand" && -e "$cand" ]] && { data_probe="$cand"; break; }
    done
    if [[ -z "$data_probe" ]]; then
        info "    no data directory on disk yet (RAG_POSTGRES_VOLUME='${pg_vol:-unset}', RAG_DATA_ROOT='${data_root:-unset}', ${data_dir}); created on first start — skipping location check"
    else
        # Symlink anywhere in the data path? (resolved != literal => a symlink hop.)
        local data_real
        data_real="$(realpath -m "$data_probe" 2>/dev/null || echo "$data_probe")"
        if [[ "$data_real" != "$data_probe" ]]; then
            _diag_warn "Data path is SYMLINKED: ${data_probe} -> ${data_real}. Symlinked bind-mount sources can surprise backups/relocation; prefer RAG_*_VOLUME env pointers (see .env.example) or a real mount."
        else
            _diag_pass "Data path has no symlink hops (${data_probe})"
        fi
        # Mounted drive vs root partition: compare the data device with /'s device.
        # `|| true` keeps a non-zero df (e.g. a path that vanished mid-run) from
        # aborting the checkup under `set -euo pipefail`.
        local dev_data dev_root mnt_data
        dev_data=$(df -P "$data_real" 2>/dev/null | awk 'NR==2 {print $1}' || true)
        dev_root=$(df -P /          2>/dev/null | awk 'NR==2 {print $1}' || true)
        mnt_data=$(df -P "$data_real" 2>/dev/null | awk 'NR==2 {print $6}' || true)
        if [[ -z "$dev_data" ]]; then
            _diag_warn "Could not resolve the data device for ${data_real}"
        elif [[ "$dev_data" == "$dev_root" ]]; then
            _diag_warn "Instance data is on the ROOT partition (${dev_root} at /). A large corpus/DB competes with the OS for root disk. Place data on a mounted drive: point RAG_DATA_ROOT / RAG_*_VOLUME at a path under it (see .env.example DATA VOLUME LOCATION)."
        else
            _diag_pass "Instance data is on a separate mount: ${dev_data} at ${mnt_data} (not the root partition)"
        fi
    fi
    # Report the explicit relocation pointers. `if`-form (not `&&`) so a false
    # test can never be the trailing non-zero status that trips `set -e`.
    if [[ -n "$data_root" ]]; then info "    RAG_DATA_ROOT=${data_root}"; fi
    if [[ -n "$pg_vol" ]]; then info "    RAG_POSTGRES_VOLUME=${pg_vol} (DB — the biggest volume)"; fi

    # -----------------------------------------------------------------------
    # 5. inotify headroom (reuse doctor's check) — its own PASS/WARN line
    # -----------------------------------------------------------------------
    _diag_section "5. inotify headroom"
    if inotify_headroom_check; then :; fi   # prints its own success/warn line

    # -----------------------------------------------------------------------
    # 6. Self-healing reconcile posture
    # -----------------------------------------------------------------------
    _diag_section "6. Self-healing reconcile"
    local rec_enabled rec_interval
    rec_enabled="$(env_get RECONCILE_ENABLED)"; rec_enabled="${rec_enabled,,}"
    rec_interval="$(env_get RECONCILE_INTERVAL_SECONDS)"; rec_interval="${rec_interval:-300}"
    if [[ "$rec_enabled" == "false" ]]; then
        _diag_warn "Periodic reconcile is OFF (RECONCILE_ENABLED=false). File add/modify/delete will NOT self-heal — run './rag sync' after changes, or re-enable."
    else
        _diag_pass "Periodic self-healing reconcile ON (every ${rec_interval}s; unchanged corpus = no re-embed)"
    fi

    # -----------------------------------------------------------------------
    # 7. Distribution mode: image-mode consumer vs source fork
    # -----------------------------------------------------------------------
    _diag_section "7. Distribution mode"
    local image_tag
    image_tag="$(env_get RAG_IMAGE_TAG)"
    if [[ -d "${SCRIPT_DIR}/app" ]]; then
        if [[ "$(rag_context)" == "template" ]]; then
            _diag_pass "Source mode: template checkout (app/ + maintainer surface present)"
        else
            _diag_pass "Source mode: source-export fork (app/ present, no maintainer surface)"
        fi
    elif [[ -n "$image_tag" ]]; then
        _diag_pass "Image mode: pinned image consumer (RAG_IMAGE_TAG=${image_tag}; no app/ source to drift)"
    else
        _diag_warn "Image mode: no app/ source and RAG_IMAGE_TAG unset in .env — image tag falls back to compose default; pin RAG_IMAGE_TAG for reproducible pulls."
    fi

    # -----------------------------------------------------------------------
    # 8. Ollama reachability (lightweight — reuses host_ollama_url)
    # -----------------------------------------------------------------------
    _diag_section "8. Ollama reachability"
    local ourl
    ourl="$(host_ollama_url)"
    if curl -sf --max-time 5 "${ourl}/api/tags" >/dev/null 2>&1; then
        _diag_pass "Ollama reachable at ${ourl}"
    else
        _diag_fail "Ollama NOT reachable at ${ourl} (embeddings + chat will fail). Fix: 'ollama serve', an SSH tunnel, or './rag ollama-forwarder'."
    fi

    # -----------------------------------------------------------------------
    # 9. Config validation (HONEST — consumes GET /api/admin/validate-config)
    # -----------------------------------------------------------------------
    # ONE accountable path: this is the SAME endpoint `rag validate-config`
    # calls — no second parallel bash checker. If the API is down or the
    # endpoint doesn't answer 200, config correctness is UNKNOWN, so this is a
    # FAIL (never a silent PASS). Guarded for `set -euo pipefail`.
    _diag_section "9. Config validation"
    if [[ "$api_up" == "1" ]]; then
        local vc_json vc_rc=0
        vc_json=$(curl -sf --max-time 5 "${url}/api/admin/validate-config" 2>/dev/null) || vc_rc=$?
        if [[ "$vc_rc" != "0" || -z "$vc_json" ]]; then
            _diag_fail "config validation unavailable (endpoint down or non-200) — config correctness UNKNOWN"
        else
            local vc_out=""
            vc_out=$(printf '%s' "$vc_json" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print("PARSEFAIL|could not parse validate-config response: %s" % e); sys.exit(0)
errs  = [i for i in d.get("issues", []) if i.get("severity") == "error"]
warns = [i for i in d.get("issues", []) if i.get("severity") == "warning"]
checked = d.get("checked", 0)
if d.get("valid") and not errs:
    print("VALID|config valid (%s checks)" % checked)
else:
    print("INVALID|%d config error(s) (%s checks)" % (len(errs), checked))
def line(i):
    ln = i.get("line"); return ("line %s" % ln) if ln else "line ?"
for i in errs:
    doc = i.get("doc") or ""; doc = (" [%s]" % doc) if doc else ""
    print("ERR|  %s (%s): %s -> %s%s" % (i.get("param","?"), line(i), i.get("problem",""), i.get("fix",""), doc))
for i in warns:
    print("WARN|  %s (%s): %s -> %s" % (i.get("param","?"), line(i), i.get("problem",""), i.get("fix","")))
' 2>/dev/null) || vc_out=""
            if [[ -z "$vc_out" ]]; then
                _diag_fail "config validation returned an unparseable response — config correctness UNKNOWN"
            else
                local vc_verdict
                vc_verdict=$(printf '%s\n' "$vc_out" | head -1)
                case "$vc_verdict" in
                    "VALID|"*)     _diag_pass "${vc_verdict#VALID|}" ;;
                    "INVALID|"*)   _diag_fail "${vc_verdict#INVALID|}" ;;
                    "PARSEFAIL|"*) _diag_fail "${vc_verdict#PARSEFAIL|}" ;;
                    *)             _diag_fail "config validation: unexpected verdict" ;;
                esac
                # Per-issue detail (verdict already scored one PASS/FAIL for the
                # section; print errors as error lines, warnings as warn lines).
                printf '%s\n' "$vc_out" | tail -n +2 | while IFS= read -r _dl; do
                    case "$_dl" in
                        "ERR|"*)  error "${_dl#ERR|}" ;;
                        "WARN|"*) warn  "${_dl#WARN|}" ;;
                    esac
                done
                # Fold warnings into the tally (the while-pipe runs in a subshell,
                # so bump the counter here from a plain count).
                local vc_wcount
                vc_wcount=$(printf '%s\n' "$vc_out" | grep -c '^WARN|' || true)
                if [[ "${vc_wcount:-0}" -gt 0 ]]; then
                    _DIAG_WARN=$((_DIAG_WARN + vc_wcount))
                fi
            fi
        fi
    else
        _diag_fail "config validation unavailable (API down) — config correctness UNKNOWN"
    fi

    # -----------------------------------------------------------------------
    # 10. Metrics (--verbose only) — pull-on-demand GET /api/metrics (0.5.0)
    # -----------------------------------------------------------------------
    # Display-only: does NOT score PASS/WARN/FAIL (plain diagnose semantics are
    # unchanged; --verbose just renders more). HONEST: when metrics are OFF this
    # prints "metrics disabled ..." — never a row of fabricated zeros.
    if [[ "$verbose" == "1" ]]; then
        _diag_section "10. Metrics"
        if [[ "$api_up" != "1" ]]; then
            warn "metrics unavailable (API down)"
        else
            local m_json m_rc=0
            m_json=$(curl -sf --max-time 5 "${url}/api/metrics" 2>/dev/null) || m_rc=$?
            if [[ "$m_rc" != "0" || -z "$m_json" ]]; then
                warn "metrics endpoint unavailable (older image without /api/metrics?)"
            else
                printf '%s' "$m_json" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print("  could not parse /api/metrics: %s" % e); sys.exit(0)
if not d.get("enabled"):
    print("  metrics disabled (RAG_METRICS_ENABLED=false) — enable in config + \"rag up\"")
    sys.exit(0)
print("  since %s" % d.get("since",""))
reqs = d.get("requests",{})
print("  requests: total=%s" % reqs.get("total",0))
for route, n in sorted((reqs.get("by_route") or {}).items()):
    print("    %-24s %s" % (route, n))
subs = d.get("subsystems") or {}
if subs:
    print("  subsystems (ms, since start):")
    print("    %-12s %8s %8s %8s %8s" % ("name","count","p50","p95","max"))
    for name in sorted(subs):
        s = subs[name]
        print("    %-12s %8s %8s %8s %8s" % (name, s.get("count",0), s.get("p50_ms",0), s.get("p95_ms",0), s.get("max_ms",0)))
ac = d.get("answer_cache")
if ac:
    print("  answer_cache: lookups=%s exact=%s semantic=%s misses=%s hit_rate=%s verify_fail=%s llm_ms_saved=%s" % (
        ac.get("lookups",0), ac.get("exact_hits",0), ac.get("semantic_hits",0),
        ac.get("misses",0), ac.get("hit_rate",0), ac.get("verify_fail",0), ac.get("llm_ms_saved",0)))
re = d.get("record_errors",0)
if re:
    print("  record_errors=%s (a metrics collector raised — meter degraded, requests unaffected)" % re)
slow = d.get("slow_queries") or []
if slow:
    print("  slow queries (last %d):" % len(slow))
    for q in slow[-5:]:
        print("    %s %s total=%sms spans=%s" % (q.get("ts",""), q.get("route",""), q.get("total_ms",0), q.get("spans",{})))
' 2>/dev/null || warn "  could not render /api/metrics"
            fi
        fi
    fi

    # -----------------------------------------------------------------------
    # 11. Embedding weights provenance (--verbose only) — WHICH WEIGHTS, not
    #     which tag name
    # -----------------------------------------------------------------------
    # Display-only, exactly like section 10: it scores no PASS/WARN/FAIL, so
    # plain `rag diagnose` and its exit code are unchanged.
    #
    # EMBEDDING_MODEL is a TAG and a tag is a mutable pointer. Section 2 prints
    # the tag; every guard in the app compares the tag; and the incident this
    # section exists for is a tag whose WEIGHTS were replaced underneath it while
    # every name comparison kept passing. This asks the Ollama server which blob
    # it is actually serving — a metadata call that loads no weights — and
    # compares it to EMBEDDING_MODEL_DIGEST if one is pinned.
    #
    # Unpinned is the default and is NOT reported as a problem; the observed
    # digest is printed so an operator can pin it in one copy-paste. That is the
    # bootstrap path: you cannot detect a change from a baseline you never wrote
    # down, which is exactly why the April incident was undiagnosable.
    if [[ "$verbose" == "1" ]]; then
        _diag_section "11. Embedding weights provenance"
        local emodel epin ourl2 show_json observed=""
        emodel="$(env_get EMBEDDING_MODEL)"; emodel="${emodel:-nomic-embed-text}"
        epin="$(env_get EMBEDDING_MODEL_DIGEST)"
        ourl2="$(host_ollama_url)"
        printf '  model tag   : %s\n' "$emodel"
        if show_json=$(curl -sf --max-time 5 "${ourl2}/api/show" \
                -d "{\"model\":\"${emodel}\",\"name\":\"${emodel}\"}" 2>/dev/null); then
            observed=$(printf '%s' "$show_json" | grep -oE 'blobs[/\\]sha256[-:][0-9a-f]{8,}' \
                | head -1 | grep -oE '[0-9a-f]{8,}$' || true)
        fi
        if [[ -z "$observed" ]]; then
            # NOT a clean result. "Could not read" and "matches" are different
            # facts and this section never conflates them.
            warn "  served weights UNREADABLE for '${emodel}' at ${ourl2} — cannot"
            warn "  confirm the index and the server agree. This is 'unknown', not 'fine'."
        else
            printf '  served blob : sha256:%s\n' "$observed"
            if [[ -z "$epin" ]]; then
                printf '  pin         : (none) — a tag is not a version.\n'
                printf '                To make a weights change detectable, add to .env:\n'
                printf '                  EMBEDDING_MODEL_DIGEST=%s\n' "${observed:0:12}"
                printf '                It is inert except as a comparison: nothing aborts on it.\n'
            elif [[ "$observed" == "${epin#sha256:}"* ]]; then
                printf '  pin         : %s  MATCH\n' "$epin"
            else
                error "  WEIGHTS CHANGED — pinned ${epin}, serving sha256:${observed}."
                error "  Same tag, different weights. Vectors stored before the change are"
                error "  NOT in the same embedding space as anything embedded after it."
                error "  Remedy (a decision, not a default): './rag reindex' is the only"
                error "  complete fix; pinning the old blob back buys time if it still"
                error "  exists; carrying on knowingly is defensible only while nothing"
                error "  new is being ingested. See app/embedding_provenance.py."
            fi
        fi
    fi

    # -----------------------------------------------------------------------
    # 12. Version-source consistency — do all the files stating a version agree?
    # -----------------------------------------------------------------------
    # SCORED, and always-on (not --verbose gated), because unlike sections 10
    # and 11 this one reports a defect that is already latent in the tree rather
    # than an observation about the environment.
    #
    # VERSION is a BUILD INPUT: build.sh tags the distribution images from it.
    # On 2026-07-21 it said 0.3.0 while CHANGELOG.md, README.md and the seven
    # images actually serving traffic all said 0.5.0 — so `rag build` (or the
    # `./rag up --build` that `rag clean` signs off by suggesting) would have
    # silently stamped a fresh image `0.3.0` and desynced that instance from
    # every other one on the daemon. Nothing would have errored.
    #
    # Fixing the file did not close the class; this check does. Verdicts come
    # from scripts/version_consistency.py, which distinguishes UNKNOWN ("a
    # declared source could not be read") from CONSISTENT — an unreadable source
    # is never scored as a pass, exactly as section 11 refuses to read an
    # unreadable digest as MATCH.
    _diag_section "12. Version-source consistency"
    local _vc_root _vc_script _vc_json _vc_verdict _vc_detail _vc_have=0 _vc_f
    _vc_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." >/dev/null 2>&1 && pwd -P)"
    for _vc_f in VERSION CHANGELOG.md README.md; do
        [[ -f "${_vc_root}/${_vc_f}" ]] && _vc_have=1
    done
    _vc_script="${_vc_root}/scripts/version_consistency.py"
    if (( _vc_have == 0 )); then
        # Image-mode consumer: a .env plus a compose file pinning an image tag.
        # No file here states a version, so none can disagree. Deliberately NOT
        # tallied as a PASS — nothing was verified.
        info "  not applicable — image-mode consumer carries no version sources"
        info "  (no VERSION / CHANGELOG.md / README.md). Its version is whatever"
        info "  RAG_IMAGE_TAG pins; section 7 reports that."
    elif ! command -v python3 >/dev/null 2>&1; then
        _diag_fail "version consistency UNKNOWN — python3 not on PATH, so the version sources could not be compared. Not a pass: VERSION is what 'rag build' tags images from."
    elif [[ ! -f "$_vc_script" ]]; then
        _diag_fail "version consistency UNKNOWN — version sources are present but ${_vc_script} is missing, so they could not be compared. Not a pass."
    elif ! _vc_json=$(python3 "$_vc_script" --root "$_vc_root" --json 2>/dev/null); then
        # A non-zero exit is expected on MISMATCH/UNKNOWN and still prints JSON;
        # landing here means it produced nothing usable at all.
        if [[ -z "$_vc_json" ]]; then
            _diag_fail "version consistency UNKNOWN — the checker produced no output. Not a pass."
        fi
    fi
    if [[ -n "${_vc_json:-}" ]]; then
        _vc_verdict=$(printf '%s' "$_vc_json" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print(d["verdict"])' 2>/dev/null)
        _vc_detail=$(printf '%s' "$_vc_json" | python3 -c \
            'import json,sys; d=json.load(sys.stdin); print(d["detail"])' 2>/dev/null)
        case "$_vc_verdict" in
            CONSISTENT)
                _diag_pass "version sources agree — ${_vc_detail}" ;;
            MISMATCH)
                _diag_fail "VERSION SOURCES DISAGREE — ${_vc_detail}"
                error "  Fix before building: make VERSION, the newest CHANGELOG.md"
                error "  release heading, and README.md's '**Version**:' field state"
                error "  the same number. Until then 'rag build' will tag images from"
                error "  a VERSION the rest of the repo contradicts." ;;
            UNKNOWN)
                _diag_fail "version consistency UNKNOWN — ${_vc_detail}" ;;
            NOT_APPLICABLE)
                info "  not applicable — ${_vc_detail}" ;;
            *)
                _diag_fail "version consistency UNKNOWN — unexpected verdict from the checker. Not a pass." ;;
        esac
    fi

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    _diag_section "Summary"
    printf "  %sPASS %d%s   %sWARN %d%s   %sFAIL %d%s\n" \
        "$GREEN" "$_DIAG_PASS" "$NC" \
        "$YELLOW" "$_DIAG_WARN" "$NC" \
        "$RED" "$_DIAG_FAIL" "$NC"
    echo ""
    if (( _DIAG_FAIL > 0 )); then
        error "diagnose: ${_DIAG_FAIL} FAIL — address the failures above."
        return 1
    elif (( _DIAG_WARN > 0 )); then
        warn "diagnose: ${_DIAG_WARN} warning(s) — review, but nothing is broken."
        return 0
    fi
    success "diagnose: all checks passed."
    return 0
}

# Per-KB document/chunk counts across the logical KB databases (best-effort).
# Each KB is a separate postgres database; iterate them and COUNT(*) the
# documents/chunks tables when present. No-ops cleanly when postgres is down.
_diag_perkb_counts() {
    command -v docker >/dev/null 2>&1 || return 0
    local pg pguser pgdb dbs db has row printed=0
    pg=$(docker compose ps -q postgres 2>/dev/null || true)
    [[ -z "$pg" ]] && return 0
    pguser="$(env_get POSTGRES_USER)"; pguser="${pguser:-raguser}"
    pgdb="$(env_get POSTGRES_DB)";     pgdb="${pgdb:-ragdb}"

    dbs=$(docker compose exec -T postgres psql -U "$pguser" -d "$pgdb" -tAc \
        "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres')" \
        2>/dev/null | tr -d '\r') || return 0
    [[ -z "$dbs" ]] && return 0

    while IFS= read -r db; do
        [[ -z "$db" ]] && continue
        has=$(docker compose exec -T postgres psql -U "$pguser" -d "$db" -tAc \
            "SELECT to_regclass('public.documents') IS NOT NULL AND to_regclass('public.chunks') IS NOT NULL" \
            2>/dev/null | tr -d '[:space:]')
        [[ "$has" == "t" ]] || continue
        row=$(docker compose exec -T postgres psql -U "$pguser" -d "$db" -tAc \
            "SELECT (SELECT count(*) FROM documents) || '|' || (SELECT count(*) FROM chunks)" \
            2>/dev/null | tr -d '[:space:]')
        [[ -n "$row" ]] || continue
        if (( printed == 0 )); then
            echo "    per-KB (logical database) doc/chunk counts:"
            printed=1
        fi
        printf '      %-24s docs=%-8s chunks=%s\n' "$db" "${row%%|*}" "${row#*|}"
    done <<< "$dbs"
    return 0
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag diagnose${NC} — Post-deploy checkup of a running instance  (alias: ${GREEN}diag${NC})

${CYAN}Usage:${NC}
  rag diagnose            # sections 1-9 + Summary
  rag diagnose --verbose  # also section 10 (Metrics — GET /api/metrics)

Where ${GREEN}rag doctor${NC} is a pre-flight (can this host start a stack?),
${GREEN}rag diagnose${NC} inspects a RUNNING instance and its data placement:

  1. API /api/health liveness + component status
  2. corpus counts (/api/status) + per-KB doc/chunk counts + KB health
  3. root disk usage vs the 80% ceiling
  4. data location — mounted drive vs root partition, symlinks in the path
  5. inotify instances used vs the per-user cap
  6. self-healing reconcile posture (RECONCILE_ENABLED / interval)
  7. distribution mode — image-mode consumer vs source fork
  8. Ollama reachability
  9. config validation — GET /api/admin/validate-config: PASS "config valid",
     else names each bad param + line + fix (same endpoint as ${GREEN}rag validate-config${NC})
 10. metrics (${GREEN}--verbose${NC} only) — GET /api/metrics: subsystem p50/p95, cache
     hit-rate/verify-fail, slow queries; "metrics disabled" when off (display-only,
     does not affect the PASS/WARN/FAIL tally)

Prints a PASS/WARN/FAIL summary. Exit code is non-zero only when a hard
check FAILs (API down, Ollama unreachable, root disk >=90%, invalid config).
EOF
}
