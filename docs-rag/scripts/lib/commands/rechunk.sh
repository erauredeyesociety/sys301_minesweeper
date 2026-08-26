# shellcheck shell=bash
# =============================================================================
# commands/rechunk.sh — module for `rag rechunk`  (audience: both)
# =============================================================================
# DESTRUCTIVE rebuild-from-source, per KB, to backfill line-spans / re-chunk an
# existing corpus. Plain re-ingest dedups on whole-document content_hash, so it
# will NOT re-chunk unchanged content — line-spans (start_line/end_line, a 0.4.x
# feature) stay null on a pre-0.4.x corpus. This command deletes a KB's indexed
# rows and re-ingests from its DECLARED SOURCE so the chunker runs again and
# spans populate.
#
# DATA-SAFETY (this is the highest-risk command in the CLI):
#   * DRY-RUN by DEFAULT — reports counts + declared sources + on-disk source
#     status and deletes NOTHING. `--apply` is REQUIRED to rebuild.
#   * REFUSE-IF-EMPTY — a KB whose declared source dir is missing or empty is
#     SKIPPED, never wiped (never destroy an index with nothing to rebuild from).
#   * PER-KB ISOLATION — targets are rebuilt SEQUENTIALLY; a non-primary KB's
#     wipe is bound to its own database (ingest_kb.py --rebuild), and primary's
#     wipe is `-d ragdb` only. A failure on one KB never affects another.
#   * NEVER `down -v`, never a server-wide wipe, never touches config/.env.
#
# Non-primary KB  -> ingest_kb.py --kb NAME --rebuild (wipes THAT KB's DB, re-ingests)
# primary (ragdb) -> psql DELETE chunks+documents in ragdb, then the v1 do_ingest
#                    (the exact flow `rag ingest` runs)
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "rechunk||both|Destructively re-chunk a KB from source to backfill line-spans (dry-run by default)"
}

