# shellcheck shell=bash
# =============================================================================
# rag status — Show service status and health
# =============================================================================
# run() is the `show_status` body verbatim; helpers from ../common.sh.

cmd_meta() {
    echo "status||both|Show service status and health"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    echo ""
    printf "${BOLD}RAG Bootstrap Status${NC}\n"
    echo "===================="
    echo ""

    docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || {
        warn "Services not running"
        return 1
    }

    echo ""

    # Show health if running
    local port
    port="$(resolved_port)"
    if curl -sf "http://localhost:${port}/api/health" >/dev/null 2>&1; then
        local health
        health=$(curl -sf "http://localhost:${port}/api/health")

        echo "Health Status:"
        echo "$health" | python3 -c "
import sys, json
h = json.load(sys.stdin)
print(f\"  Overall:    {h['status'].upper()}\")
print(f\"  Database:   {'OK' if h['database'] else 'FAIL'}\")
print(f\"  Redis:      {'OK' if h['redis'] else 'FAIL'}\")
print(f\"  Embedding:  {'OK' if h['embedding_service'] else 'FAIL'}\")
print(f\"  LLM:        {'OK' if h['llm'] else 'FAIL'}\")
" 2>/dev/null || echo "  (Could not parse health response)"

        # Self-healing posture: the app runs a periodic in-process reconcile
        # (default-ON) that picks up add/modify/delete with no redeploy. An
        # unchanged corpus re-embeds nothing (content-hash short-circuit).
        local reconcile_enabled reconcile_interval
        reconcile_enabled="$(env_get RECONCILE_ENABLED)"; reconcile_enabled="${reconcile_enabled,,}"
        reconcile_interval="$(env_get RECONCILE_INTERVAL_SECONDS)"
        reconcile_interval="${reconcile_interval:-300}"
        echo ""
        if [[ "$reconcile_enabled" == "false" ]]; then
            echo "Self-healing:  periodic reconcile OFF — run './rag sync' to pick up file changes"
        else
            echo "Self-healing:  periodic reconcile ON every ${reconcile_interval}s (auto add/modify/delete; no redeploy)"
        fi

        echo ""
        echo "Access the UI at: http://localhost:${port}"
    fi
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag status${NC} — Show service status and health

${CYAN}Usage:${NC}
  rag status

Prints the compose service table, a component health summary, the self-healing
reconcile cadence, and the UI URL.
EOF
}
