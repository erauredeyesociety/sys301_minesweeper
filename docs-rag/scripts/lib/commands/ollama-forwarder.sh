# shellcheck shell=bash
# =============================================================================
# rag ollama-forwarder — Print rootless Ollama TCP-forwarder setup
# =============================================================================
# run() is the `cmd_ollama_forwarder` body verbatim; helpers from
# ../common.sh (only info() is used here).

cmd_meta() {
    echo "ollama-forwarder||both|Print rootless Ollama TCP-forwarder setup"
}

run() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi

    local unit_dir="${HOME}/.config/systemd/user"
    cat << 'EOF'

Ollama connectivity modes
=========================
The stack reaches Ollama through OLLAMA_BASE_URL (.env). Three supported modes:

  1. LOCAL (default): Ollama runs on this host, containers reach it via
     host.docker.internal (host-gateway). If Ollama only listens on 127.0.0.1,
     containers CANNOT reach it — use the rootless forwarder below, or set
     OLLAMA_HOST=0.0.0.0 for the Ollama service (wider exposure).

  2. REMOTE: point OLLAMA_BASE_URL at the remote host directly, e.g.
     OLLAMA_BASE_URL=http://gpu-box.example:11434

  3. SSH BRIDGE: forward a remote Ollama to this host, then use mode 1:
     ssh -N -L 11434:localhost:11434 user@gpu-box

Rootless TCP forwarder (mode 1 fix; no root, no OLLAMA_HOST change)
-------------------------------------------------------------------
Forwards the Docker bridge address (host-gateway target, default 172.17.0.1)
port 11434 to Ollama on 127.0.0.1:11434. Requires: socat.

One-off (foreground):

  socat TCP-LISTEN:11434,bind=172.17.0.1,fork,reuseaddr TCP:127.0.0.1:11434

Persistent systemd --user unit — save the block below to
~/.config/systemd/user/rag-ollama-forward.service :

  [Unit]
  Description=RAG Bootstrap - forward Ollama 11434 to Docker bridge (rootless)
  After=network.target

  [Service]
  ExecStart=/usr/bin/socat TCP-LISTEN:11434,bind=172.17.0.1,fork,reuseaddr TCP:127.0.0.1:11434
  Restart=on-failure
  RestartSec=3

  [Install]
  WantedBy=default.target

Then enable it:

  mkdir -p ~/.config/systemd/user
  systemctl --user daemon-reload
  systemctl --user enable --now rag-ollama-forward.service
  # survive logout: loginctl enable-linger $USER

Verify from a container's perspective:

  curl -s http://172.17.0.1:11434/api/tags | head -c 200

EOF
    info "Template printed above; unit path: ${unit_dir}/rag-ollama-forward.service"
}

help() {
    if ! command -v env_get >/dev/null 2>&1; then
        # shellcheck source=../common.sh
        source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../common.sh"
    fi
    cat << EOF

${BOLD}rag ollama-forwarder${NC} — Ollama connectivity help

${CYAN}Usage:${NC}
  rag ollama-forwarder

Prints the three Ollama connectivity modes and a rootless socat TCP-forwarder
(plus a systemd --user unit) for reaching a 127.0.0.1-only Ollama from
containers.
EOF
}
