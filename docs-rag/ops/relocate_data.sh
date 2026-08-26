#!/usr/bin/env bash
# =============================================================================
# relocate_data.sh — SAFELY move an instance's bind-mount data to a new disk
# =============================================================================
# Moves this RAG instance's data volumes (docs / cache / logs — every
# RAG_*_VOLUME declared in .env) from wherever they live now (e.g. a cramped
# ~/Downloads/<instance>) to a roomier target root (e.g.
# /mnt/quickiespace/<instance>), then repoints .env at the new location and
# brings the stack back up on the copied data.
#
# RUN IT FROM THE CONSUMER / INSTANCE DIRECTORY (the one holding .env and
# docker-compose.yml). It reads RAG_DATA_ROOT + every RAG_*_VOLUME from that
# .env and operates only on this instance.
#
# Usage:
#   ./relocate_data.sh --to <new-data-root> [--apply] [--remove-old] [-y]
#
#   (no --apply)   DRY-RUN (default). Prints the plan only — for each source
#                  volume: its path, size, the target path, the target
#                  filesystem's free space, and whether it fits. Refuses (exit
#                  1) if the target filesystem lacks room. Touches NOTHING.
#   --apply        Execute the relocation (see SAFETY below).
#   --remove-old   After the stack is verified healthy on the NEW data, offer to
#                  delete the OLD source dirs (still asks for typed confirmation;
#                  never deletes without it). Without this flag the old data is
#                  left in place and the exact `rm -rf` is printed for you.
#   -y, --yes      Skip the pre-flight "proceed?" confirmation in --apply mode
#                  (does NOT skip the --remove-old deletion confirmation).
#   -h, --help     This help.
#
# SAFETY MODEL (abort-safe + never-lose-data, in order):
#   1. Space check FIRST — refuse before stopping anything if the target fs
#      cannot hold the data.
#   2. `docker compose stop` — quiesce postgres/redis so files are consistent
#      (containers/volumes are KEPT; this is not `down -v`).
#   3. `rsync -aH` each source -> new-root/<name>/ (cross-filesystem safe;
#      re-runnable, so an interrupted copy resumes cleanly).
#   4. VERIFY every copy (apparent bytes + file counts, within tolerance). On
#      ANY mismatch: ABORT, leave the source 100% intact, restart the stack on
#      the OLD data, and touch NOTHING in .env.
#   5. Only after every copy verifies: back up .env -> .env.bak, then rewrite
#      RAG_DATA_ROOT + each RAG_*_VOLUME to the new root in place.
#   6. `docker compose up -d` and wait for /api/health to go green.
#   7. Only after HEALTHY: the OLD source dirs are eligible for removal — and
#      even then this script never auto-deletes; it prints the exact `rm -rf`
#      (or, with --remove-old, prompts for a typed confirmation first).
#
# The source data is never deleted before the copy is verified AND the stack is
# healthy on the new location. If anything is off, the source is left intact and
# the stack is restored to its prior state.
#
# NOTE — postgres/redis data: current-layout instances declare
# RAG_POSTGRES_VOLUME + RAG_REDIS_VOLUME in .env (direct-path under
# RAG_DATA_ROOT), so this script picks them up like every other RAG_*_VOLUME and
# MOVES them (postgres — the biggest volume — included). Only LEGACY instances
# that kept the DB nested under ./data/docker/{postgres,redis} (no RAG_*_VOLUME
# entry) are not auto-moved; for those, relocate the whole ./data dir while the
# stack is stopped and symlink it into the new root (the plan output flags this).
# =============================================================================

set -euo pipefail

# --- resolve instance dir (where we were invoked) ----------------------------
INSTANCE_DIR="$(pwd)"
ENV_FILE="${INSTANCE_DIR}/.env"
COMPOSE_FILE=""
for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
    if [[ -f "${INSTANCE_DIR}/${f}" ]]; then COMPOSE_FILE="${INSTANCE_DIR}/${f}"; break; fi
done

# --- colour helpers (match rag/common.sh idiom) ------------------------------
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'
info()    { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
die()     { error "$@"; exit 1; }

usage() { sed -n '2,56p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

# --- parse args --------------------------------------------------------------
NEW_ROOT=""
APPLY=0
REMOVE_OLD=0
ASSUME_YES=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)    usage; exit 0 ;;
        --to)         NEW_ROOT="${2:-}"; shift 2 ;;
        --apply)      APPLY=1; shift ;;
        --remove-old) REMOVE_OLD=1; shift ;;
        -y|--yes)     ASSUME_YES=1; shift ;;
        *) die "unknown argument: $1 (use --help)" ;;
    esac
