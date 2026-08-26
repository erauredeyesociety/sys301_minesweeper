#!/usr/bin/env bash
# =============================================================================
# commands/migrate.sh — one-command, CLEAN deployment + data migration
# =============================================================================
# Takes a deployment from an OLD shape (fork-based, and/or data living on the
# root/cramped disk or behind symlinks) to a CLEAN, image-mode consumer with
# data on a chosen drive — in ONE command, DRY-RUN by default.
#
# What "clean" means here (the standard this command produces):
#   * image-mode consumer (ZERO application source / docs) scaffolded by the
#     `new-consumer` module;
#   * DIRECT-path data volumes under --data-root — EVERY volume, postgres and
#     redis (the BIGGEST) included, so nothing large lands on the root/home disk:
#         RAG_DATA_ROOT=/mnt/quickiespace/NAME
#         RAG_POSTGRES_VOLUME=/mnt/quickiespace/NAME/postgres  (no symlink layer,
#         RAG_REDIS_VOLUME=/mnt/quickiespace/NAME/redis         no ".../docker/..."
#         RAG_DOCS_VOLUME=/mnt/quickiespace/NAME/docs           subpath layer —
#         RAG_CACHE_VOLUME=/mnt/quickiespace/NAME/cache          the DB never sits
#         RAG_LOGS_VOLUME=/mnt/quickiespace/NAME/logs            on the local disk).
#
# Usage:
#   rag migrate [--from <old-dir>] --to <new-dir> --data-root <drive-path> \
#               [--preserve-data | --fresh] [--apply] [options]
#
#   (no --apply)      DRY-RUN (default): prints the full plan — the detected OLD
#                     config, the CLEAN target, the data strategy, the bring-up /
#                     verify steps, and exactly what will be left to remove.
#                     Touches NOTHING.
#   --from <dir>      OLD deployment directory (holds its .env + compose file).
#                     Default: the current directory.
#   --to <dir>        NEW, clean consumer directory to create (must be
#                     empty/absent). REQUIRED.
#   --data-root <p>   Absolute drive path for the new DIRECT-path data volumes,
#                     e.g. /mnt/quickiespace/NAME. REQUIRED.
#   --fresh           DATA STRATEGY (default, cleanest): re-ingest from the
#                     detected source docs — regenerable embeddings, a pristine
#                     new instance; no old state is carried.
#   --preserve-data   Carry the OLD embeddings/DB + docs onto the new
#                     direct-path volumes — ONLY if the embedding model+dimension
#                     match. On mismatch this command refuses to preserve and
#                     falls back to --fresh with a clear message.
#   --apply           Execute the migration (default is dry-run).
#   --name <name>     Identity for the new instance (default: carried from the
#                     old PROJECT_NAME, else the --to basename).
#   --tag <tag>       RAG_IMAGE_TAG to pin (default: carried, else 'latest').
#   --mode single|multikb   Override the auto-detected deployment shape.
#   -y, --yes         Skip the pre-flight confirmation in --apply mode.
#   -h, --help        This help.
#
# SAFETY MODEL (abort-safe; the OLD deployment is NEVER destroyed here):
#   * Dry-run first: nothing changes until you pass --apply.
#   * The new instance is built and health-verified BEFORE anything about the
#     old one is proposed for removal.
#   * --preserve-data copies (rsync -aH) then VERIFIES (bytes + entry counts)
#     before booting the new stack; a mismatch aborts with the OLD data 100%
#     intact.
#   * This command PRINTS the exact cleanup command for the old dir / symlinks /
#     root-disk cruft — it never auto-deletes the old deployment.
# =============================================================================

# ---------------------------------------------------------------------------
# Module contract: cmd_meta (one line), run (body), help (long usage).
# Sourcing this file MUST be side-effect free — no top-level work.
# ---------------------------------------------------------------------------

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "migrate||both|Migrate an OLD deployment to a CLEAN image-mode instance on a chosen drive"
}

help() {
    # Reuse common.sh's header-usage printer when present; else inline sed.
    if declare -F print_header_usage >/dev/null 2>&1; then
        print_header_usage "${BASH_SOURCE[0]}"
    else
        sed -n '2,56p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    fi
}

run() {
    _migrate_ensure_helpers
    _migrate_parse_args "$@"
    _migrate_detect_old
    _migrate_resolve_plan
    _migrate_print_plan

    if (( MIG_APPLY )); then
        _migrate_apply
    else
        echo
        info "DRY-RUN complete — nothing was changed."
        info "Re-run with --apply to execute this migration."
    fi
}

# ===========================================================================
# Helpers (all prefixed _migrate_ / _mig* so they never collide with other
# modules; defined here but only ever CALLED from run()).
# ===========================================================================

