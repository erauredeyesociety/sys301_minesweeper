# =============================================================================
# commands/relocate.sh — `rag relocate` module (thin wrapper; consumer)
# =============================================================================
# Convenience wrapper around the UNCHANGED, self-contained relocate_data.sh
# (consumer scaffolds carry it at ops/; the template checkout at scripts/). That
# tool SAFELY moves this instance's data volumes to a roomier disk (dry-run by
# default; never deletes the source until the copy is verified AND the stack is
# healthy on the new location). It derives the instance dir from $(pwd), so this
# module cd's to the dispatcher root — the instance dir for a consumer — before
# exec. The tool is never modified; every argument is forwarded verbatim.
#
# Module contract: defines exactly cmd_meta/run/help; sourcing is side-effect
# free.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "relocate||consumer|Move this instance's data volumes to a new disk (relocate_data.sh)"
}

help() {
    cat <<'RAG_RELOCATE_HELP'
rag relocate — SAFELY move this instance's data volumes to a roomier disk

Thin wrapper around relocate_data.sh (consumer: ops/relocate_data.sh). Run from
the consumer / instance directory (the one holding .env + docker-compose.yml).
Dry-run by default; --apply executes. Arguments are forwarded verbatim.

Usage:
  rag relocate --to <new-data-root>                 # DRY-RUN (plan only)
  rag relocate --to <new-data-root> --apply         # execute the relocation
  rag relocate --to <new-data-root> --apply --remove-old -y

Full flag reference + safety model: `ops/relocate_data.sh --help`.
RAG_RELOCATE_HELP
}

run() {
    local root tool cand
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    case "${1:-}" in
        -h|--help|help) help; return 0 ;;
    esac

    # consumer scaffold: ops/relocate_data.sh ; template checkout: scripts/…
    for cand in "${root}/ops/relocate_data.sh" "${root}/scripts/relocate_data.sh"; do
        if [[ -f "$cand" ]]; then tool="$cand"; break; fi
    done
    [[ -n "${tool:-}" ]] \
        || { echo "ERROR: relocate: relocate_data.sh not found (looked in ops/ and scripts/)" >&2; return 1; }

    # --dry-run IS the default here (real run needs --apply). Accept an explicit
    # --dry-run as a no-op by dropping it before forwarding: relocate_data.sh does
    # not take that flag, so forwarding it verbatim would error "unknown option".
    local -a args=(); local a
    for a in "$@"; do
        [[ "$a" == "--dry-run" ]] && continue
        args+=("$a")
    done

    # relocate_data.sh derives its instance dir from $(pwd): the dispatcher root
    # is that dir for a consumer scaffold.
    cd "$root"
    exec bash "$tool" ${args[@]+"${args[@]}"}
}
