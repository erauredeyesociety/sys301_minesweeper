# shellcheck shell=bash
# =============================================================================
# commands/sync-cli.sh — module for `rag sync-cli`  (audience: both)
# =============================================================================
# Copy the `rag` CLI surface BAKED INTO the running api image out into this
# instance dir, so the host-side CLI stays in LOCKSTEP with an image bump.
#
# WHY: an image tag bump delivers new API ENDPOINTS, but new `rag` SUBCOMMANDS
# are host-side files under scripts/lib/commands/ — they do NOT travel with the
# image on their own. The multi-KB image (app/Dockerfile.multi-kb) bakes the CLI
# into /src; this command extracts it back out. After `rag up` onto a newer tag,
# one `rag sync-cli` refreshes the CLI to match — NO rag-bootstrap source
# checkout needed.
#
# WHAT IT COPIES (only generic, replaceable CLI assets):
#   /src/rag         -> ./rag           (dispatcher; exec bit preserved)
#   /src/scripts/lib -> ./scripts/lib   (command modules + shared lib)
#   /src/client      -> ./client        (query helpers, if present)
#   /src/agent_hints -> ./agent_hints   (agent docs, if present)
#   /src/ops         -> ./ops           (consumer-scaffold CLI dir, if BOTH the
#                                        image carries it AND this instance uses it)
#
# WHAT IT NEVER TOUCHES: config.yaml, .env, docker-compose.yml (instance-specific;
# they are not baked into the image and are never in the copy list).
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "sync-cli||both|Copy the baked rag CLI out of the api container (lockstep after an image bump)"
}