run() {
    # Pull in shared helpers (parse_config/do_ingest/resolved_port/info/warn/fatal)
    # if the module was sourced standalone (dispatcher already sources common.sh).
    if ! command -v do_ingest >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local root
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    local apply=0 scope="" want_all=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; return 0 ;;
            --apply)    apply=1; shift ;;
            --dry-run)  apply=0; shift ;;
            --all)      want_all=1; shift ;;
            --kb)       [[ $# -ge 2 ]] || fatal "rechunk: --kb needs a value (a KB name or 'primary')"; scope="$2"; shift 2 ;;
            --kb=*)     scope="${1#*=}"; shift ;;
            -*) fatal "rechunk: unknown option: $1 (use --help)" ;;
            *)  fatal "rechunk: unexpected argument: $1 (use --help)" ;;
        esac
    done

    if [[ -n "$scope" && "$want_all" == "1" ]]; then
        fatal "rechunk: --kb and --all are mutually exclusive"
    fi
    # Default scope = all targets (safe; still dry-run unless --apply).

    command -v docker >/dev/null 2>&1 || fatal "rechunk: 'docker' not found on PATH"

    # docker compose reads compose file + .env from the instance dir (== root).
    cd "$root"

    parse_config   # populates CONFIG_FILE / CONFIG_INGEST_DIRS for primary

    # Non-primary rebuilds run the BAKED /src/scripts/ingest_kb.py from the image
    # (lockstep), so a host-side ingest_kb.py is NOT required. Detect one only for
    # the informational preflight; its absence is not fatal.
    local opsdir="" cand
    for cand in "${root}/ops" "${root}/scripts"; do
        if [[ -f "${cand}/ingest_kb.py" ]]; then opsdir="$cand"; break; fi
    done

    # --- enumerate targets ---------------------------------------------------
    # Each line: kind<TAB>name<TAB>database<TAB>dir1:dir2:...
    local targets
    targets="$(_rechunk_enum "${CONFIG_FILE}" "$scope" "${CONFIG_INGEST_DIRS:-./data/docs}")" \
        || fatal "rechunk: could not read knowledge bases from ${CONFIG_FILE}"
    if [[ -z "$targets" ]]; then
        if [[ -n "$scope" ]]; then
            fatal "rechunk: no such target '${scope}' (not 'primary' and not a configured knowledge base)"
        fi
        fatal "rechunk: no rechunk targets found in ${CONFIG_FILE}"
    fi

    local pg_up="" api_up=""
    pg_up="$(docker compose ps -q postgres 2>/dev/null || true)"
    api_up="$(docker compose ps -q api 2>/dev/null || true)"

    # --- header --------------------------------------------------------------
    echo
    if [[ "$apply" == "1" ]]; then
        printf '%s' "$RED"
        echo "╔══════════════════════════════════════════════════════════════════════╗"
        echo "║  rag rechunk --apply : DESTRUCTIVE REBUILD                             ║"
        echo "║  Each target KB's indexed rows are DELETED and RE-INGESTED from source.║"
        echo "║  This RE-EMBEDS every document (GPU cost; heavy on a shared Ollama).   ║"
        echo "║  A KB with a missing/empty source is SKIPPED, never wiped.            ║"
        echo "╚══════════════════════════════════════════════════════════════════════╝"
        printf '%s' "$NC"
    else
        info "rechunk DRY-RUN — reporting counts + declared source status; nothing is deleted."
        info "Re-run with --apply to rebuild (required). Scope one KB first with --kb <name>."
    fi
    echo

    # --- per-target loop (SEQUENTIAL; each isolated) -------------------------
    local line kind name database dirs
    local n_targets=0 n_rebuilt=0 n_skipped=0 n_failed=0
    # Read all targets first so `--apply` can print the confirmation up front.
    local -a T_KIND=() T_NAME=() T_DB=() T_DIRS=()
    while IFS=$'\t' read -r kind name database dirs; do
        [[ -n "$name" ]] || continue
        T_KIND+=("$kind"); T_NAME+=("$name"); T_DB+=("$database"); T_DIRS+=("$dirs")
    done <<< "$targets"
    n_targets="${#T_NAME[@]}"

    # Confirmation gate for --apply (TTY-interactive; auto-proceeds unattended).
    if [[ "$apply" == "1" ]]; then
        warn "About to rebuild ${n_targets} target(s): ${T_NAME[*]}"
        if [[ -t 0 ]]; then
            local reply=""
            printf '%sType "yes" to proceed with the destructive rebuild: %s' "$YELLOW" "$NC"
            read -r reply || reply=""
            if [[ "$reply" != "yes" ]]; then
                warn "rechunk: aborted (no changes made)."
                return 1
            fi
        else
            warn "rechunk: no TTY — proceeding non-interactively (--apply was given)."
        fi
        echo
        # Stack must be up to rebuild (do_ingest hits the API; run --rm needs env).
        [[ -n "$api_up" ]] \
            || fatal "rechunk --apply: api container not running — './rag up' first."
    fi

    local i
    for (( i = 0; i < n_targets; i++ )); do
        kind="${T_KIND[$i]}"; name="${T_NAME[$i]}"; database="${T_DB[$i]}"; dirs="${T_DIRS[$i]}"

        echo "────────────────────────────────────────────────────────────────────────"
        echo "KB: ${name}   [${kind}]   database=${database}"

        # counts BEFORE (best-effort; needs postgres up)
        local before="(postgres down — counts unavailable)"
        if [[ -n "$pg_up" ]]; then
            before="$(_rechunk_counts "$database")"
        fi
        echo "  before: ${before}"

        # declared sources + on-disk status (host view — corpus is same-path
        # bind-mounted into the container, so the host path is what ingest reads)
        local src_ok=1 d abs status any_dir=0
        echo "  declared source(s):"
        local IFS_SAVE="$IFS"; IFS=':'
        # shellcheck disable=SC2206
        local -a dir_arr=($dirs)
        IFS="$IFS_SAVE"
        if [[ "${#dir_arr[@]}" -eq 0 || ( "${#dir_arr[@]}" -eq 1 && -z "${dir_arr[0]}" ) ]]; then
            echo "    (none declared)"
            src_ok=0
        fi
        for d in "${dir_arr[@]}"; do
            [[ -n "$d" ]] || continue
            any_dir=1
            if [[ "$d" != /* ]]; then
                # Relative ingest_dir: the host resolves it against the instance
                # dir, but the container resolves against /src — the two views can
                # diverge (host says "ok" while the container ingests nothing),
                # risking a wipe-then-ingest-nothing. Refuse (skip); require an
                # absolute path for a destructive rechunk.
                status="REL-SKIP"; src_ok=0
                printf '    [%-7s] %s  (relative — use an absolute ingest_dir for rechunk)\n' "$status" "$d"
                continue
            fi
            abs="$d"
            if [[ ! -d "$abs" ]]; then
                status="MISSING"; src_ok=0
            elif [[ -z "$(find "$abs" -type f -print -quit 2>/dev/null)" ]]; then
                status="EMPTY"; src_ok=0
            else
                status="ok"
            fi
            printf '    [%-7s] %s\n' "$status" "$abs"
        done
        [[ "$any_dir" == "1" ]] || src_ok=0

        # ---- DRY-RUN: report only -------------------------------------------
        if [[ "$apply" != "1" ]]; then
            if [[ "$src_ok" == "1" ]]; then
                success "  would REBUILD (source present) — re-run with --apply"
            else
                warn "  would SKIP (source missing/empty — refuse to wipe)"
            fi
            echo
            continue
        fi

        # ---- APPLY ----------------------------------------------------------
        if [[ "$src_ok" != "1" ]]; then
            warn "  SKIP ${name}: declared source missing/empty — refusing to wipe."
            n_skipped=$((n_skipped + 1))
            echo
            continue
        fi

        # Per-KB isolation: a failure here must NOT abort the loop or touch
        # another KB. Each branch returns nonzero on failure → we log + continue.
        if _rechunk_rebuild_one "$kind" "$name" "$database" "$opsdir"; then
            local after="(postgres down)"
            [[ -n "$pg_up" ]] && after="$(_rechunk_counts "$database")"
            success "  after:  ${after}"
            # line-span confirmation: with_span is the 3rd count field
            local ws="${after##*with_span=}"
            echo "  line-spans populated: ${ws}"
            n_rebuilt=$((n_rebuilt + 1))
        else
            error "  REBUILD FAILED for ${name} — other KBs are unaffected (isolated)."
            n_failed=$((n_failed + 1))
        fi
        echo
    done

    # --- summary -------------------------------------------------------------
    echo "════════════════════════════════════════════════════════════════════════"
    if [[ "$apply" == "1" ]]; then
        echo "rechunk --apply complete: ${n_rebuilt} rebuilt, ${n_skipped} skipped, ${n_failed} failed (of ${n_targets})."
        [[ "$n_failed" -eq 0 ]] || return 1
    else
        echo "rechunk DRY-RUN complete (of ${n_targets} target(s)) — nothing was changed."
        echo "Re-run with --apply to rebuild. Test on one KB first: rag rechunk --kb <name> --apply"
    fi
}

# --- helpers (module-local; underscore-prefixed) -----------------------------

# Enumerate rechunk targets from config.yaml.
#   $1 = config file   $2 = scope ("" = all, else a KB name / 'primary')
#   $3 = CONFIG_INGEST_DIRS (colon-joined) — primary's declared source
# Emits: kind<TAB>name<TAB>database<TAB>dir1:dir2:...   (one target per line)
_rechunk_enum() {
    RAG_RC_CONFIG="$1" RAG_RC_SCOPE="$2" RAG_RC_PRIMARY_DIRS="$3" python3 - <<'PY'
import os, sys
cfg_path = os.environ["RAG_RC_CONFIG"]
scope = os.environ.get("RAG_RC_SCOPE", "")
primary_dirs = [d for d in os.environ.get("RAG_RC_PRIMARY_DIRS", "").split(":") if d]

kbs = {}
try:
    import yaml
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
    kbs = cfg.get("knowledge_bases") or {}
except Exception:
    cfg = {}
    kbs = {}

rows = []  # (kind, name, database, [dirs])

# primary (== ragdb, the v1 corpus). Its declared source is the v1
# ingestion.directories (passed in as CONFIG_INGEST_DIRS), NOT ingest_dirs.
# If knowledge_bases declares a 'primary', honor its database but keep v1 dirs.
if not scope or scope == "primary":
    prim = kbs.get("primary") or {}
    db = prim.get("database", "ragdb")
    rows.append(("primary", "primary", db, primary_dirs))

# non-primary KBs
for name, kb in (kbs or {}).items():
    if name == "primary":
        continue
    if scope and scope != name:
        continue
    kb = kb or {}
    db = kb.get("database") or ("ragdb_" + name.replace("-", "_"))
    dirs = kb.get("ingest_dirs") or []
    rows.append(("kb", name, db, list(dirs)))

# scope given but matched nothing -> emit nothing (caller errors)
for kind, name, db, dirs in rows:
    sys.stdout.write("\t".join([kind, name, str(db), ":".join(str(d) for d in dirs)]) + "\n")
PY
}

# Doc/chunk/line-span counts for one database (best-effort; postgres must be up).
# Echoes a single line: "documents=D chunks=C with_span=S" (or an error note).
_rechunk_counts() {
    local db="$1" raw
    raw="$(docker compose exec -T postgres psql -U raguser -d "$db" -tAqc \
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks), (SELECT count(*) FROM chunks WHERE metadata->>'start_line' IS NOT NULL);" \
        2>/dev/null | tr -d '[:space:]')" || raw=""
    if [[ -z "$raw" ]]; then
        echo "documents=? chunks=? with_span=? (db '${db}' unreachable)"
        return 0
    fi
    # psql -A default field separator is '|'
    local d c s
    IFS='|' read -r d c s <<< "$raw"
    echo "documents=${d:-?} chunks=${c:-?} with_span=${s:-?}"
}

# Rebuild ONE KB. Returns nonzero on failure (caller isolates + continues).
#   $1 = kind (primary|kb)  $2 = name  $3 = database  $4 = opsdir (has ingest_kb.py)
_rechunk_rebuild_one() {
    local kind="$1" name="$2" database="$3" opsdir="$4"

    if [[ "$kind" == "primary" ]]; then
        # Health-gate BEFORE the wipe: never delete the primary corpus unless
        # re-ingest can actually proceed (API healthy). Otherwise an up-but-
        # unhealthy API would leave primary wiped-but-not-reingested.
        local port; port="$(resolved_port)"
        if ! curl -sf "http://localhost:${port}/api/health" >/dev/null 2>&1; then
            error "  primary: API not healthy at :${port} — REFUSING to wipe (nothing deleted). './rag up' / wait for health, then retry."
            return 1
        fi
        info "  primary: API healthy — wiping ${database} (chunks+documents) then v1 re-ingest…"
        # Wipe is scoped to -d ragdb ONLY — never a server-wide DELETE.
        docker compose exec -T postgres psql -U raguser -d "$database" \
            -c "DELETE FROM chunks; DELETE FROM documents;" >/dev/null \
            || { error "  primary: psql wipe failed"; return 1; }
        # The SAME v1 flow `rag ingest` runs (re-chunks from source, spans populate).
        do_ingest || { error "  primary: do_ingest failed — rows were wiped; re-run './rag ingest' when healthy"; return 1; }
        return 0
    fi

    # non-primary: run the BAKED ingest_kb.py from the image (/src/scripts) so the
    # --rebuild-capable tool is always in LOCKSTEP with the running image — never
    # a possibly-stale host ops/ingest_kb.py (which may predate --rebuild). Its
    # wipe is bound to THIS KB's own dsn, so it can only touch ${database}.
    info "  ${name}: ingest_kb.py --kb ${name} --rebuild (baked tool; wipes ${database} only)…"
    docker compose run --rm --no-deps \
        api python /src/scripts/ingest_kb.py --kb "$name" --rebuild \
        || { error "  ${name}: ingest_kb.py --rebuild failed"; return 1; }
    return 0
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat <<EOF

${BOLD}rag rechunk${NC} — destructively re-chunk a KB from source (backfill line-spans)

Plain re-ingest dedups on whole-document content hash, so it will ${BOLD}not${NC}
re-chunk unchanged content — 0.4.x line-spans (start_line/end_line) stay null on
a pre-0.4.x corpus. ${BOLD}rechunk${NC} deletes a KB's indexed rows and re-ingests from
its declared source so the chunker runs again and spans populate.

${RED}DESTRUCTIVE. Re-embeds every document (GPU cost). Dry-run is the default —
--apply is REQUIRED to change anything.${NC}

${CYAN}Usage:${NC}
  rag rechunk [--kb <name> | --all] [--apply]

${CYAN}Options:${NC}
  ${GREEN}(default)${NC}     DRY-RUN — per KB: doc/chunk counts, declared sources, on-disk
                source status (ok / MISSING / EMPTY). Deletes nothing.
  ${GREEN}--kb <name>${NC}  Scope to one KB ('primary' == the v1 corpus). Test here first.
  ${GREEN}--all${NC}        All targets: primary + every configured knowledge base (default).
  ${GREEN}--apply${NC}      REQUIRED to actually rebuild. Without it, nothing is deleted.
  ${GREEN}-h, --help${NC}   This help.

${CYAN}Data-safety (this is the highest-risk command):${NC}
  ${GREEN}•${NC} DRY-RUN by default; ${GREEN}--apply${NC} required to wipe.
  ${GREEN}•${NC} A KB whose source dir is ${BOLD}missing or empty${NC} is SKIPPED, never wiped.
  ${GREEN}•${NC} Targets rebuild ${BOLD}sequentially${NC}, each isolated to its own database —
    a failure on one KB never affects another.
  ${GREEN}•${NC} Non-primary → ingest_kb.py --rebuild (that KB's DB only); primary →
    psql DELETE in ragdb then the v1 ingest. Never ${BOLD}down -v${NC}.

${CYAN}Examples:${NC}
  rag rechunk                      # dry-run report for every KB (safe)
  rag rechunk --kb primary         # dry-run just the v1 corpus
  rag rechunk --kb docs-kb --apply # rebuild one small KB first
  rag rechunk --all --apply        # rebuild everything (heavy — re-embeds all KBs)
EOF
}
