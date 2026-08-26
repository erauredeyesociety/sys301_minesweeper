#!/usr/bin/env bash
# =============================================================================
# scripts/lib/common.sh — shared library for the unified `rag` CLI
# =============================================================================
# Single source for the primitives the `rag` command modules share (logging,
# .env I/O, compose invocation, free-port bands + host port registry,
# health-wait, dry-run/apply parsing, path-safety guards, VERSION read/record,
# self-doc help).
#
# CONTRACT
#   * This file is SOURCED, never executed. It therefore does NOT set
#     `set -euo pipefail` (that would clobber the caller's shell options); the
#     `rag` dispatcher and every command module set it themselves and source
#     this lib under those options. Every helper here is written to be safe
#     under `set -euo pipefail` (all optional vars referenced as ${x:-}).
#   * Sourcing is SIDE-EFFECT-FREE apart from defining functions + a handful of
#     readonly-ish constants (colors, RAG_ROOT, DEFAULT_*). No commands run, no
#     files are touched at source time.
#   * Graceful degradation: consumer-context state (the XDG port registry) is
#     optional — the registry helpers no-op cleanly when it is absent.
#
# Relationship to the standalone ops tools: relocate_data.sh, ingest_kb.py and
# migrate_indexes.py are copied verbatim into consumer ops/ and MUST run without
# scripts/lib/. They keep their own inlined helpers and are NOT refactored onto
# this lib (see docs/findings/2026-07-05_modular_cli_design.md §3).
# =============================================================================

# --- double-source guard -----------------------------------------------------
[[ -n "${_RAG_COMMON_SH_LOADED:-}" ]] && return 0
_RAG_COMMON_SH_LOADED=1

# ---------------------------------------------------------------------------
# Color output helpers (canonical idiom)
# ---------------------------------------------------------------------------
# ANSI-C quoting ($'...') so the escapes are real ESC bytes: they render
# correctly both in printf format strings AND inside heredocs.
: "${RED:=$'\033[0;31m'}"
: "${GREEN:=$'\033[0;32m'}"
: "${YELLOW:=$'\033[1;33m'}"
: "${BLUE:=$'\033[0;34m'}"
: "${CYAN:=$'\033[0;36m'}"
: "${BOLD:=$'\033[1m'}"
: "${NC:=$'\033[0m'}"