# Fallback primitives so the module also runs in isolation (self-verify) when
# the dispatcher has not sourced common.sh. These NEVER override common.sh's
# canonical versions — each is guarded by `declare -F`.
_migrate_ensure_helpers() {
    : "${BOLD:=$'\033[1m'}"; : "${NC:=$'\033[0m'}"
    : "${RED:=$'\033[0;31m'}"; : "${GREEN:=$'\033[0;32m'}"
    : "${YELLOW:=$'\033[1;33m'}"; : "${BLUE:=$'\033[0;34m'}"
    if ! declare -F info >/dev/null 2>&1; then
        info()    { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }
    fi
    if ! declare -F success >/dev/null 2>&1; then
        success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
    fi
    if ! declare -F warn >/dev/null 2>&1; then
        warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
    fi
    if ! declare -F error >/dev/null 2>&1; then
        error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
    fi
    if ! declare -F die >/dev/null 2>&1; then
        die()     { error "$@"; exit 1; }
    fi
}

# Repo/template root (this file is scripts/lib/commands/migrate.sh).
_migrate_repo_root() { (cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd); }

# Read one KEY from an arbitrary .env file (migrate needs to read the OLD
# instance's .env AND the template defaults — common.sh's env_get binds to a
# single active .env, so this file-argument reader is migrate-local glue, not a
# duplication of that logic). Strips CRLF + one layer of quotes.
_menv_get() {
    local f="$1" k="$2" v
    v="$(grep -m1 "^${k}=" "$f" 2>/dev/null | cut -d= -f2- || true)"
    v="${v%$'\r'}"
    v="${v#\"}"; v="${v%\"}"
    v="${v#\'}"; v="${v%\'}"
    printf '%s' "$v"
}

# Resolve an OLD RAG_*_VOLUME value (raw, cur_root) to a concrete host path,
# best-effort + eval-free. Expands a leading ${RAG_DATA_ROOT}/$RAG_DATA_ROOT ref,
# anchors a bare-relative value at MIG_FROM, and returns empty on an unsupported
# $-expansion (the caller then falls back to the legacy nested path).
_mig_resolve_old_vol() {
    local raw="$1" cur_root="$2" out="$1"
    [[ -n "$raw" ]] || { printf ''; return 0; }
    out="${out/#\$\{RAG_DATA_ROOT\}/$cur_root}"
    out="${out/#\$RAG_DATA_ROOT/$cur_root}"
    case "$out" in *'$'*) printf ''; return 0 ;; esac   # unknown expansion -> fallback
    [[ "$out" = /* ]] || out="${MIG_FROM%/}/${out#./}"
    printf '%s' "${out%/}"
}

# Read a value from a config.yaml `section:\n  key: value` pair (best-effort,
# used only for detection/plan display).
_myaml_get() {
    local f="$1" section="$2" key="$3"
    awk -v s="$section" -v k="$key" '
        $0 ~ "^"s":" {inx=1; next}
        inx && /^[^[:space:]]/ {inx=0}
        inx && $1==k":" {sub(/^[[:space:]]*[A-Za-z0-9_.-]+:[[:space:]]*/,""); print; exit}
    ' "$f" 2>/dev/null
}

# List knowledge-base names under `knowledge_bases:` in a config.yaml.
_migrate_kb_names() {
    awk '
        f && /^[^[:space:]]/ {f=0}
        f && /^  [A-Za-z0-9_.-]+:[[:space:]]*$/ {gsub(/[[:space:]:]/,""); print}
        /^knowledge_bases:/ {f=1}
    ' "$1" 2>/dev/null
}

