# =============================================================================
# commands/build.sh — module for `rag build`  (audience: template / maintainer)
# =============================================================================
# Builds + tags the three rag-bootstrap distribution images into the LOCAL
# docker daemon from the repo-root VERSION file.
#
# Module contract: defines cmd_meta / help / run and nothing else at top level;
# sourcing is side-effect free.
# =============================================================================

# Locate the shared lib relative to this module (scripts/lib/commands/<cmd>.sh).
_RAG_CMD_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
# shellcheck source=../common.sh disable=SC1091
[[ -f "${_RAG_CMD_DIR}/../common.sh" ]] && source "${_RAG_CMD_DIR}/../common.sh"

# name | aliases(csv) | audience(both|consumer|template) | one-line summary
cmd_meta() {
    echo "build||template|Build + tag the three distribution images from VERSION"
}

help() {
    cat <<'EOF'
Usage: rag build [FLAGS]

Build + tag the three rag-bootstrap distribution images into the local docker
daemon from the repo-root VERSION file.

Selection (default: all three):
  --api-only          build only rag-bootstrap-api (single-KB)
  --multikb-only      build only rag-bootstrap-api-multikb
  --frontend-only     build only rag-bootstrap-frontend

Tagging:
  --version X.Y.Z     override the version read from VERSION
  --no-latest         tag only :<ver>, skip the :latest alias

Other:
  --with-rerank       bake the optional cross-encoder reranker extra
                      (sentence-transformers, pulls torch/CPU) into the api +
                      multikb images via --build-arg INSTALL_RERANK=true; default
                      OFF keeps the image torch-free (reranker.py is fail-soft)
  --dry-run           print the docker build commands, build nothing
  --push [REGISTRY]   STUB: retag + push to REGISTRY (default localhost:5000);
                      SKIPS with a notice when no registry is reachable
                      (this repo does not stand up a registry)
  -h, --help          show this help

Images built (the exact refs consumers pin):
  rag-bootstrap-api:<ver>            app/Dockerfile            ctx app/
  rag-bootstrap-api-multikb:<ver>    app/Dockerfile.multi-kb  ctx .   (bakes the rag CLI)
  rag-bootstrap-frontend:<ver>       frontend/Dockerfile      ctx frontend/
EOF
}