info()    { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
fatal()   { error "$@"; exit 1; }

# ---------------------------------------------------------------------------
# Context + roots
# ---------------------------------------------------------------------------
# This lib lives at <root>/scripts/lib/common.sh, so <root> is two levels up.
# <root> is the canonical template repo in a checkout, or the instance dir in a
# source-export consumer (which ships `rag` + scripts/lib/). Overridable via
# RAG_ROOT for tests / unusual layouts.
_RAG_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
: "${RAG_ROOT:=$(cd -- "${_RAG_LIB_DIR}/../.." >/dev/null 2>&1 && pwd -P)}"

# Default values (canonical contracts: port base 10000, nomic-embed-text/768).
: "${DEFAULT_PORT_BASE:=10000}"
: "${DEFAULT_PORT:=10000}"
: "${DEFAULT_NETWORK:=rag-bootstrap}"
: "${DEFAULT_PROJECT:=rag-bootstrap}"
: "${DEFAULT_EMBEDDING_MODEL:=nomic-embed-text}"
: "${DEFAULT_EMBEDDING_DIM:=768}"
: "${DEFAULT_EMBEDDING_BACKEND:=ollama}"
: "${DEFAULT_OLLAMA_URL:=http://host.docker.internal:11434}"

# .env location (overridable). Modules that need a different instance dir set
# ENV_FILE before calling the env_* helpers.
: "${ENV_FILE:=${RAG_ROOT}/.env}"

rag_root() { printf '%s\n' "$RAG_ROOT"; }

# rag_context -> "template" | "consumer"
#   template = the canonical checkout: maintainer surface present
#              (templates/ + CONSUMER_MANIFEST + app/).
#   consumer = anything else (image-mode scaffold, or source-export instance —
#              the latter ships app/ but NOT templates//CONSUMER_MANIFEST).
rag_context() {
    if [[ -d "${RAG_ROOT}/templates" \
        && -f "${RAG_ROOT}/CONSUMER_MANIFEST" \
        && -d "${RAG_ROOT}/app" ]]; then
        echo template
    else
        echo consumer
    fi
}

# ---------------------------------------------------------------------------
# .env I/O (superset of the historical variants)
# ---------------------------------------------------------------------------
env_get() {
    # Print the value of KEY from $ENV_FILE (empty if missing). Tolerates CRLF
    # files and strips ONE layer of paired quotes (relocate_data.sh behavior).
    local v
    v="$(grep -m1 "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    v="${v%$'\r'}"            # tolerate CRLF .env files
    v="${v#\"}"; v="${v%\"}"  # strip paired double quotes
    v="${v#\'}"; v="${v%\'}"  # strip paired single quotes
    printf '%s' "$v"
}

env_has() {
    grep -q "^${1}=" "$ENV_FILE" 2>/dev/null
}

env_set() {
    # Replace KEY=... in place, or append if missing.
    local key="$1" value="$2"
    if env_has "$key"; then
        local tmp
        tmp=$(mktemp)
        awk -v k="$key" -v v="$value" -F= '$1 == k { print k "=" v; next } { print }' \
            "$ENV_FILE" > "$tmp" && mv "$tmp" "$ENV_FILE"
    else
        printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    fi
}

env_ensure() {
    # Append KEY=VALUE only if KEY is not already present (preserve customizations).
    env_has "$1" || printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
}

env_keys_matching() {
    # Print KEY names in $ENV_FILE matching the given anchored regex
    # (e.g. env_keys_matching 'RAG_[A-Z0-9_]*_VOLUME').
    grep -oE "^${1}=" "$ENV_FILE" 2>/dev/null | sed 's/=$//' || true
}

# ---------------------------------------------------------------------------
# Compose wrapper
# ---------------------------------------------------------------------------
# Unifies a bare `docker compose` (relies on cwd docker-compose.yml)
# and relocate_data.sh's explicit `-f "$COMPOSE_FILE"` form. When COMPOSE_FILE
# is set it is passed through; otherwise compose discovers the file in cwd.
compose() {
    docker compose ${COMPOSE_FILE:+-f "$COMPOSE_FILE"} "$@"
}

resolve_compose_file() {
    # Best-effort: echo the first compose file found under DIR (default RAG_ROOT).
    # Empty output when none present (compose() then falls back to cwd discovery).
    local dir="${1:-$RAG_ROOT}" f
    for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
        if [[ -f "${dir}/${f}" ]]; then printf '%s\n' "${dir}/${f}"; return 0; fi
    done
    return 0
}

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
# Published-port band offsets: web on base+0, monitoring on base+10..+16.
# (Historically hard-coded in PORT_OFFSETS and the scaffolder loop.)
RAG_PORT_BAND_OFFSETS=(0 10 11 12 13 14 15 16)

port_in_use() {
    # True (0) if TCP port is LISTENING. ss -> lsof -> /dev/tcp fallback.
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}\$"
    elif command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    else
        # Last resort: try connecting.
        (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null && { exec 3>&- 3<&- || true; return 0; }
        return 1
    fi
}

resolve_health_port() {
    # Health/web port: RAG_PORT, else RAG_PORT_BASE, else the canonical default.
    local p
    p="$(env_get RAG_PORT)"
    [[ -n "$p" ]] || p="$(env_get RAG_PORT_BASE)"
    [[ -n "$p" ]] || p="$DEFAULT_PORT"
    printf '%s\n' "$p"
}

# --- host-level port registry (coordinates concurrent instances on one host) --
# `ss`/`lsof` only see LISTENING sockets, so a sibling that has claimed a port
# in its .env but is still building/pulling is invisible. The registry makes
# claimed-but-not-yet-bound ports visible: scan AND claim atomically under an
# flock; release on stop/reset (or reap as stale once containers are gone).
#
# File format, one claim per line:  <port> <compose_project> <claimed_epoch>
# XDG_RUNTIME_DIR falls back to /tmp, so the registry path always resolves; the
# helpers additionally no-op when the file itself is absent (fresh host).
: "${PORT_REGISTRY:=${XDG_RUNTIME_DIR:-/tmp}/rag-bootstrap-ports}"
: "${PORT_REGISTRY_LOCK:=${PORT_REGISTRY}.lock}"
: "${PORT_REGISTRY_GRACE:=900}"   # seconds a claim survives with no containers yet
: "${PORT_BAND_SIZE:=20}"         # ports per instance band (base .. base+19)

registry_project_name() {
    local p
    p="$(env_get COMPOSE_PROJECT_NAME)"
    echo "${p:-${CONFIG_PROJECT:-$DEFAULT_PROJECT}}"
}

registry_project_alive() {
    # "Alive" = the compose project still has containers (any state).
    docker ps -aq --filter "label=com.docker.compose.project=${1}" 2>/dev/null | grep -q .
}

registry_prune_stale_locked() {
    # Caller must hold the registry lock. Stale = registered but the project's
    # containers are gone (reclaimable) — except claims still inside the grace
    # window, which may legitimately have no containers yet (pre-bind sibling).
    [[ -s "$PORT_REGISTRY" ]] || return 0
    local now tmp port proj ts _rest
    now=$(date +%s)
    tmp=$(mktemp)
    while read -r port proj ts _rest; do
        [[ -z "$port" || -z "$proj" ]] && continue
        if [[ "${ts:-}" =~ ^[0-9]+$ ]] && (( now - ts < PORT_REGISTRY_GRACE )); then
            printf '%s %s %s\n' "$port" "$proj" "$ts" >> "$tmp"
        elif registry_project_alive "$proj"; then
            printf '%s %s %s\n' "$port" "$proj" "${ts:-$now}" >> "$tmp"
        fi
        # else: stale entry (registered but containers gone) -> reclaimed
    done < "$PORT_REGISTRY"
    mv "$tmp" "$PORT_REGISTRY"
}

registry_remove_project_locked() {
    # Caller must hold the registry lock. Drop all claims held by <project>.
    [[ -f "$PORT_REGISTRY" ]] || return 0
    local tmp
    tmp=$(mktemp)
    awk -v proj="$1" '$2 != proj' "$PORT_REGISTRY" > "$tmp" && mv "$tmp" "$PORT_REGISTRY"
}

registry_port_taken_locked() {
    # Caller must hold the registry lock. Is <port> claimed by another project?
    local port="$1" project="$2"
    [[ -f "$PORT_REGISTRY" ]] || return 1
    awk -v port="$port" -v proj="$project" \
        '$1 == port && $2 != proj { found = 1 } END { exit found ? 0 : 1 }' \
        "$PORT_REGISTRY"
}

registry_scan_and_claim() {
    # Usage: registry_scan_and_claim <start_port> <count> <project>
    # Under the registry flock: prune stale entries, drop this project's old
    # claim, then pick the first port in [start, start+count) that is neither
    # listening nor claimed by a live sibling; record and echo it.
    # Returns 1 (empty output) when the range is exhausted or the lock times out.
    local start="$1" count="$2" project="$3"
    (
        flock -w 15 9 || {
            error "Could not acquire port-registry lock: ${PORT_REGISTRY_LOCK}"
            exit 1
        }
        touch "$PORT_REGISTRY"
        registry_prune_stale_locked
        registry_remove_project_locked "$project"
        local i candidate
        for (( i = 0; i < count; i++ )); do
            candidate=$((start + i))
            if port_in_use "$candidate"; then
                continue
            fi
            if registry_port_taken_locked "$candidate" "$project"; then
                continue
            fi
            printf '%s %s %s\n' "$candidate" "$project" "$(date +%s)" >> "$PORT_REGISTRY"
            echo "$candidate"
            exit 0
        done
        exit 1
    ) 9>>"$PORT_REGISTRY_LOCK"
}

registry_record() {
    # Unconditionally (re)record <port> for <project> (own-stack/restart path).
    local port="$1" project="$2"
    (
        flock -w 15 9 || exit 0
        touch "$PORT_REGISTRY"
        registry_remove_project_locked "$project"
        printf '%s %s %s\n' "$port" "$project" "$(date +%s)" >> "$PORT_REGISTRY"
    ) 9>>"$PORT_REGISTRY_LOCK"
}

registry_release() {
    # Free this instance's registry claim (called from stop / reset / clean).
    # No-ops cleanly when the registry file was never created on this host.
    local project
    project="$(registry_project_name)"
    [[ -f "$PORT_REGISTRY" ]] || return 0
    (
        flock -w 15 9 || exit 0
        registry_remove_project_locked "$project"
    ) 9>>"$PORT_REGISTRY_LOCK"
}

registry_list() {
    # Enumerate this host's docs-rag stacks from DURABLE docker state (NOT the
    # ephemeral in-runtime port-registry file, which only tracks THIS instance's
    # claims): every running rag-bootstrap container that publishes a host port.
    # One TAB-separated row per such container, sorted by port:
    #     <compose_project>\t<published_port>\t<image_tag>
    # Only port-publishing containers match, so a normal stack yields one row (its
    # web frontend). READ-ONLY — a single `docker ps` query touches no state; no-ops
    # cleanly (empty output, rc 0) when docker is absent or no stack is running.
    command -v docker >/dev/null 2>&1 || return 0
    docker ps --filter "label=com.docker.compose.project" \
        --format '{{.Label "com.docker.compose.project"}}|{{.Image}}|{{.Ports}}' \
        2>/dev/null \
    | awk -F'|' '
        $2 ~ /^rag-bootstrap/ && match($3, /:[0-9]+->/) {
            port = substr($3, RSTART + 1, RLENGTH - 3)
            tag  = $2; sub(/^.*:/, "", tag)
            print $1 "\t" port "\t" tag
        }' \
    | sort -t "$(printf '\t')" -k2,2n
}

# ---------------------------------------------------------------------------
# Health-wait (merges wait_for_api + wait_for_health)
# ---------------------------------------------------------------------------
wait_for_health() {
    # wait_for_health [port] [max_wait_seconds]
    # Polls http://127.0.0.1:<port>/api/health until 200 or timeout.
    # Returns 0 on healthy, 1 on timeout (caller decides whether to fatal) —
    # keeping the primitive reusable across commands with different messaging.
    local port="${1:-$(resolve_health_port)}"
    local max_wait="${2:-120}"
    local url="http://127.0.0.1:${port}/api/health"
    local interval=3 elapsed=0

    info "Waiting for API to be ready at ${url} ..."
    while (( elapsed < max_wait )); do
        if curl -sf "$url" >/dev/null 2>&1; then
            success "API is ready at http://127.0.0.1:${port}"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
        printf "."
    done
    echo ""
    return 1
}

# ---------------------------------------------------------------------------
# Dry-run / apply mode parsing (export/update/relocate idiom)
# ---------------------------------------------------------------------------
parse_dry_apply() {
    # Scan args for --apply / --dry-run and echo the resolved mode
    # ("dry-run" default | "apply"). Non-mode args are ignored so callers can
    # scan the same argv for positionals separately.
    local mode="dry-run" a
    for a in "$@"; do
        case "$a" in
            --apply)   mode="apply" ;;
            --dry-run) mode="dry-run" ;;
        esac
    done
    printf '%s\n' "$mode"
}