_migrate_have() { declare -F "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
_migrate_parse_args() {
    MIG_FROM="$PWD"
    MIG_TO=""
    MIG_DATA_ROOT=""
    MIG_STRATEGY="fresh"          # fresh | preserve
    MIG_APPLY=0
    MIG_NAME=""
    MIG_TAG=""
    MIG_MODE=""                   # "" => auto-detect
    MIG_ASSUME_YES=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)        help; exit 0 ;;
            --from)           MIG_FROM="${2:-}"; shift 2 ;;
            --to)             MIG_TO="${2:-}"; shift 2 ;;
            --data-root)      MIG_DATA_ROOT="${2:-}"; shift 2 ;;
            --fresh)          MIG_STRATEGY="fresh"; shift ;;
            --preserve-data)  MIG_STRATEGY="preserve"; shift ;;
            --dry-run)        shift ;;   # explicit no-op: dry-run IS the default (real run needs --apply)
            --apply)          MIG_APPLY=1; shift ;;
            --name)           MIG_NAME="${2:-}"; shift 2 ;;
            --tag)            MIG_TAG="${2:-}"; shift 2 ;;
            --mode)           MIG_MODE="${2:-}"; shift 2 ;;
            -y|--yes)         MIG_ASSUME_YES=1; shift ;;
            --)               shift; break ;;
            -*)               die "unknown option: $1 (use --help)" ;;
            *)                die "unexpected argument: $1 (use --help)" ;;
        esac
    done

    # --- required + shape validation -------------------------------------
    [[ -n "$MIG_TO" ]]        || { help; echo >&2; die "missing required --to <new-dir>"; }
    [[ -n "$MIG_DATA_ROOT" ]] || { help; echo >&2; die "missing required --data-root <drive-path>"; }

    [[ "$MIG_DATA_ROOT" = /* ]]     || die "invalid --data-root '${MIG_DATA_ROOT}': must be an ABSOLUTE path"
    [[ "$MIG_DATA_ROOT" != *".."* ]] || die "invalid --data-root: must not contain '..'"
    MIG_DATA_ROOT="${MIG_DATA_ROOT%/}"

    [[ "$MIG_TO" != *".."* ]] || die "invalid --to: must not contain '..'"
    # Absolute-ize --to for stable downstream paths (parent must exist eventually).
    case "$MIG_TO" in
        /*) : ;;
        *)  MIG_TO="${PWD%/}/${MIG_TO#./}" ;;
    esac
    MIG_TO="${MIG_TO%/}"

    [[ "$MIG_FROM" != *".."* ]] || die "invalid --from: must not contain '..'"
    [[ -d "$MIG_FROM" ]]        || die "old deployment dir not found: ${MIG_FROM} (pass --from <old-dir>)"
    MIG_FROM="$(cd "$MIG_FROM" && pwd)"

    [[ "$MIG_FROM" != "$MIG_TO" ]] || die "--from and --to must differ (refusing an in-place migration)"

    case "$MIG_STRATEGY" in fresh|preserve) ;; *) die "internal: bad strategy" ;; esac
    if [[ -n "$MIG_MODE" ]]; then
        case "$MIG_MODE" in single|multikb) ;; *) die "invalid --mode '${MIG_MODE}': expected single|multikb" ;; esac
    fi

    # --to must be empty/absent (mirrors new-consumer's refuse-overwrite).
    if [[ -e "$MIG_TO" ]]; then
        [[ -d "$MIG_TO" ]] || die "--to exists and is not a directory: ${MIG_TO}"
        [[ -z "$(ls -A "$MIG_TO" 2>/dev/null)" ]] \
            || die "--to directory is non-empty (refusing to overwrite): ${MIG_TO}"
    fi
}

# ---------------------------------------------------------------------------
# Detect the OLD deployment's config from its compose/.env (+ config.yaml).
# ---------------------------------------------------------------------------
_migrate_detect_old() {
    OLD_ENV="${MIG_FROM}/.env"
    OLD_COMPOSE=""
    for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
        [[ -f "${MIG_FROM}/${f}" ]] && { OLD_COMPOSE="${MIG_FROM}/${f}"; break; }
    done
    OLD_CONFIG=""
    for f in config/config.yaml config.yaml; do
        [[ -f "${MIG_FROM}/${f}" ]] && { OLD_CONFIG="${MIG_FROM}/${f}"; break; }
    done

    [[ -f "$OLD_ENV" || -n "$OLD_COMPOSE" ]] \
        || die "no .env or docker-compose file under ${MIG_FROM} — not a deployment dir (pass the correct --from)"

    # --- identity / port / docs / image tag ------------------------------
    OLD_NAME="$(_menv_get "$OLD_ENV" COMPOSE_PROJECT_NAME)"
    [[ -n "$OLD_NAME" ]] || OLD_NAME="$(_menv_get "$OLD_ENV" PROJECT_NAME)"

    OLD_PORT="$(_menv_get "$OLD_ENV" RAG_PORT)"
    [[ -n "$OLD_PORT" ]] || OLD_PORT="$(_menv_get "$OLD_ENV" RAG_PORT_BASE)"

    OLD_DOCS="$(_menv_get "$OLD_ENV" DOCS_PATH)"
    OLD_TAG="$(_menv_get "$OLD_ENV" RAG_IMAGE_TAG)"

    # --- data layout -----------------------------------------------------
    OLD_DATA_ROOT="$(_menv_get "$OLD_ENV" RAG_DATA_ROOT)"
    OLD_DOCS_VOL="$(_menv_get "$OLD_ENV" RAG_DOCS_VOLUME)"
    OLD_CACHE_VOL="$(_menv_get "$OLD_ENV" RAG_CACHE_VOLUME)"
    OLD_LOGS_VOL="$(_menv_get "$OLD_ENV" RAG_LOGS_VOLUME)"
    # postgres/redis (the EMBEDDINGS store). New-style deployments set explicit
    # RAG_POSTGRES_VOLUME/RAG_REDIS_VOLUME (direct-path under RAG_DATA_ROOT);
    # OLD/buggy deployments kept them nested under <dir>/data/docker/{postgres,
    # redis}. Resolve from the .env first (expanding a leading RAG_DATA_ROOT ref),
    # then fall back to the legacy nested path so BOTH source shapes migrate.
    OLD_DB_DIR="${MIG_FROM}/data/docker"      # legacy nested layout (fallback)
    OLD_POSTGRES_VOL="$(_mig_resolve_old_vol "$(_menv_get "$OLD_ENV" RAG_POSTGRES_VOLUME)" "$OLD_DATA_ROOT")"
    OLD_REDIS_VOL="$(_mig_resolve_old_vol "$(_menv_get "$OLD_ENV" RAG_REDIS_VOLUME)" "$OLD_DATA_ROOT")"
    [[ -n "$OLD_POSTGRES_VOL" ]] || OLD_POSTGRES_VOL="${OLD_DB_DIR}/postgres"
    [[ -n "$OLD_REDIS_VOL"    ]] || OLD_REDIS_VOL="${OLD_DB_DIR}/redis"

    # --- embedding triple (env first, config fallback) -------------------
    OLD_MODEL="$(_menv_get "$OLD_ENV" EMBEDDING_MODEL)"
    OLD_DIM="$(_menv_get "$OLD_ENV" EMBEDDING_DIMENSION)"
    if [[ -z "$OLD_MODEL" && -n "$OLD_CONFIG" ]]; then
        OLD_MODEL="$(_myaml_get "$OLD_CONFIG" embedding model)"
        OLD_DIM="$(_myaml_get "$OLD_CONFIG" embedding dimension)"
    fi

    # --- mode: multikb if a config.yaml declares knowledge_bases ---------
    OLD_MODE="single"
    OLD_KBS=""
    if [[ -n "$OLD_CONFIG" ]] && grep -qE '^knowledge_bases:' "$OLD_CONFIG" 2>/dev/null; then
        OLD_MODE="multikb"
        OLD_KBS="$(_migrate_kb_names "$OLD_CONFIG" | paste -sd, - 2>/dev/null || true)"
    elif [[ -n "$OLD_COMPOSE" ]] && grep -qiE 'multi[-_]kb' "$OLD_COMPOSE" 2>/dev/null; then
        OLD_MODE="multikb"
    fi
}

# ---------------------------------------------------------------------------
# Resolve the plan: carry-forward values + the chosen data strategy.
# ---------------------------------------------------------------------------
_migrate_resolve_plan() {
    # --- carry-forward identity / port / tag / mode ----------------------
    NEW_NAME="$MIG_NAME"
    [[ -n "$NEW_NAME" ]] || NEW_NAME="$OLD_NAME"
    [[ -n "$NEW_NAME" ]] || NEW_NAME="$(basename "$MIG_TO")"

    NEW_PORT="$OLD_PORT"
    NEW_TAG="$MIG_TAG"
    [[ -n "$NEW_TAG" ]] || NEW_TAG="$OLD_TAG"
    [[ -n "$NEW_TAG" ]] || NEW_TAG="latest"

    NEW_MODE="$MIG_MODE"
    [[ -n "$NEW_MODE" ]] || NEW_MODE="$OLD_MODE"

    NEW_DOCS="$OLD_DOCS"

    # --- new embedding triple = clean template defaults ------------------
    local tenv; tenv="$(_migrate_repo_root)/templates/consumer.env.template"
    NEW_MODEL="$(_menv_get "$tenv" EMBEDDING_MODEL)"
    NEW_DIM="$(_menv_get "$tenv" EMBEDDING_DIMENSION)"
    [[ -n "$NEW_MODEL" ]] || NEW_MODEL="nomic-embed-text"
    [[ -n "$NEW_DIM" ]]   || NEW_DIM="768"

    # --- direct-path clean volume layout (what --data-root produces) -----
    # EVERY volume, postgres + redis (the biggest) included, lands UNDER
    # NEW_DATA_ROOT — never on a local ${MIG_TO}/data/docker path.
    NEW_DATA_ROOT="$MIG_DATA_ROOT"
    NEW_POSTGRES_VOL="${NEW_DATA_ROOT}/postgres"
    NEW_REDIS_VOL="${NEW_DATA_ROOT}/redis"
    NEW_DOCS_VOL="${NEW_DATA_ROOT}/docs"
    NEW_CACHE_VOL="${NEW_DATA_ROOT}/cache"
    NEW_LOGS_VOL="${NEW_DATA_ROOT}/logs"

    # --- data-strategy resolution ----------------------------------------
    # embeddings are only reusable when model AND dimension both match.
    PRESERVE_OK=1
    PRESERVE_REASON=""
    if [[ "$MIG_STRATEGY" == "preserve" ]]; then
        if [[ -z "$OLD_MODEL" || -z "$OLD_DIM" ]]; then
            PRESERVE_OK=0
            PRESERVE_REASON="could not read the OLD embedding model/dimension (checked ${OLD_ENV##*/} + config.yaml)"
        elif [[ "$OLD_MODEL" != "$NEW_MODEL" || "$OLD_DIM" != "$NEW_DIM" ]]; then
            PRESERVE_OK=0
            PRESERVE_REASON="embedding space differs — old=${OLD_MODEL}/${OLD_DIM} vs new=${NEW_MODEL}/${NEW_DIM}; stored vectors are not comparable"
        elif [[ ! -d "$OLD_POSTGRES_VOL" ]]; then
            PRESERVE_OK=0
            PRESERVE_REASON="no OLD embeddings store found at ${OLD_POSTGRES_VOL} (nothing to preserve)"
        fi
    fi
    # EFFECTIVE strategy after the compatibility guard.
    if [[ "$MIG_STRATEGY" == "preserve" && $PRESERVE_OK -eq 1 ]]; then
        EFFECTIVE_STRATEGY="preserve"
    else
        EFFECTIVE_STRATEGY="fresh"
    fi

    # --- cruft the OLD deployment leaves behind (for the cleanup report) --
    CRUFT=()
    if [[ -L "${MIG_FROM}/data" ]]; then
        CRUFT+=("symlink: ${MIG_FROM}/data -> $(readlink "${MIG_FROM}/data" 2>/dev/null)")
    fi
    local p
    # Include the OLD postgres/redis stores: a DB left on the root/home disk (the
    # exact bug this migration fixes) is the most important cruft to surface.
    for p in "$OLD_DATA_ROOT" "$OLD_POSTGRES_VOL" "$OLD_REDIS_VOL" "$OLD_DOCS_VOL" "$OLD_CACHE_VOL" "$OLD_LOGS_VOL"; do
        [[ -n "$p" ]] || continue
        case "$p" in
            /mnt/*|/media/*|/srv/*) : ;;                     # roomy disk — fine
            /root/*|/home/*|"$HOME"/*) CRUFT+=("root/home-disk data: ${p}") ;;
        esac
        case "$p" in *"/docker/"*) CRUFT+=("nested '/docker/' subpath layer (flattened in the clean layout): ${p}") ;; esac
    done
}

# ---------------------------------------------------------------------------
# Print the full plan (the graded DRY-RUN artifact).
# ---------------------------------------------------------------------------
_migrate_print_plan() {
    echo
    printf "%s\n" "${BOLD}RAG deployment + data migration plan${NC}"
    printf "  mode        : %s\n" "$( ((MIG_APPLY)) && echo '--apply (EXECUTE)' || echo 'DRY-RUN (no changes)')"
    echo

    printf "%s\n" "${BOLD}1) Detected OLD deployment${NC}"
    printf "  from dir    : %s\n" "$MIG_FROM"
    printf "  compose     : %s\n" "${OLD_COMPOSE:-<none found>}"
    printf "  .env        : %s\n" "$( [[ -f "$OLD_ENV" ]] && echo "$OLD_ENV" || echo '<none found>')"
    printf "  config.yaml : %s\n" "${OLD_CONFIG:-<none — single-KB>}"
    printf "  identity    : %s\n" "${OLD_NAME:-<unset>}"
    printf "  shape       : %s%s\n" "$OLD_MODE" "$( [[ -n "$OLD_KBS" ]] && echo "  (KBs: ${OLD_KBS})")"
    printf "  port        : %s\n" "${OLD_PORT:-<unset>}"
    printf "  docs source : %s\n" "${OLD_DOCS:-<unset>}"
    printf "  embeddings  : %s / %s\n" "${OLD_MODEL:-<unknown>}" "${OLD_DIM:-<unknown>}"
    printf "  data root   : %s\n" "${OLD_DATA_ROOT:-<unset>}"
    printf "  docs vol    : %s\n" "${OLD_DOCS_VOL:-<default ./data/docs>}"
    printf "  cache vol   : %s\n" "${OLD_CACHE_VOL:-<default ./data/cache>}"
    printf "  logs vol    : %s\n" "${OLD_LOGS_VOL:-<default ./data/logs>}"
    printf "  postgres vol: %s\n" "$( [[ -d "$OLD_POSTGRES_VOL" ]] && echo "$OLD_POSTGRES_VOL" || echo "<none at ${OLD_POSTGRES_VOL}>")"
    printf "  redis vol   : %s\n" "$( [[ -d "$OLD_REDIS_VOL" ]] && echo "$OLD_REDIS_VOL" || echo "<none at ${OLD_REDIS_VOL}>")"
    echo

    printf "%s\n" "${BOLD}2) CLEAN target (image-mode, direct-path volumes)${NC}"
    printf "  to dir      : %s\n" "$MIG_TO"
    printf "  identity    : %s\n" "$NEW_NAME"
    printf "  shape       : %s\n" "$NEW_MODE"
    printf "  port        : %s\n" "${NEW_PORT:-<none detected — pass a free base via the old .env>}"
    printf "  image tag   : %s\n" "$NEW_TAG"
    printf "  docs source : %s\n" "${NEW_DOCS:-<unset>}"
    printf "  data root   : %s\n" "$NEW_DATA_ROOT"
    printf "    postgres  : %s\n" "$NEW_POSTGRES_VOL"
    printf "    redis     : %s\n" "$NEW_REDIS_VOL"
    printf "    docs vol  : %s\n" "$NEW_DOCS_VOL"
    printf "    cache vol : %s\n" "$NEW_CACHE_VOL"
    printf "    logs vol  : %s\n" "$NEW_LOGS_VOL"
    printf "  scaffolded by: new-consumer  (NO symlink layer, NO '/docker/' subpath layer; DB under data-root)\n"
    printf "    command   : rag new-consumer %q %s %q --mode %s --data-root %q --tag %q --out %q\n" \
        "$NEW_NAME" "${NEW_PORT:-<PORT>}" "${NEW_DOCS:-<DOCS>}" "$NEW_MODE" "$NEW_DATA_ROOT" "$NEW_TAG" "$MIG_TO"
    echo

    printf "%s\n" "${BOLD}3) Data strategy${NC}"
    if [[ "$MIG_STRATEGY" == "preserve" && $PRESERVE_OK -eq 0 ]]; then
        warn "requested --preserve-data but it is NOT possible:"
        printf "    reason  : %s\n" "$PRESERVE_REASON"
        printf "    action  : falling back to --fresh (re-ingest) — the only correct option here.\n"
    fi
    if [[ "$EFFECTIVE_STRATEGY" == "fresh" ]]; then
        printf "  strategy    : FRESH (re-ingest — pristine, regenerable embeddings)\n"
        printf "  source docs : %s\n" "${NEW_DOCS:-<unset>}"
        printf "  ingest via  : the new instance's ingest flow after it is healthy\n"
    else
        printf "  strategy    : PRESERVE (carry OLD embeddings + docs onto the new direct-path volumes)\n"
        printf "  compat      : OK — embeddings match (%s / %s)\n" "$NEW_MODEL" "$NEW_DIM"
        printf "  will copy (rsync -aH, then VERIFY bytes+counts, never deleting source):\n"
        [[ -d "$OLD_POSTGRES_VOL" ]] && printf "    %s\n" "${OLD_POSTGRES_VOL}/ ->  ${NEW_POSTGRES_VOL}/  (postgres = the embeddings; biggest volume)"
        [[ -d "$OLD_REDIS_VOL"    ]] && printf "    %s\n" "${OLD_REDIS_VOL}/ ->  ${NEW_REDIS_VOL}/"
        [[ -n "$OLD_DOCS_VOL"  ]] && printf "    %s\n" "${OLD_DOCS_VOL}/  ->  ${NEW_DOCS_VOL}/"
        [[ -n "$OLD_CACHE_VOL" ]] && printf "    %s\n" "${OLD_CACHE_VOL}/ ->  ${NEW_CACHE_VOL}/"
        [[ -n "$OLD_LOGS_VOL"  ]] && printf "    %s\n" "${OLD_LOGS_VOL}/  ->  ${NEW_LOGS_VOL}/"
        printf "  note        : for an in-place SINGLE-instance disk move (not a migration),\n"
        printf "                use the 'relocate' module instead (rag relocate --to ...).\n"
    fi
    echo

    printf "%s\n" "${BOLD}4) Bring-up + verify${NC}"
    printf "  1. (apply) stop the OLD stack (kept, not removed) to free port %s\n" "${NEW_PORT:-<port>}"
    printf "  2. scaffold the clean consumer at %s\n" "$MIG_TO"
    [[ "$EFFECTIVE_STRATEGY" == "preserve" ]] && printf "  3. copy + verify the OLD data into the new direct-path layout\n"
    printf "  %s. docker compose up -d  (from %s)\n" "$( [[ "$EFFECTIVE_STRATEGY" == preserve ]] && echo 4 || echo 3)" "$MIG_TO"
    printf "  %s. health-gate: http://127.0.0.1:%s/api/health\n" "$( [[ "$EFFECTIVE_STRATEGY" == preserve ]] && echo 5 || echo 4)" "${NEW_PORT:-<port>}"
    [[ "$EFFECTIVE_STRATEGY" == "fresh" ]] \
        && printf "  5. ingest from %s + confirm chunk count > 0\n" "${NEW_DOCS:-<docs>}" \
        || printf "  6. confirm carried chunk count > 0\n"
    echo

    printf "%s\n" "${BOLD}5) Cleanup of the OLD deployment (NEVER auto-run)${NC}"
    printf "  The OLD deployment is left fully intact until you confirm the new one\n"
    printf "  is serving correctly. Once verified, remove it with:\n"
    printf "    docker compose -p %q down    # from %s (frees containers; keeps data)\n" "${OLD_NAME:-$NEW_NAME}" "$MIG_FROM"
    printf "    rm -rf %q\n" "$MIG_FROM"
    if [[ ${#CRUFT[@]} -gt 0 ]]; then
        echo
        printf "  Detected cruft to clean up as well:\n"
        local c; for c in "${CRUFT[@]}"; do printf "    - %s\n" "$c"; done
    fi
}

# ---------------------------------------------------------------------------
# Guarded cross-instance copy (copy -> verify -> keep source). Used ONLY by
# --preserve-data. This deliberately does NOT drive the single-instance
# `relocate` module end-to-end: that module repoints + RESTARTS the OLD stack
# (which would re-occupy the carried port) and preserves source basenames that
# need not match the clean docs/cache/logs layout. We reuse relocate's SAFETY
# MODEL (rsync -aH, then verify apparent bytes + entry counts, never delete the
# source) adapted to seed a NEW instance before its first boot.
_migrate_safe_copy() {
    local src="$1" dst="$2"
    [[ -d "$src" ]] || { warn "source missing, skipping: ${src}"; return 0; }
    command -v rsync >/dev/null 2>&1 || die "rsync not found — install rsync and retry (nothing changed)."
    info "copying ${src}/ -> ${dst}/"
    mkdir -p "$dst"
    rsync -aH "${src}/" "${dst}/" || die "rsync failed for ${src} — ABORT (OLD data intact at ${src})."
    # verify: entry counts exact + apparent bytes within 0.1% (or 4KiB).
    local sc dc sb db diff tol
    sc="$(find "$src" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')"
    dc="$(find "$dst" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')"
    [[ "$sc" == "$dc" ]] || die "VERIFY FAILED ${dst}: entries ${dc} != ${sc} — ABORT (OLD data intact at ${src})."
    sb="$(du -sb "$src" 2>/dev/null | awk '{print $1}')"; sb="${sb:-0}"
    db="$(du -sb "$dst" 2>/dev/null | awk '{print $1}')"; db="${db:-0}"
    diff=$(( sb - db )); (( diff < 0 )) && diff=$(( -diff ))
    tol=$(( sb / 1000 )); (( tol < 4096 )) && tol=4096
    (( diff <= tol )) || die "VERIFY FAILED ${dst}: bytes ${db} vs ${sb} (>${tol}B) — ABORT (OLD data intact at ${src})."
    success "verified ${dst} (${sc} entries)"
}

# ---------------------------------------------------------------------------
# --apply: execute the migration, abort-safe, OLD never destroyed.
# ---------------------------------------------------------------------------
_migrate_apply() {
    [[ -n "$NEW_PORT" ]] || die "cannot --apply: no port detected in the OLD .env (need RAG_PORT/RAG_PORT_BASE)"
    [[ -n "$NEW_DOCS" ]] || die "cannot --apply: no DOCS_PATH detected in the OLD .env (needed to scaffold + ingest)"

    if (( ! MIG_ASSUME_YES )); then
        echo
        printf "%s" "${BOLD}Proceed with --apply? Stops the OLD stack, scaffolds the clean instance, boots it. [y/N] ${NC}"
        read -r reply || reply=""
        case "$reply" in [yY]|[yY][eE][sS]) ;; *) die "aborted by user (nothing changed)." ;; esac
    fi

    # 1. Stop the OLD stack to free the carried port (KEPT — not `down -v`).
    if [[ -n "$OLD_COMPOSE" ]]; then
        info "stopping the OLD stack (kept, not removed) to free port ${NEW_PORT}..."
        ( cd "$MIG_FROM" && docker compose stop ) \
            || warn "could not stop the OLD stack automatically — free port ${NEW_PORT} before boot."
    fi

    # 2. Scaffold the clean consumer via the new-consumer module (single source).
    info "scaffolding the clean consumer at ${MIG_TO}..."
    local -a nc=()
    if [[ -n "${RAG_BIN:-}" && -x "${RAG_BIN:-/nonexistent}" ]]; then
        nc=("$RAG_BIN" new-consumer)
    else
        nc=(bash "$(_migrate_repo_root)/rag" new-consumer)
    fi
    "${nc[@]}" "$NEW_NAME" "$NEW_PORT" "$NEW_DOCS" \
        --mode "$NEW_MODE" --data-root "$NEW_DATA_ROOT" --tag "$NEW_TAG" --out "$MIG_TO" \
        || die "scaffold failed — nothing carried; OLD deployment intact. Remove the partial dir with: rm -rf ${MIG_TO}"

    # 2b. Carry the OLD KB list forward (multikb): the generated config.yaml is a
    #     minimal stub; the OLD config.yaml is the authoritative KB list.
    if [[ "$NEW_MODE" == "multikb" && -n "$OLD_CONFIG" && -f "${MIG_TO}/config.yaml" ]]; then
        info "carrying forward the OLD knowledge_bases list into the new config.yaml..."
        cp "$OLD_CONFIG" "${MIG_TO}/config.yaml"
        # Re-point identity/port to the (possibly renamed) new instance.
        sed -i \
            -e "s/^project_name:.*/project_name: ${NEW_NAME}/" \
            -e "s/^  name:.*/  name: ${NEW_NAME}-net/" \
            "${MIG_TO}/config.yaml" 2>/dev/null || warn "could not rewrite identity in config.yaml — review it manually."
    fi

    # 3. PRESERVE: seed the new direct-path volumes + DB before first boot.
    if [[ "$EFFECTIVE_STRATEGY" == "preserve" ]]; then
        info "preserving OLD data (embeddings match ${NEW_MODEL}/${NEW_DIM})..."
        # postgres + redis land DIRECTLY under NEW_DATA_ROOT (data-root/postgres,
        # data-root/redis) — matching the scaffolded .env RAG_POSTGRES_VOLUME /
        # RAG_REDIS_VOLUME — never on a local ${MIG_TO}/data/docker path.
        [[ -d "$OLD_POSTGRES_VOL" ]] && _migrate_safe_copy "$OLD_POSTGRES_VOL" "$NEW_POSTGRES_VOL"
        [[ -d "$OLD_REDIS_VOL"    ]] && _migrate_safe_copy "$OLD_REDIS_VOL"    "$NEW_REDIS_VOL"
        [[ -n "$OLD_DOCS_VOL"  && -d "$OLD_DOCS_VOL"  ]] && _migrate_safe_copy "$OLD_DOCS_VOL"  "$NEW_DOCS_VOL"
        [[ -n "$OLD_CACHE_VOL" && -d "$OLD_CACHE_VOL" ]] && _migrate_safe_copy "$OLD_CACHE_VOL" "$NEW_CACHE_VOL"
        [[ -n "$OLD_LOGS_VOL"  && -d "$OLD_LOGS_VOL"  ]] && _migrate_safe_copy "$OLD_LOGS_VOL"  "$NEW_LOGS_VOL"
    fi

    # 4. Boot the clean instance.
    info "starting the clean instance..."
    ( cd "$MIG_TO" && docker compose up -d ) \
        || die "docker compose up failed for the new instance. OLD deployment is intact; restart it with: ( cd ${MIG_FROM} && docker compose up -d )"

    # 5. Health-gate.
    if ! _migrate_wait_health "$NEW_PORT"; then
        error "the new instance did NOT become healthy at http://127.0.0.1:${NEW_PORT}/api/health"
        warn "OLD deployment is intact. Roll back with: ( cd ${MIG_TO} && docker compose down ) && ( cd ${MIG_FROM} && docker compose up -d )"
        die "migration NOT confirmed healthy — OLD deployment left untouched."
    fi

    # 6. Data verify: fresh => ingest; preserve => confirm carried content.
    if [[ "$EFFECTIVE_STRATEGY" == "fresh" ]]; then
        info "ingesting from ${NEW_DOCS} (fresh)..."
        if curl -sf -X POST "http://127.0.0.1:${NEW_PORT}/api/ingest" \
                -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1; then
            success "ingest triggered — track it via /api/status (async job)."
        else
            warn "could not auto-trigger ingest via the API; ingest manually from ${MIG_TO} (see RUN.md)."
        fi
    else
        _migrate_report_count "$NEW_PORT"
    fi

    # 7. Success + the (never-auto-run) cleanup command for the OLD deployment.
    echo
    success "clean instance is UP and healthy at http://127.0.0.1:${NEW_PORT}  (${MIG_TO})"
    echo
    info "The OLD deployment was left fully intact. After you confirm the new one"
    info "serves correctly, remove the old one with:"
    printf "    ( cd %q && docker compose -p %q down )\n" "$MIG_FROM" "${OLD_NAME:-$NEW_NAME}"
    printf "    rm -rf %q\n" "$MIG_FROM"
    if [[ ${#CRUFT[@]} -gt 0 ]]; then
        echo
        info "Also clean up (verify these are not shared first):"
        local c; for c in "${CRUFT[@]}"; do printf "    - %s\n" "$c"; done
    fi
}

# Health-wait: prefer common.sh's wait_for_health if the dispatcher provides it.
_migrate_wait_health() {
    local port="$1"
    if declare -F wait_for_health >/dev/null 2>&1; then
        wait_for_health "$port" && return 0 || return 1
    fi
    local url="http://127.0.0.1:${port}/api/health" elapsed=0
    info "waiting for API health at ${url} ..."
    while (( elapsed < 120 )); do
        curl -sf "$url" >/dev/null 2>&1 && { success "API healthy."; return 0; }
        sleep 3; elapsed=$(( elapsed + 3 )); printf "."
    done
    echo; return 1
}

_migrate_report_count() {
    local port="$1" body
    body="$(curl -sf "http://127.0.0.1:${port}/api/status" 2>/dev/null || true)"
    if [[ -n "$body" ]]; then
        info "new instance /api/status: ${body}"
    else
        warn "could not read /api/status to confirm carried chunk count — verify manually."
    fi
}