done

[[ -n "$NEW_ROOT" ]]     || { usage; echo >&2; die "missing required --to <new-data-root>"; }
[[ "$NEW_ROOT" = /* ]]   || die "invalid --to '${NEW_ROOT}': must be an ABSOLUTE path"
[[ "$NEW_ROOT" != *".."* ]] || die "invalid --to: must not contain '..'"
[[ -f "$ENV_FILE" ]]     || die "no .env in ${INSTANCE_DIR} — run this from the instance directory (the one with .env + docker-compose.yml)"
[[ -n "$COMPOSE_FILE" ]] || die "no docker-compose file in ${INSTANCE_DIR} — run this from the instance directory"

# Normalise NEW_ROOT (strip trailing slash, but keep root "/").
[[ "$NEW_ROOT" == "/" ]] || NEW_ROOT="${NEW_ROOT%/}"

# --- .env readers (read-only variants of common.sh env_get/env_set) ----------
env_get() {  # print value of KEY from .env, empty if absent; strips one layer of quotes
    local v
    v="$(grep -m1 "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    v="${v%$'\r'}"                       # tolerate CRLF .env files
    v="${v#\"}"; v="${v%\"}"             # strip paired double quotes
    v="${v#\'}"; v="${v%\'}"             # strip paired single quotes
    printf '%s' "$v"
}

env_keys_matching() {  # print KEY names in .env matching the given anchored regex
    grep -oE "^${1}=" "$ENV_FILE" 2>/dev/null | sed 's/=$//' || true
}

env_set_inplace() {  # replace KEY=... in place (KEY must already exist)
    local key="$1" value="$2" tmp
    tmp="$(mktemp "${INSTANCE_DIR}/.env.reloc.XXXXXX")"
    awk -v k="$key" -v v="$value" -F= 'BEGIN{done=0}
        $1 == k { print k "=" v; done=1; next }
        { print }
        END { if (!done) print k "=" v }' \
        "$ENV_FILE" > "$tmp" && mv "$tmp" "$ENV_FILE"
}

# --- resolve a possibly-relative / var-referencing volume path safely --------
# Values in .env are literal paths in practice. We support the realistic forms
# WITHOUT eval (no code-from-data): absolute, leading ./ or ../-free relative
# (resolved against the instance dir), leading ~/, and a leading
# $RAG_DATA_ROOT / ${RAG_DATA_ROOT} reference. Anything else containing a '$'
# we refuse to guess at.
resolve_path() {
    local raw="$1" cur_root="$2" out="$raw"
    # Expand a leading RAG_DATA_ROOT reference against the CURRENT root value.
    out="${out/#\$\{RAG_DATA_ROOT\}/$cur_root}"
    out="${out/#\$RAG_DATA_ROOT/$cur_root}"
    # Leading ~ -> $HOME
    if [[ "$out" == "~" || "$out" == "~/"* ]]; then out="${HOME}${out#\~}"; fi
    case "$out" in
        *'$'*) die "cannot safely resolve volume path '${raw}' (unsupported \$-expansion); edit .env to an absolute path and re-run" ;;
    esac
    # Relative -> anchor at the instance dir (compose runs from here).
    [[ "$out" = /* ]] || out="${INSTANCE_DIR}/${out}"
    printf '%s' "$out"
}

# --- disk helpers ------------------------------------------------------------
# Available KiB on the filesystem that WOULD hold PATH (walk up to the nearest
# existing ancestor so we can probe a target that does not exist yet).
df_avail_kb() {
    local p="$1"
    while [[ ! -e "$p" && "$p" == */* ]]; do p="${p%/*}"; [[ -n "$p" ]] || p="/"; done
    [[ -e "$p" ]] || p="/"
    df -Pk "$p" 2>/dev/null | awk 'NR==2 {print $4}'
}
# Disk-usage estimate (blocks, KiB) — used for the space check (fs-block aware).
du_disk_kb()     { du -sk  "$1" 2>/dev/null | awk '{print $1}'; }
# Apparent size (bytes) — used for VERIFY (filesystem-block independent).
du_apparent_b()  { du -sb  "$1" 2>/dev/null | awk '{print $1}'; }
count_entries()  { find "$1" -mindepth 1 2>/dev/null | wc -l | tr -d ' '; }
human()          { numfmt --to=iec --suffix=B "$1" 2>/dev/null || printf '%sB' "$1"; }