dry_run_footer() {
    # Standard trailer printed at the end of a dry-run pass. Optional $1 = the
    # verb noun ("copied" / "changed"); defaults to a generic message.
    local what="${1:-changed}"
    echo "DRY-RUN complete — nothing was ${what}."
    echo "Re-run with --apply to execute."
}

# ---------------------------------------------------------------------------
# Path-safety guards (scaffold / export / relocate)
# ---------------------------------------------------------------------------
require_absolute() {
    # require_absolute <label> <value>
    [[ "$2" = /* ]] || fatal "invalid ${1} '${2}': must be an ABSOLUTE path"
}

reject_traversal() {
    # reject_traversal <label> <value>
    [[ "$2" != *".."* ]] || fatal "invalid ${1}: must not contain '..'"
}

reject_unsafe() {
    # reject_unsafe <label> <value>
    # Reject control chars (an embedded newline could inject an extra KEY=val
    # line) and quote/backtick chars (would break YAML/env quoting). No eval is
    # ever involved; this is defense-in-depth for values substituted into files.
    [[ "$2" != *[[:cntrl:]]* ]] \
        || fatal "invalid ${1}: contains a control character (newline/tab/etc.)"
    case "$2" in
        *\"*|*\'*|*\`*) fatal "invalid ${1}: must not contain quote or backtick characters" ;;
    esac
}

# ---------------------------------------------------------------------------
# VERSION read / upstream-sync record (build + update)
# ---------------------------------------------------------------------------
read_version() {
    # Echo the semver on line 1 of the VERSION file ($1, default <root>/VERSION),
    # validated as X.Y.Z[-/+prerelease]. Exits nonzero (fatal) on missing/blank/
    # non-semver so callers never emit an empty or malformed image tag.
    local version_file="${1:-${RAG_ROOT}/VERSION}" version
    [[ -f "$version_file" ]] || fatal "VERSION file not found at ${version_file}"
    version="$(head -n 1 "$version_file" | tr -d '[:space:]')"
    [[ -n "$version" ]] || fatal "version is empty (VERSION file blank): ${version_file}"
    [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+.][0-9A-Za-z.-]+)?$ ]] \
        || fatal "version '${version}' is not a valid semver (X.Y.Z)"
    printf '%s\n' "$version"
}

record_upstream_sync() {
    # record_upstream_sync <version_file> <upstream_dir>
    # Best-effort: stamp/refresh the `last-upstream-sync:` line in VERSION with
    # today's date + the upstream commit (and a dirty marker if applicable).
    local version_file="$1" upstream="$2" upstream_commit upstream_dirty=""
    upstream_commit="$(git -C "$upstream" log -1 --format=%H 2>/dev/null || echo 'unknown')"
    if [[ -n "$(git -C "$upstream" status --porcelain -- . 2>/dev/null | head -1)" ]]; then
        upstream_dirty=" + uncommitted working-tree changes"
    fi
    if [[ -f "$version_file" ]] && grep -q '^last-upstream-sync:' "$version_file"; then
        sed -i "s|^last-upstream-sync:.*|last-upstream-sync: $(date +%F) (commit ${upstream_commit}${upstream_dirty})|" "$version_file"
    else
        echo "last-upstream-sync: $(date +%F) (commit ${upstream_commit}${upstream_dirty})" >> "$version_file"
    fi
}

# ---------------------------------------------------------------------------
# Self-documenting help (the `sed -n '2,Np' | sed 's/^# //'` idiom)
# ---------------------------------------------------------------------------
print_header_usage() {
    # print_header_usage <file> [start_line] [end_line]
    # Emit a script's comment header (default lines 2..40) with the leading
    # "# " stripped — the usage() body used by the maintainer scripts.
    local file="$1" start="${2:-2}" end="${3:-40}"
    sed -n "${start},${end}p" "$file" | sed 's/^# \{0,1\}//'
}

# ---------------------------------------------------------------------------
# Lifecycle + preflight helpers
# ---------------------------------------------------------------------------
# The `rag up/down/restart/ingest/sync/status/health/doctor/reset/clean`
# modules call ~30 deploy-time helpers (parse_config, generate_env,
# ensure_data_directories, port_preflight, ollama_preflight, dim_guard,
# wait_for_api, do_ingest, resolved_port, wipe_data_dirs, show_status,
# echo_effective_config, compose_up_with_port_retry, stored_embedding_dimension,
# the doctor headroom checks, …). Those live in lifecycle.sh, which is sourced
# HERE so every module that sources common.sh gets the full surface. lifecycle.sh
# relies on the primitives defined above (logging, colors, .env I/O, the port
# registry, RAG_ROOT + DEFAULT_*), so it must be sourced last.
if [[ -f "${_RAG_LIB_DIR}/lifecycle.sh" ]]; then
    # shellcheck source=lifecycle.sh disable=SC1091
    source "${_RAG_LIB_DIR}/lifecycle.sh"
fi
