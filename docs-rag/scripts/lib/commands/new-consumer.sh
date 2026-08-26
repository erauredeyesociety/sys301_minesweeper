# =============================================================================
# commands/new-consumer.sh — `rag new-consumer` module (template-only)
# =============================================================================
# Stamps a docs-free, image-mode RAG consumer deployment dir. Image-mode
# scaffolds also receive the unified `rag` dispatcher + scripts/lib/ + the
# standalone ops tools so consumers get `rag up/doctor/status/...`.
#
# Module contract: defines exactly cmd_meta/run/help at top level; sourcing is
# side-effect free. All private helpers live INSIDE run().
# =============================================================================

cmd_meta() {
    # name | aliases(csv) | audience(both|consumer|template) | one-line summary
    echo "new-consumer||template|Stamp a docs-free, image-mode RAG consumer deployment dir"
}

help() {
    # (quoted heredoc: nothing below is expanded).
    cat <<'RAG_NC_HELP'
=============================================================================
rag new-consumer — stamp a docs-free, image-mode RAG consumer deployment dir
=============================================================================
Creates a self-contained CONSUMER directory that runs PRE-BUILT rag-bootstrap
images (built on this host by `rag build` — no registry). The
stamped dir carries ZERO application source and ZERO docs: only a compose file
(image: refs), a rendered .env, the query client, agent hints, per-KB ops
tooling, and (multi-KB only) a config.yaml stub + a generated RUN.md.

Usage:
  rag new-consumer <name> <port-base> <docs-path> [options]

Arguments:
  <name>        instance identity (COMPOSE_PROJECT_NAME / network prefix).
                [a-z0-9][a-z0-9._-]* — no spaces, no path separators.
  <port-base>   published-port band base. Multiple of 20, >= 10020, and FREE
                (checked via `ss -ltn`). 10040 (live docs stack) is refused.
  <docs-path>   absolute host path to this instance's docs root (DOCS_PATH).

Options:
  --mode single|multikb   deployment shape (default: single).
  --data-root <dir>       bind-mount data root (default: <out>/data).
  --tag <tag>             RAG_IMAGE_TAG to pin (default: latest).
  --out <dir>             target directory (default: ./consumers/<name>).
  -h, --help              this help.

Guarantees:
  * Refuses to overwrite an existing non-empty target.
  * All interpolated args are validated + quoted (no eval, no ../ traversal).
  * .env is written mode 600 and NEVER auto-committed.
  * The stamped dir contains no docs/, no app/*.py, no frontend/ source.
=============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATES="${REPO_ROOT}/templates"

die()  { echo "ERROR: $*" >&2; exit 1; }
note() { echo "  $*" >&2; }

Reject values that would corrupt the generated .env / config.yaml when
substituted (they are written UNQUOTED into `KEY=val` lines and into
`ingest_dirs: ["__DOCS_PATH__"]`). No eval is involved, but an embedded
RAG_NC_HELP
}

run() {
    set -euo pipefail

    # Repo (template) root: module lives at scripts/lib/commands/, so ../../..
    # resolves to the template checkout root (where templates/ + client/ live).
    local REPO_ROOT TEMPLATES
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
    TEMPLATES="${REPO_ROOT}/templates"

    die()  { echo "ERROR: $*" >&2; exit 1; }
    note() { echo "  $*" >&2; }

    # Reject values that would corrupt the generated .env / config.yaml when
    # substituted (they are written UNQUOTED into `KEY=val` lines and into
    # `ingest_dirs: ["__DOCS_PATH__"]`). No eval is involved, but an embedded
    # newline could inject an extra KEY=val line and a quote/backtick could break
    # YAML/env quoting. $1 = human label, $2 = value.
    reject_unsafe() {
        [[ "$2" != *[[:cntrl:]]* ]] \
            || die "invalid ${1}: contains a control character (newline/tab/etc.)"
        case "$2" in
            *\"*|*\'*|*\`*) die "invalid ${1}: must not contain quote or backtick characters" ;;
        esac
    }

    # --- parse args ----------------------------------------------------------
    local MODE="single"
    local DATA_ROOT=""
    local TAG="latest"
    local OUT=""
    local POS=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) help; exit 0 ;;
            --mode)    MODE="${2:-}"; shift 2 ;;
            --data-root) DATA_ROOT="${2:-}"; shift 2 ;;
            --tag)     TAG="${2:-}"; shift 2 ;;
            --out)     OUT="${2:-}"; shift 2 ;;
            --) shift; while [[ $# -gt 0 ]]; do POS+=("$1"); shift; done ;;
            -*) die "unknown option: $1 (use --help)" ;;
            *)  POS+=("$1"); shift ;;
        esac
    done

    [[ ${#POS[@]} -eq 3 ]] || { help; echo >&2; die "expected 3 positional args (name port-base docs-path), got ${#POS[@]}"; }
    local NAME="${POS[0]}"
    local PORT_BASE="${POS[1]}"
    local DOCS_PATH="${POS[2]}"

    # --- validate: name (identity; no traversal / shell metachars) -----------
    reject_unsafe "<name>" "$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9._-]*$ ]] \
        || die "invalid <name> '${NAME}': use [a-z0-9][a-z0-9._-]* (no spaces/slashes)"
    [[ "$NAME" != *".."* ]] || die "invalid <name>: must not contain '..'"

    # --- validate: mode ------------------------------------------------------
    case "$MODE" in
        single|multikb) ;;
        *) die "invalid --mode '${MODE}': expected 'single' or 'multikb'" ;;
    esac

    # --- validate: tag (image tag charset) -----------------------------------
    [[ "$TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
        || die "invalid --tag '${TAG}': use docker tag charset [A-Za-z0-9._-]"

    # --- validate: port-base -------------------------------------------------
    [[ "$PORT_BASE" =~ ^[0-9]+$ ]] || die "invalid <port-base> '${PORT_BASE}': not a number"
    (( PORT_BASE % 20 == 0 ))      || die "invalid <port-base> ${PORT_BASE}: must be a multiple of 20"
    (( PORT_BASE >= 10020 ))       || die "invalid <port-base> ${PORT_BASE}: must be >= 10020 (10000-10019 reserved for the base stack)"
    (( PORT_BASE <= 65515 ))       || die "invalid <port-base> ${PORT_BASE}: band would exceed 65535"
    (( PORT_BASE != 10040 ))       || die "refusing <port-base> 10040: reserved for the live docs-rag multi-KB stack"

    # Free-port check: the published web port is PORT_BASE+0. Guard the whole
    # reserved band [base .. base+19] against anything currently LISTENING.
    if command -v ss >/dev/null 2>&1; then
        local listening
        listening="$(ss -ltnH 2>/dev/null | awk '{print $4}' | sed 's/.*://')"
        local off p
        for off in 0 10 11 12 13 14 15 16; do
            p=$(( PORT_BASE + off ))
            if grep -qx "$p" <<<"$listening"; then
                die "port ${p} (base+${off}) is already in use — pick a free <port-base>"
            fi
        done
    else
        note "WARNING: 'ss' not found — skipping free-port check; verify ${PORT_BASE} is free."
    fi

    # --- validate: docs-path (absolute, no traversal, no control/quote chars) --
    reject_unsafe "<docs-path>" "$DOCS_PATH"
    [[ "$DOCS_PATH" = /* ]]        || die "invalid <docs-path> '${DOCS_PATH}': must be an ABSOLUTE path"
    [[ "$DOCS_PATH" != *".."* ]]   || die "invalid <docs-path>: must not contain '..'"

    # --- resolve output dir; refuse overwrite --------------------------------
    [[ -n "$OUT" ]] || OUT="${REPO_ROOT}/consumers/${NAME}"
    case "$OUT" in *".."*) die "invalid --out: must not contain '..'";; esac
    # Absolute-ize (without requiring existence) for the source-tree guard below.
    case "$OUT" in /*) : ;; *) OUT="$(pwd)/${OUT#./}" ;; esac
    # GUARD: an instance is a DEPLOYMENT, not part of the template — it must NEVER
    # live inside the rag-bootstrap SOURCE tree. The default (./consumers/<name>)
    # lands here and is the exact mistake docs/deployment/DISTRIBUTION.md warns
    # about, so refuse it and point at the right place.
    case "${OUT%/}/" in
        "${REPO_ROOT%/}/"*)
            die "refusing to scaffold an instance inside the rag-bootstrap source repo:
    ${OUT}
  An instance must live OUTSIDE ${REPO_ROOT} — in your project's own repo (config
  version-controlled with the project) or a dedicated instances dir, with its data
  on a data drive. Re-run with an explicit --out (and --data-root), e.g.:
    rag new-consumer ${NAME} <port-base> <docs> \\
      --out <your-project>/docs-rag --data-root /mnt/<drive>/${NAME}
  See ${REPO_ROOT}/docs/deployment/DISTRIBUTION.md (Where a docs-rag instance lives)." ;;
    esac
    if [[ -e "$OUT" ]]; then
        [[ -d "$OUT" ]] || die "target exists and is not a directory: ${OUT}"
        if [[ -n "$(ls -A "$OUT" 2>/dev/null)" ]]; then
            die "target directory is non-empty (refusing to overwrite): ${OUT}"
        fi
    fi

    # --- resolve data root ---------------------------------------------------
    [[ -n "$DATA_ROOT" ]] || DATA_ROOT="${OUT}/data"
    case "$DATA_ROOT" in *".."*) die "invalid --data-root: must not contain '..'";; esac

    # --- render --------------------------------------------------------------
    mkdir -p "$OUT"
    # Absolute-ize OUT for downstream paths / RUN.md.
    OUT="$(cd "$OUT" && pwd)"

    # compose (image mode) — verbatim template, no substitution needed.
    if [[ "$MODE" == "single" ]]; then
        cp "${TEMPLATES}/consumer-compose.single.yml" "${OUT}/docker-compose.yml"
    else
        cp "${TEMPLATES}/consumer-compose.multikb.yml" "${OUT}/docker-compose.yml"
    fi

    # .env — substitute placeholders via a NON-eval, delimiter-safe python pass.
    NAME="$NAME" PORT_BASE="$PORT_BASE" DOCS_PATH="$DOCS_PATH" \
    DATA_ROOT="$DATA_ROOT" TAG="$TAG" \
    python3 - "${TEMPLATES}/consumer.env.template" "${OUT}/.env" <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
t = open(src).read()
for k, v in (("__PROJECT__", os.environ["NAME"]),
             ("__PORT_BASE__", os.environ["PORT_BASE"]),
             ("__DOCS_PATH__", os.environ["DOCS_PATH"]),
             ("__DATA_ROOT__", os.environ["DATA_ROOT"])):
    t = t.replace(k, v)
# RAG_IMAGE_TAG line pin (leave 'latest' default replaced by chosen tag).
t = t.replace("RAG_IMAGE_TAG=latest", "RAG_IMAGE_TAG=" + os.environ["TAG"])
# Create the .env with mode 0600 AT OPEN TIME (os.open honors the mode arg,
# masked only by umask) so there is no world/group-readable window between
# creation and a later chmod. The chmod below is a belt-and-suspenders backstop.
fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(t)
PY
    chmod 600 "${OUT}/.env"

    # Config-safety by default: a version-controllable .env.example (the ONE secret
    # redacted) + a .gitignore, so the instance is reconstructable from git even if
    # the disk is lost, WITHOUT ever committing the real password or regenerable
    # data. The real .env stays here (mode 600, git-ignored).
    sed 's|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=CHANGEME_generate_with_openssl_rand_hex_24|' \
        "${OUT}/.env" > "${OUT}/.env.example"
    cat > "${OUT}/.gitignore" <<'GITIGN'
# Config-safety net: never commit the real secret-bearing .env or regenerable
# data. Only .env.example (redacted) is tracked; reconstruct .env from it and set
# a fresh POSTGRES_PASSWORD (e.g. `openssl rand -hex 24`).
.env
.env.*
!.env.example
data/
*.bak
*.pre-*
GITIGN

    # config.yaml stub — MULTI-KB only.
    if [[ "$MODE" == "multikb" ]]; then
        NAME="$NAME" PORT_BASE="$PORT_BASE" DOCS_PATH="$DOCS_PATH" \
        python3 - "${TEMPLATES}/consumer-config.example.yaml" "${OUT}/config.yaml" <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
t = open(src).read()
for k, v in (("__PROJECT__", os.environ["NAME"]),
             ("__PORT_BASE__", os.environ["PORT_BASE"]),
             ("__DOCS_PATH__", os.environ["DOCS_PATH"])):
    t = t.replace(k, v)
open(dst, "w").write(t)
PY
    fi

    # client (query contract) — ragq.py + fallback_policy.py (ragq imports it).
    mkdir -p "${OUT}/client"
    cp "${REPO_ROOT}/client/ragq.py" "${OUT}/client/ragq.py"
    [[ -f "${REPO_ROOT}/client/fallback_policy.py" ]] \
        && cp "${REPO_ROOT}/client/fallback_policy.py" "${OUT}/client/fallback_policy.py"

    # agent_hints (agent-facing usage).
    mkdir -p "${OUT}/agent_hints"
    cp "${REPO_ROOT}/agent_hints/"*.md "${OUT}/agent_hints/" 2>/dev/null || true

    # ops (per-KB tooling; ingest/migrate run inside the api container).
    mkdir -p "${OUT}/ops"
    cp "${REPO_ROOT}/scripts/ingest_kb.py"       "${OUT}/ops/ingest_kb.py"
    cp "${REPO_ROOT}/scripts/migrate_indexes.py" "${OUT}/ops/migrate_indexes.py"
    # relocate_data.sh runs on the HOST (from this consumer dir), NOT in-container:
    # a SAFE helper to move this instance's data volumes to a roomier disk.
    cp "${REPO_ROOT}/scripts/relocate_data.sh"   "${OUT}/ops/relocate_data.sh"
    chmod +x "${OUT}/ops/relocate_data.sh"

    # unified CLI — ship the `rag` dispatcher + scripts/lib/ into the scaffold so
    # image-mode consumers get `rag doctor/status/...` alongside `docker compose`
    # (template-only commands stay hidden here via the dispatcher's context
    # detection). Copied only when present in this checkout; their absence never
    # blocks scaffolding.
    if [[ -f "${REPO_ROOT}/rag" && -d "${REPO_ROOT}/scripts/lib" ]]; then
        cp "${REPO_ROOT}/rag" "${OUT}/rag"
        chmod +x "${OUT}/rag"
        mkdir -p "${OUT}/scripts"
        cp -R "${REPO_ROOT}/scripts/lib" "${OUT}/scripts/lib"
    fi

    # RUN.md — generated quickstart (NOT copied from docs/).
    cat > "${OUT}/RUN.md" <<EOF
# ${NAME} — RAG consumer (${MODE} mode)

Generated by \`rag new-consumer\` on $(date +%F). Runs PRE-BUILT
rag-bootstrap images (RAG_IMAGE_TAG=${TAG}). No application source lives here.

## Prerequisites
- Images built on THIS host: \`rag build\` in the canonical repo.
- Ollama reachable with the embedding model: \`ollama pull nomic-embed-text\`.

## Boot
\`\`\`sh
docker compose up -d          # web UI on http://127.0.0.1:${PORT_BASE}
docker compose logs -f api
\`\`\`

## Query
\`\`\`sh
RAG_ENDPOINT_URL=http://127.0.0.1:${PORT_BASE} python3 client/ragq.py "your question"
curl -sf -X POST http://127.0.0.1:${PORT_BASE}/api/v1/search \\
  -H 'Content-Type: application/json' -d '{"query":"...","limit":5}'
\`\`\`

## Ingest / index (per KB, inside the api container)
\`\`\`sh
docker compose run --rm --no-deps -v "\$PWD/ops:/src/scripts:ro" \\
  api python /src/scripts/ingest_kb.py --kb <name>
\`\`\`

## Relocate data to a roomier disk (SAFE; run from THIS dir)
Moves this instance's data volumes (RAG_*_VOLUME) to a new root, verifies the
copy, repoints .env, and restarts on the new location — never deleting the
source until it is verified AND the stack is healthy. Dry-run by default:
\`\`\`sh
bash ops/relocate_data.sh --to /mnt/quickiespace/${NAME}            # plan only
bash ops/relocate_data.sh --to /mnt/quickiespace/${NAME} --apply    # execute
\`\`\`
EOF

    echo "Scaffolded ${MODE} consumer at: ${OUT}" >&2
    echo "  next: review ${OUT}/.env (POSTGRES_PASSWORD!), then 'cd ${OUT} && docker compose up -d'" >&2
    echo "$OUT"
}