run() {
    # Pull in shared helpers (info/warn/fatal/success) if sourced standalone.
    if ! command -v fatal >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local root
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
        "") : ;;
        -*) fatal "sync-cli: unknown option: $1 (use --help)" ;;
        *)  fatal "sync-cli: unexpected argument: $1 (use --help)" ;;
    esac

    command -v docker >/dev/null 2>&1 \
        || fatal "sync-cli: 'docker' not found on PATH"

    # docker compose reads its compose file + .env from cwd; the dispatcher root
    # IS the instance dir. cd there so `docker compose` resolves the right
    # compose project (COMPOSE_PROJECT_NAME) → the right api container.
    cd "$root"

    local cid
    cid="$(docker compose ps -q api 2>/dev/null || true)"
    [[ -n "$cid" ]] \
        || fatal "sync-cli: api container not running — start the stack first (./rag up), then re-run."

    info "Refreshing the host CLI from the baked image in container ${cid:0:12} …"

    # Stage into a scratch dir, then swap into place. Copying to a NON-existent
    # dest avoids the `docker cp DIR existing/` nesting gotcha AND drops stale/
    # deleted modules (a plain in-place copy would leave removed commands behind).
    local stage
    stage="$(mktemp -d)"
    # shellcheck disable=SC2064
    trap "rm -rf '$stage'" RETURN

    local copied=0    # targets present in the image (and thus copied out)
    local changed=0   # of those, targets whose CONTENT actually differed on disk

    # Stable content digest of a file OR directory (recursive, path-relative), or the
    # sentinel __absent__. Used to report unchanged-vs-refreshed PER target so a single
    # `rag sync-cli` run is self-evidently turn-key (nothing changed => "0 refreshed").
    # Content-only (ignores mode); never fails the run under `set -euo pipefail`.
    _synccli_digest() {
        local p="$1"
        if [[ -f "$p" ]]; then
            sha256sum "$p" 2>/dev/null | awk '{print $1}' || true
        elif [[ -d "$p" ]]; then
            ( cd "$p" && find . -type f -print0 | LC_ALL=C sort -z \
                | xargs -0 sha256sum | sha256sum | awk '{print $1}' ) 2>/dev/null || true
        else
            printf '__absent__\n'
        fi
        return 0
    }

    # --- ./rag (single file; preserve exec bit) ------------------------------
    if docker compose exec -T api test -e /src/rag >/dev/null 2>&1; then
        docker compose cp api:/src/rag "$stage/rag" \
            || fatal "sync-cli: failed to copy /src/rag out of the api container"
        local rag_before rag_new
        rag_before="$(_synccli_digest "$root/rag")"
        rag_new="$(_synccli_digest "$stage/rag")"
        install -m 0755 "$stage/rag" "$root/rag" \
            || fatal "sync-cli: failed to install ./rag"
        if [[ "$rag_before" == "$rag_new" ]]; then
            info "  ./rag                 unchanged"
        else
            success "  ./rag                 refreshed"
            changed=$((changed + 1))
        fi
        copied=$((copied + 1))
    else
        warn "  /src/rag not present in the image — skipping (older api image?)"
    fi

    # --- directory assets (stage → atomic-ish swap) --------------------------
    #   $1 = path inside container (under /src)   $2 = dest dir in instance
    #   $3 = required(1) | optional(0)  — optional targets skip if the instance
    #        does not already have that dir (e.g. ops/ on a source-export layout).
    _synccli_swap_dir() {
        local src="$1" dest="$2" required="$3" base name
        base="$(basename "$dest")"
        # Skip optional targets the instance layout doesn't use.
        if [[ "$required" != "1" && ! -d "$dest" ]]; then
            return 0
        fi
        # Skip cleanly if the image doesn't carry it (older api image / not baked).
        if ! docker compose exec -T api test -d "$src" >/dev/null 2>&1; then
            if [[ "$required" == "1" ]]; then
                warn "  ${src} not present in the image — skipping (older api image?)"
            fi
            return 0
        fi
        docker compose cp "api:${src}" "$stage/$base" \
            || fatal "sync-cli: failed to copy ${src} out of the api container"
        # Compare the freshly-copied tree against what's on disk BEFORE the swap.
        local d_before d_new
        d_before="$(_synccli_digest "$dest")"
        d_new="$(_synccli_digest "$stage/$base")"
        # swap: new dir into place, remove old, rename in — never edit in place.
        rm -rf "${dest}.new"
        mv "$stage/$base" "${dest}.new" \
            || fatal "sync-cli: failed to stage ${dest}.new"
        rm -rf "$dest"
        mv "${dest}.new" "$dest" \
            || fatal "sync-cli: failed to swap ${dest} into place"
        if [[ "$d_before" == "$d_new" ]]; then
            info "  ${dest#"$root/"}/  unchanged"
        else
            success "  ${dest#"$root/"}/  refreshed"
            changed=$((changed + 1))
        fi
        copied=$((copied + 1))
    }

    # Snapshot the RUNNING sync-cli module BEFORE the scripts/lib swap overwrites it on
    # disk — we compare against the freshly-synced copy to decide the turn-key re-exec
    # (SNAG A). Reading ${BASH_SOURCE[0]} after the swap would just read the new file.
    local self_before="$stage/sync-cli.self.before"
    cp -f "${BASH_SOURCE[0]}" "$self_before" 2>/dev/null || true

    _synccli_swap_dir /src/scripts/lib "$root/scripts/lib" 1
    _synccli_swap_dir /src/client      "$root/client"      0
    _synccli_swap_dir /src/agent_hints "$root/agent_hints" 0
    _synccli_swap_dir /src/ops         "$root/ops"         0

    # --- per-KB ops tools (ingest_kb.py / migrate_indexes.py + doc-health) ---
    # Host-side tools that `rag ingest-kb`, `rag reindex`, `rag rechunk`,
    # `rag preview-prune`, and `rag cite-check` drive. The instance keeps them in
    # ops/ (consumer scaffold) or scripts/ (template) — refresh them too so those
    # commands stay in lockstep with the image. (preview_prune.py reuses its
    # sibling build_dup_clusters.py, so that ships alongside it.)
    _synccli_copy_tool() {
        local fname="$1" tooldir=""
        if   [[ -d "$root/ops" ]];     then tooldir="$root/ops"
        elif [[ -d "$root/scripts" ]]; then tooldir="$root/scripts"
        else return 0; fi
        docker compose exec -T api test -e "/src/scripts/$fname" >/dev/null 2>&1 || return 0
        docker compose cp "api:/src/scripts/$fname" "$stage/$fname" \
            || fatal "sync-cli: failed to copy /src/scripts/$fname out of the api container"
        local t_before t_new
        t_before="$(_synccli_digest "$tooldir/$fname")"
        t_new="$(_synccli_digest "$stage/$fname")"
        install -m 0644 "$stage/$fname" "$tooldir/$fname" \
            || fatal "sync-cli: failed to install $fname"
        if [[ "$t_before" == "$t_new" ]]; then
            info "  ${tooldir#"$root/"}/$fname  unchanged"
        else
            success "  ${tooldir#"$root/"}/$fname  refreshed"
            changed=$((changed + 1))
        fi
        copied=$((copied + 1))
    }
    _synccli_copy_tool ingest_kb.py
    _synccli_copy_tool migrate_indexes.py
    _synccli_copy_tool preview_prune.py
    _synccli_copy_tool build_dup_clusters.py
    _synccli_copy_tool cite_check.py

    # --- turn-key second pass (SNAG A: two-pass chicken-and-egg) --------------
    # Coming from < 0.8.0, THIS run used the OLD host-side sync-cli module whose copy
    # list predated the doc-health tools, so it delivered the old target set and NOT
    # preview_prune.py / build_dup_clusters.py / cite_check.py. The swap above just
    # refreshed scripts/lib (including THIS module) to the image's version. If the
    # freshly-synced module DIFFERS from the one now running, re-exec `rag sync-cli`
    # EXACTLY ONCE (guarded against a loop) so a SINGLE invocation is turn-key.
    local synced_module="$root/scripts/lib/commands/sync-cli.sh"
    if [[ -z "${RAG_SYNCCLI_REEXEC_GUARD:-}" && -f "$synced_module" && -f "$self_before" ]] \
       && ! cmp -s "$synced_module" "$self_before"; then
        info "sync-cli module changed — re-running ONCE to finish delivering the 0.8 doc-health tools…"
        rm -rf "$stage"          # the RETURN trap won't fire across exec — clean up first
        cd "$root"
        RAG_SYNCCLI_REEXEC_GUARD=1 exec "$root/rag" sync-cli
    fi

    echo
    if (( copied == 0 )); then
        fatal "sync-cli: nothing copied — the api image does not appear to carry the CLI (rebuild it with 'rag build --multikb-only')."
    fi
    success "sync-cli: CLI is now in lockstep with the running image (${changed} refreshed, $((copied - changed)) unchanged of ${copied} target(s))."
    info "config.yaml / .env / docker-compose.yml were NOT touched."
    info "Run 'rag help' to see the refreshed command list."
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat <<EOF

