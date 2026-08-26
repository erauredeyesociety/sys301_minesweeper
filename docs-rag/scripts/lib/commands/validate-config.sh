# shellcheck shell=bash
# =============================================================================
# commands/validate-config.sh — module for `rag validate-config`  (both)
# =============================================================================
# THIN wrapper around GET /api/admin/validate-config. All the logic — the
# structured Config.validate_detailed() checks, the line resolution — lives in
# the app (app/config_manager.py + app/admin_api.py). This script only AUTOMATES
# calling that endpoint and pretty-prints the result: either "config valid" or
# each bad parameter with its config.yaml line + a concrete fix. NO business
# logic. It is a focused alias of the `rag diagnose` "Config validation" section
# and hits the EXACT SAME endpoint — one accountable path, no second checker.
#
# READ-ONLY: the endpoint reads config only (no DB session, no writes).
#
# HONEST: if the instance is down / the endpoint doesn't answer, this reports
# UNKNOWN (non-zero exit), never a fake "valid". If the endpoint says
# valid=false, exit is non-zero.
#
# Module contract: defines exactly cmd_meta / run / help; sourcing is
# side-effect free. Runs under the dispatcher's `set -euo pipefail`.
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "validate-config|valcfg,validate|both|Validate config.yaml — names bad params + line + fix (READ-ONLY)"
}

run() {
    if ! command -v resolved_port >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local as_json=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; return 0 ;;
            --json) as_json=1; shift ;;
            -*) fatal "validate-config: unknown option: $1 (use --help)" ;;
            *)  fatal "validate-config: unexpected argument: $1 (use --help)" ;;
        esac
    done

    parse_config
    local port url
    port="$(resolved_port)"
    url="http://localhost:${port}/api/admin/validate-config"

    info "GET ${url}  (READ-ONLY — no writes)"

    # HONEST: a failed request means correctness is UNKNOWN, not valid.
    local resp
    resp="$(curl -sf --max-time 10 "$url")" \
        || fatal "validate-config: request failed — config correctness UNKNOWN (is the instance up? try './rag status'). Endpoint: ${url}"

    if [[ -n "$as_json" ]]; then
        printf '%s\n' "$resp"
        # Exit non-zero when invalid so --json is scriptable too.
        printf '%s' "$resp" | python3 -c 'import sys,json; sys.exit(0 if json.load(sys.stdin).get("valid") else 2)' 2>/dev/null
        return $?
    fi

    _valcfg_render "$resp"
}

# --- helpers (module-local; underscore-prefixed) -----------------------------

# Pretty-print the ValidateConfigResponse JSON passed as $1. Returns non-zero
# when the config is invalid (or the body is unparseable), so `rag
# validate-config` has a meaningful exit code.
_valcfg_render() {
    RAG_RESP="$1" python3 - <<'PY'
import os, json, sys

try:
    r = json.loads(os.environ["RAG_RESP"])
except Exception as e:
    print("validate-config: could not parse response: %s" % e, file=sys.stderr)
    sys.exit(2)

issues = r.get("issues", []) or []
errs  = [i for i in issues if i.get("severity") == "error"]
warns = [i for i in issues if i.get("severity") == "warning"]
valid = bool(r.get("valid")) and not errs
checked = r.get("checked", 0)

print()
print("RAG Config Validation — READ-ONLY")
print("=" * 60)
print("config : %s" % (r.get("config_path") or "(unknown)"))
print("checks : %s run" % checked)
print("-" * 60)

def line(i):
    ln = i.get("line")
    return ("line %s" % ln) if ln else "line ?"

if valid:
    print("OK  config valid — %s checks, 0 errors, %d warning(s)" % (checked, len(warns)))
else:
    print("FAIL  %d config error(s) across %s checks:" % (len(errs), checked))
    for i in errs:
        doc = i.get("doc") or ""
        doc = ("  [%s]" % doc) if doc else ""
        print("  ✗ %s (%s)" % (i.get("param", "?"), line(i)))
        print("      problem: %s" % i.get("problem", ""))
        print("      fix    : %s%s" % (i.get("fix", ""), doc))

if warns:
    print()
    print("warnings (advisory — do not block valid):")
    for i in warns:
        print("  ! %s (%s): %s" % (i.get("param", "?"), line(i), i.get("problem", "")))
        print("      fix: %s" % i.get("fix", ""))

note = r.get("note")
if note:
    print()
    print(note)

sys.exit(0 if valid else 2)
PY
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh disable=SC1091
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat <<EOF

${BOLD}rag validate-config${NC} — is config.yaml good?  (aliases: ${GREEN}valcfg${NC}, ${GREEN}validate${NC})

Thin wrapper around ${CYAN}GET /api/admin/validate-config${NC} (the SAME endpoint the
${GREEN}rag diagnose${NC} "Config validation" section uses — one accountable path). It either
prints ${BOLD}config valid${NC} or names each bad parameter with its config.yaml ${BOLD}line${NC}
and a concrete ${BOLD}fix${NC}.

${YELLOW}READ-ONLY — reads config only; no DB session, nothing written.${NC}
${YELLOW}HONEST — if the instance is down or the endpoint can't answer, correctness is${NC}
${YELLOW}reported UNKNOWN (non-zero exit), never a fake "valid".${NC}

${CYAN}Usage:${NC}
  rag validate-config [--json]

${CYAN}Options:${NC}
  ${GREEN}--json${NC}      Print the raw JSON response instead of the table.
  ${GREEN}-h, --help${NC}  This help.

${CYAN}Exit code:${NC} 0 = config valid; 2 = invalid (errors named above); non-zero on
an unreachable endpoint (correctness UNKNOWN).

${CYAN}Examples:${NC}
  rag validate-config            # human-readable pass/fail + fixes
  rag validate-config --json     # raw JSON (scriptable; exit 2 when invalid)
EOF
}