run() {
    # --- locate repo root (module lives in <root>/scripts/lib/commands) -------
    local REPO_ROOT VERSION_FILE
    REPO_ROOT="$(cd -- "${_RAG_CMD_DIR}/../../.." >/dev/null 2>&1 && pwd -P)"
    VERSION_FILE="${REPO_ROOT}/VERSION"

    # --- image definitions (name | dockerfile | context) ---------------------
    local API_NAME="rag-bootstrap-api"
    local API_DOCKERFILE="app/Dockerfile"
    local API_CONTEXT="app"

    local MULTIKB_NAME="rag-bootstrap-api-multikb"
    local MULTIKB_DOCKERFILE="app/Dockerfile.multi-kb"
    # Context is the REPO ROOT (".") — the multi-KB image bakes the host-side
    # `rag` CLI (rag + scripts + client + agent_hints), which live at repo root,
    # not under app/. A repo-root .dockerignore keeps secrets/dev trees out.
    local MULTIKB_CONTEXT="."

    local FRONTEND_NAME="rag-bootstrap-frontend"
    local FRONTEND_DOCKERFILE="frontend/Dockerfile"
    local FRONTEND_CONTEXT="frontend"

    # --- defaults ------------------------------------------------------------
    local BUILD_API=1
    local BUILD_MULTIKB=1
    local BUILD_FRONTEND=1
    local TAG_LATEST=1
    local WITH_RERANK=0
    local DRY_RUN=0
    local VERSION_OVERRIDE=""
    local PUSH_REGISTRY=""
    local VERSION

    # --- arg parse -----------------------------------------------------------
    local SELECT_FLAGS=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --api-only)      BUILD_API=1; BUILD_MULTIKB=0; BUILD_FRONTEND=0; SELECT_FLAGS=$((SELECT_FLAGS+1)) ;;
            --multikb-only)  BUILD_API=0; BUILD_MULTIKB=1; BUILD_FRONTEND=0; SELECT_FLAGS=$((SELECT_FLAGS+1)) ;;
            --frontend-only) BUILD_API=0; BUILD_MULTIKB=0; BUILD_FRONTEND=1; SELECT_FLAGS=$((SELECT_FLAGS+1)) ;;
            --no-latest)     TAG_LATEST=0 ;;
            --with-rerank)   WITH_RERANK=1 ;;
            --dry-run)       DRY_RUN=1 ;;
            --version)
                [[ $# -ge 2 ]] || { echo "ERROR: --version needs an argument" >&2; exit 2; }
                VERSION_OVERRIDE="$2"; shift ;;
            --version=*)     VERSION_OVERRIDE="${1#*=}" ;;
            --push)
                # Optional argument: next token is the registry unless it's a flag.
                if [[ $# -ge 2 && "$2" != --* ]]; then
                    PUSH_REGISTRY="$2"; shift
                else
                    PUSH_REGISTRY="localhost:5000"
                fi ;;
            --push=*)        PUSH_REGISTRY="${1#*=}" ;;
            -h|--help)       help; exit 0 ;;
            *) echo "ERROR: unknown argument: $1" >&2; help >&2; exit 2 ;;
        esac
        shift
    done

    # Guard against combining more than one *-only selector.
    if [[ $SELECT_FLAGS -gt 1 ]]; then
        echo "ERROR: --api-only / --multikb-only / --frontend-only are mutually exclusive" >&2
        exit 2
    fi

    # --- resolve version -----------------------------------------------------
    if [[ -n "$VERSION_OVERRIDE" ]]; then
        VERSION="$VERSION_OVERRIDE"
    else
        if [[ ! -f "$VERSION_FILE" ]]; then
            echo "ERROR: VERSION file not found at ${VERSION_FILE}" >&2
            exit 1
        fi
        VERSION="$(head -n 1 "$VERSION_FILE" | tr -d '[:space:]')"
    fi

    # Tag integrity: never emit an empty or non-semver tag.
    if [[ -z "$VERSION" ]]; then
        echo "ERROR: version is empty (VERSION file blank or --version empty)" >&2
        exit 1
    fi
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+.][0-9A-Za-z.-]+)?$ ]]; then
        echo "ERROR: version '${VERSION}' is not a valid semver (X.Y.Z)" >&2
        exit 1
    fi

    # --- helpers -------------------------------------------------------------
    # Emit one `docker build` command line for an image (with -t tags).
    build_line() {
        local name="$1" dockerfile="$2" context="$3"
        local line="docker build -t ${name}:${VERSION}"
        if [[ $TAG_LATEST -eq 1 ]]; then
            line+=" -t ${name}:latest"
        fi
        # Optional reranker extra: only the Python images consume INSTALL_RERANK
        # (the frontend Dockerfile would warn on an unused build-arg).
        if [[ $WITH_RERANK -eq 1 && "$name" != "$FRONTEND_NAME" ]]; then
            line+=" --build-arg INSTALL_RERANK=true"
        fi
        line+=" -f ${dockerfile} ${context}"
        printf '%s' "$line"
    }

    # Build (or, in dry-run, print) one image.
    run_build() {
        local name="$1" dockerfile="$2" context="$3"
        local cmd
        cmd="$(build_line "$name" "$dockerfile" "$context")"
        if [[ $DRY_RUN -eq 1 ]]; then
            printf '%s\n' "$cmd"
            return 0
        fi
        echo ">>> Building ${name}:${VERSION}"
        ( cd -- "$REPO_ROOT" && eval "$cmd" )
    }

    # --- run builds ----------------------------------------------------------
    if [[ $DRY_RUN -ne 1 ]]; then
        echo "== rag-bootstrap image build =="
        echo "   version : ${VERSION}"
        echo "   latest  : $([[ $TAG_LATEST -eq 1 ]] && echo yes || echo no)"
        echo "   repo    : ${REPO_ROOT}"
        echo
    fi

    [[ $BUILD_API      -eq 1 ]] && run_build "$API_NAME"      "$API_DOCKERFILE"      "$API_CONTEXT"
    [[ $BUILD_MULTIKB  -eq 1 ]] && run_build "$MULTIKB_NAME"  "$MULTIKB_DOCKERFILE"  "$MULTIKB_CONTEXT"
    [[ $BUILD_FRONTEND -eq 1 ]] && run_build "$FRONTEND_NAME" "$FRONTEND_DOCKERFILE" "$FRONTEND_CONTEXT"

    # --- dry-run stops here --------------------------------------------------
    if [[ $DRY_RUN -eq 1 ]]; then
        exit 0
    fi

    # --- frontend lockstep on --multikb-only ---------------------------------
    # A release must publish BOTH images at a tag: .env's single RAG_IMAGE_TAG
    # selects api AND frontend, so a `--multikb-only --version X` build leaves
    # the frontend tag missing and `rag up` tears the stack down. Auto-retag the
    # newest existing frontend image to :${VERSION} (the frontend is unchanged
    # when only the backend moved). Skip gracefully if no frontend image exists.
    if [[ $BUILD_MULTIKB -eq 1 && $BUILD_FRONTEND -eq 0 ]]; then
        local fe_src=""
        if docker image inspect "${FRONTEND_NAME}:latest" >/dev/null 2>&1; then
            fe_src="${FRONTEND_NAME}:latest"
        else
            # No :latest (e.g. built with --no-latest). Fall back to the newest
            # existing frontend tag by creation time.
            local fe_tag
            fe_tag="$(docker image ls "${FRONTEND_NAME}" \
                --format '{{.Tag}}\t{{.CreatedAt}}' 2>/dev/null \
                | grep -v $'^<none>\t' | sort -k2 | tail -n1 | cut -f1 || true)"
            [[ -n "$fe_tag" ]] && fe_src="${FRONTEND_NAME}:${fe_tag}"
        fi
        if [[ -n "$fe_src" ]]; then
            if [[ "$fe_src" == "${FRONTEND_NAME}:${VERSION}" ]]; then
                echo ">>> Frontend ${FRONTEND_NAME}:${VERSION} already present — kept in lockstep."
            else
                docker tag "$fe_src" "${FRONTEND_NAME}:${VERSION}"
                echo ">>> Retagged ${fe_src} -> ${FRONTEND_NAME}:${VERSION} (frontend kept in lockstep with --multikb-only)."
            fi
        else
            echo "WARN: no ${FRONTEND_NAME} image to retag — the ${VERSION} tag will be api-only."
            echo "      Build the frontend too (rag build --frontend-only --version ${VERSION}) so the pair exists."
        fi
    fi

    # --- summary: image ls + the refs consumers pin --------------------------
    echo
    echo "== built images (rag-bootstrap-*) =="
    docker image ls --filter 'reference=rag-bootstrap-*' \
        --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' || true

    echo
    echo "== image refs to pin in consumer compose (image:) =="
    [[ $BUILD_API      -eq 1 ]] && echo "  ${API_NAME}:${VERSION}"
    [[ $BUILD_MULTIKB  -eq 1 ]] && echo "  ${MULTIKB_NAME}:${VERSION}"
    [[ $BUILD_FRONTEND -eq 1 ]] && echo "  ${FRONTEND_NAME}:${VERSION}"
    echo "  (or set RAG_IMAGE_TAG=${VERSION} against the :latest aliases)"

    # --- push stub (SKIPS with no reachable registry) ------------------------
    if [[ -n "$PUSH_REGISTRY" ]]; then
        echo
        echo "== push (stub) → ${PUSH_REGISTRY} =="
        # Probe the registry's /v2/ endpoint; SKIP if unreachable. This repo does
        # NOT stand up a registry — pushing is a future, out-of-scope step.
        local reg_host="${PUSH_REGISTRY%%/*}"
        if command -v curl >/dev/null 2>&1 \
            && curl -fsS --max-time 3 "http://${reg_host}/v2/" >/dev/null 2>&1; then
            echo "   registry ${reg_host} reachable — retag + push:"
            local pair name want
            for pair in \
                "${API_NAME}:${BUILD_API}" \
                "${MULTIKB_NAME}:${BUILD_MULTIKB}" \
                "${FRONTEND_NAME}:${BUILD_FRONTEND}"; do
                name="${pair%:*}"; want="${pair##*:}"
                [[ "$want" -eq 1 ]] || continue
                echo "     docker tag ${name}:${VERSION} ${PUSH_REGISTRY}/${name}:${VERSION}"
                docker tag  "${name}:${VERSION}" "${PUSH_REGISTRY}/${name}:${VERSION}"
                echo "     docker push ${PUSH_REGISTRY}/${name}:${VERSION}"
                docker push "${PUSH_REGISTRY}/${name}:${VERSION}"
            done
        else
            echo "   SKIP: no registry reachable at ${reg_host} (/v2/ probe failed)."
            echo "   This repo does not stand up a registry — local daemon tags only."
            echo "   See docs/deployment/DISTRIBUTION.md (registry:2 is future-only)."
        fi
    fi
}