# --- gather the instance's data volumes --------------------------------------
CUR_ROOT="$(env_get RAG_DATA_ROOT)"
mapfile -t VOL_KEYS < <(env_keys_matching 'RAG_[A-Z0-9_]*_VOLUME')

if [[ ${#VOL_KEYS[@]} -eq 0 ]]; then
    die "no RAG_*_VOLUME entries found in ${ENV_FILE}; nothing to relocate. (Set RAG_DOCS_VOLUME/RAG_CACHE_VOLUME/RAG_LOGS_VOLUME to real paths, or relocate ./data by symlink — see the header note.)"
fi

# Refuse a no-op relocation onto the same root.
if [[ -n "$CUR_ROOT" ]]; then
    cur_norm="${CUR_ROOT%/}"
    [[ "$cur_norm" != "$NEW_ROOT" ]] \
        || die "target --to '${NEW_ROOT}' equals the current RAG_DATA_ROOT — nothing to do"
fi

# Build the source->target plan. Parallel arrays keyed by index.
SRC_PATHS=(); DST_PATHS=(); VOL_NAMES=(); PLAN_KEYS=()
TOTAL_NEED_KB=0
declare -A SEEN_SRC=()

for key in "${VOL_KEYS[@]}"; do
    raw="$(env_get "$key")"
    [[ -n "$raw" ]] || { warn "${key} is empty in .env — skipping"; continue; }
    src="$(resolve_path "$raw" "$CUR_ROOT")"
    src="${src%/}"
    name="$(basename "$src")"
    dst="${NEW_ROOT}/${name}"

    # De-dup if two vars point at the same source dir.
    if [[ -n "${SEEN_SRC[$src]:-}" ]]; then
        PLAN_KEYS+=("$key"); SRC_PATHS+=("$src"); DST_PATHS+=("$dst"); VOL_NAMES+=("$name")
        continue
    fi
    SEEN_SRC[$src]=1
    PLAN_KEYS+=("$key"); SRC_PATHS+=("$src"); DST_PATHS+=("$dst"); VOL_NAMES+=("$name")
    if [[ -d "$src" ]]; then
        kb="$(du_disk_kb "$src")"; kb="${kb:-0}"
        TOTAL_NEED_KB=$(( TOTAL_NEED_KB + kb ))
    fi
done

# --- print the plan ----------------------------------------------------------
AVAIL_KB="$(df_avail_kb "$NEW_ROOT")"; AVAIL_KB="${AVAIL_KB:-0}"
# Require the source disk-usage estimate + 15% headroom (covers cross-fs block
# rounding for many small files).
NEED_WITH_MARGIN_KB=$(( TOTAL_NEED_KB + TOTAL_NEED_KB * 15 / 100 ))

echo
printf "%s\n" "${BOLD}RAG data relocation plan${NC}"
printf "  instance dir : %s\n" "$INSTANCE_DIR"
printf "  current root : %s\n" "${CUR_ROOT:-<unset — RAG_DATA_ROOT not in .env>}"
printf "  NEW root     : %s\n" "$NEW_ROOT"
echo
printf "  %-26s %-12s %s\n" "VOLUME (source)" "SIZE" "-> TARGET"
printf "  %-26s %-12s %s\n" "---------------" "----" "---------"
for i in "${!SRC_PATHS[@]}"; do
    src="${SRC_PATHS[$i]}"; dst="${DST_PATHS[$i]}"; key="${PLAN_KEYS[$i]}"
    if [[ -d "$src" ]]; then
        kb="$(du_disk_kb "$src")"; kb="${kb:-0}"
        sz="$(human $(( kb * 1024 )) )"
    elif [[ -e "$src" ]]; then
        sz="(not a dir!)"
    else
        sz="(missing)"
    fi
    printf "  %-26s %-12s -> %s\n" "$key" "$sz" "$dst"
    printf "    %s\n" "$src"
done
echo
printf "  data to copy      : %s (disk usage of existing source dirs)\n" "$(human $(( TOTAL_NEED_KB * 1024 )) )"
printf "  target fs free    : %s\n" "$(human $(( AVAIL_KB * 1024 )) )"
printf "  needed w/ margin  : %s (source + 15%%)\n" "$(human $(( NEED_WITH_MARGIN_KB * 1024 )) )"

FITS=1
if (( AVAIL_KB < NEED_WITH_MARGIN_KB )); then FITS=0; fi
if (( FITS )); then
    success "target filesystem has room."
else
    error "target filesystem does NOT have enough free space."
fi

# postgres/redis-under-./data caveat.
DATA_DIR="${INSTANCE_DIR}/data"
if [[ -d "${DATA_DIR}/docker/postgres" || -d "${DATA_DIR}/docker/redis" ]]; then
    # Only warn if that ./data is NOT itself already living under the new root.
    real_data="$(readlink -f "$DATA_DIR" 2>/dev/null || echo "$DATA_DIR")"
    case "$real_data" in
        "${NEW_ROOT}"/*|"${NEW_ROOT}") ;;  # already on the target — fine
        *)
            echo
            warn "postgres/redis data lives under ${DATA_DIR}/docker (NOT a RAG_*_VOLUME)."
            warn "This script does NOT move the database. To relocate it too, stop the"
            warn "stack, move ./data into ${NEW_ROOT}, and symlink ./data there:"
            warn "    docker compose stop && mv '${DATA_DIR}' '${NEW_ROOT}/data' && ln -s '${NEW_ROOT}/data' '${DATA_DIR}'"
            ;;
    esac
fi

if (( ! APPLY )); then
    echo
    if (( FITS )); then
        info "DRY-RUN complete. Re-run with --apply to perform the relocation."
    else
        die "DRY-RUN: refusing — free up space on the target or choose another --to."
    fi
    exit 0
fi

# =============================================================================
# --apply
# =============================================================================
(( FITS )) || die "refusing to --apply: target filesystem lacks space (see plan above)."

# Confirm before we touch a running stack.
if (( ! ASSUME_YES )); then
    echo
    printf "%s" "${BOLD}Proceed? This will stop the stack, copy the data, and repoint .env. [y/N] ${NC}"
    read -r reply || reply=""
    case "$reply" in [yY]|[yY][eE][sS]) ;; *) die "aborted by user (nothing changed)." ;; esac
fi

# Resolve the health port up-front (RAG_PORT, else RAG_PORT_BASE, else 10000).
HEALTH_PORT="$(env_get RAG_PORT)"
[[ -n "$HEALTH_PORT" ]] || HEALTH_PORT="$(env_get RAG_PORT_BASE)"
[[ -n "$HEALTH_PORT" ]] || HEALTH_PORT="10000"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

wait_for_health() {
    local url="http://127.0.0.1:${HEALTH_PORT}/api/health"
    local max_wait=120 interval=3 elapsed=0
    info "Waiting for API health at ${url} ..."
    while (( elapsed < max_wait )); do
        if curl -sf "$url" >/dev/null 2>&1; then
            success "API healthy on the NEW data location."
            return 0
        fi
        sleep "$interval"; elapsed=$(( elapsed + interval )); printf "."
    done
    echo
    return 1
}

# Bring the stack back on the OLD data (used on abort paths). Best-effort.
restore_stack_old() {
    warn "Restarting the stack on the ORIGINAL data (nothing was deleted)..."
    compose up -d >/dev/null 2>&1 || warn "could not auto-restart; run: docker compose up -d"
}

# --- 1. quiesce --------------------------------------------------------------
info "Stopping the stack (keeping containers + volumes) to quiesce postgres/redis..."
compose stop || die "docker compose stop failed — aborting; nothing copied, source intact."

# --- 2. rsync each volume ----------------------------------------------------
mkdir -p "$NEW_ROOT" || { restore_stack_old; die "could not create target root ${NEW_ROOT}"; }

RSYNC_FLAGS=(-aH --info=progress2)
command -v rsync >/dev/null 2>&1 || { restore_stack_old; die "rsync not found — install rsync and retry (source untouched)."; }

for i in "${!SRC_PATHS[@]}"; do
    src="${SRC_PATHS[$i]}"; dst="${DST_PATHS[$i]}"
    if [[ ! -d "$src" ]]; then
        warn "source ${src} is missing — skipping (will still repoint its .env key)."
        mkdir -p "$dst"
        continue
    fi
    if [[ "$src" == "$dst" ]]; then
        info "source and target identical for ${src} — skipping copy."
        continue
    fi
    info "Copying ${src}/  ->  ${dst}/"
    mkdir -p "$dst"
    if ! rsync "${RSYNC_FLAGS[@]}" "${src}/" "${dst}/"; then
        error "rsync failed for ${src} — ABORTING."
        restore_stack_old
        die "relocation aborted: source intact at ${src}; partial copy left at ${dst} (safe to delete)."
    fi
done

# --- 3. verify every copy ----------------------------------------------------
info "Verifying copies (apparent bytes + entry counts)..."
for i in "${!SRC_PATHS[@]}"; do
    src="${SRC_PATHS[$i]}"; dst="${DST_PATHS[$i]}"
    [[ -d "$src" ]] || continue          # nothing to verify for a missing source
    [[ "$src" != "$dst" ]] || continue

    sb="$(du_apparent_b "$src")"; sb="${sb:-0}"
    db="$(du_apparent_b "$dst")"; db="${db:-0}"
    sc="$(count_entries "$src")"; dc="$(count_entries "$dst")"

    # Entry counts must match exactly (rsync -aH is a faithful copy).
    if [[ "$sc" != "$dc" ]]; then
        error "VERIFY FAILED for ${dst}: entry count ${dc} != source ${sc}."
        restore_stack_old
        die "relocation aborted BEFORE any .env change; source fully intact at ${src}."
    fi
    # Apparent bytes within 0.1% tolerance.
    diff=$(( sb - db )); (( diff < 0 )) && diff=$(( -diff ))
    tol=$(( sb / 1000 )); (( tol < 4096 )) && tol=4096
    if (( diff > tol )); then
        error "VERIFY FAILED for ${dst}: apparent size ${db}B differs from source ${sb}B by ${diff}B (> ${tol}B tolerance)."
        restore_stack_old
        die "relocation aborted BEFORE any .env change; source fully intact at ${src}."
    fi
    success "verified ${dst}  (${sc} entries, $(human "$sb"))"
done

# --- 4. back up + rewrite .env -----------------------------------------------
BAK="${ENV_FILE}.bak"
[[ ! -e "$BAK" ]] || BAK="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$BAK"
info "Backed up .env -> ${BAK}"

# Repoint RAG_DATA_ROOT (if present) + each RAG_*_VOLUME to the new root.
if grep -q '^RAG_DATA_ROOT=' "$ENV_FILE"; then
    env_set_inplace RAG_DATA_ROOT "$NEW_ROOT"
fi
for i in "${!PLAN_KEYS[@]}"; do
    env_set_inplace "${PLAN_KEYS[$i]}" "${DST_PATHS[$i]}"
done
success ".env repointed to ${NEW_ROOT}."

# --- 5. bring the stack up on the new data + health-gate ---------------------
info "Starting the stack on the NEW data location..."
if ! compose up -d; then
    error "docker compose up failed on the new data."
    warn "Your OLD data is intact and .env.bak (${BAK}) holds the previous config."
    warn "Roll back with:  cp '${BAK}' '${ENV_FILE}' && docker compose up -d"
    die "relocation halted after copy; OLD data NOT deleted."
fi

if ! wait_for_health; then
    error "API did not become healthy on the new data within the timeout."
    warn "OLD data is intact. To roll back to the previous location:"
    warn "    cp '${BAK}' '${ENV_FILE}' && docker compose up -d"
    die "relocation NOT confirmed healthy; OLD source dirs left untouched."
fi

# --- 6. old-data disposition (never auto-delete) -----------------------------
echo
success "Relocation complete and healthy on: ${NEW_ROOT}"
echo
info "The OLD source directories were left in place (data is never auto-deleted):"
OLD_DIRS=()
for i in "${!SRC_PATHS[@]}"; do
    src="${SRC_PATHS[$i]}"; dst="${DST_PATHS[$i]}"
    [[ -d "$src" && "$src" != "$dst" ]] || continue
    OLD_DIRS+=("$src")
    printf "    %s\n" "$src"
done

if [[ ${#OLD_DIRS[@]} -eq 0 ]]; then
    info "No old source directories remain to clean up."
    exit 0
fi

echo
info "Once you have confirmed the stack is serving correctly, remove them with:"
for d in "${OLD_DIRS[@]}"; do printf "    rm -rf %q\n" "$d"; done

if (( REMOVE_OLD )); then
    echo
    warn "You passed --remove-old. This will PERMANENTLY delete the directories above."
    printf "%s" "${BOLD}Type 'delete' to confirm removal of the OLD source dirs: ${NC}"
    read -r confirm || confirm=""
    if [[ "$confirm" == "delete" ]]; then
        for d in "${OLD_DIRS[@]}"; do
            info "Removing ${d}"
            rm -rf -- "$d" || warn "could not remove ${d} (remove it manually)."
        done
        success "Old source directories removed."
    else
        warn "Not confirmed — old data left in place. Remove it manually when ready."
    fi
fi

exit 0