${BOLD}rag sync-cli${NC} — refresh the host CLI from the baked image (lockstep)

An image tag bump ships new API ${BOLD}endpoints${NC} but not new ${BOLD}rag${NC} subcommands —
those are host-side files under ${CYAN}scripts/lib/commands/${NC}. The multi-KB image bakes
the exact CLI it matches into ${CYAN}/src${NC}; this command copies it back out so the
host CLI stays in step. Run it right after ${GREEN}rag up${NC} onto a newer image tag.

${YELLOW}No rag-bootstrap source checkout needed. config.yaml / .env / docker-compose.yml
are NEVER touched.${NC}

${CYAN}Usage:${NC}
  rag sync-cli

${CYAN}Copies (only generic CLI assets; stale/removed modules are dropped):${NC}
  ${GREEN}/src/rag${NC}          -> ./rag           (dispatcher, exec bit preserved)
  ${GREEN}/src/scripts/lib${NC}  -> ./scripts/lib   (command modules + shared lib)
  ${GREEN}/src/client${NC}       -> ./client        (query helpers, if present)
  ${GREEN}/src/agent_hints${NC}  -> ./agent_hints   (agent docs, if present)
  ${GREEN}/src/ops${NC}          -> ./ops           (only if the instance already uses ops/)

${CYAN}Requires:${NC} the api container running (${GREEN}rag up${NC}) on an image built with a
rag CLI baked in (${GREEN}rag build --multikb-only${NC} at 0.4.2+). Against an older image
that carries no CLI, sync-cli reports it and makes no changes.
EOF
}
