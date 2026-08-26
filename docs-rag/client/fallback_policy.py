"""Shared RAG fallback policy for consuming agents.

Canonical implementation of the endpoint-discovery, retry, and fallback rules
in ``docs/integration/CONSUMING_AGENTS_CONTRACT.md`` (sections 1 and 4).
Stdlib-only on purpose: consuming projects can import or vendor this single
file without installing anything.

Library usage::

    from fallback_policy import search, format_citation, RagUnavailable

    try:
        hits = search("how does the watcher archive files?", limit=5)
        for hit in hits:
            print(format_citation(hit), hit["content"][:200])
    except RagUnavailable as exc:
        # Contract section 4: use grep + Read for the rest of this turn.
        print(exc.advice)

Endpoint discovery only::

    from fallback_policy import resolve_endpoint
    url = resolve_endpoint()  # RAG_ENDPOINT_URL -> ~/.config/rag/endpoint.json -> default
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass
from pathlib import Path

# Canonical port scheme: RAG_PORT_BASE=10000, web entrypoint at base+0.
DEFAULT_ENDPOINT = "http://127.0.0.1:10000"
ENDPOINT_ENV_VAR = "RAG_ENDPOINT_URL"
ENDPOINT_CONFIG_FILE = Path.home() / ".config" / "rag" / "endpoint.json"

# Pin /api/v1/search; /api/search is the same handler kept for legacy
# consumers. A 404/405 on the v1 path means an older server — fall through.
SEARCH_PATHS = ("/api/v1/search", "/api/search")
# Multi-KB gateway (kb= selection). Tried first only when kb is requested;
# servers lacking it (404/405) or with it unconfigured (503) degrade to v1
# with a loud RuntimeWarning — the kb filter is NOT honored on v1.
V2_SEARCH_PATH = "/api/v2/search"
HEALTH_PATH = "/api/health"
INDEX_HEALTH_PATH = "/health/index"

FALLBACK_ADVICE = (
    "RAG unavailable: fall back to grep + Read against the source tree for the "
    "remainder of this turn. Do not block the workflow on RAG."
)


class RagError(RuntimeError):
    """Base class for RAG client errors."""


class RagUnavailable(RagError):
    """RAG could not be reached (after retry). Carries the fallback advice."""

    def __init__(self, message: str, advice: str = FALLBACK_ADVICE) -> None:
        super().__init__(message)
        self.advice = advice


class RagRequestError(RagError):
    """The server rejected the request (4xx). Fix the request; do not retry."""


@dataclass(frozen=True)
class FallbackPolicy:
    """Contract section 4: ONE retry on 5xx/429/timeout, short backoff, then
    fall back to grep + Read for the remainder of the turn."""

    max_retries: int = 1
    backoff_seconds: float = 2.0
    timeout_seconds: float = 10.0

    def should_retry(self, attempt: int, status: int | None = None) -> bool:
        """Whether to retry after a failed attempt (0-indexed).

        `status` is the HTTP status code, or None for connection errors and
        timeouts. Only availability-shaped failures (5xx, 429, no-connection)
        are retryable.
        """
        if attempt >= self.max_retries:
            return False
        return status is None or status >= 500 or status == 429


DEFAULT_POLICY = FallbackPolicy()


def resolve_endpoint() -> str:
    """Contract section 1: RAG_ENDPOINT_URL env var, then
    ~/.config/rag/endpoint.json {"url": ...}, then the default."""
    url = os.environ.get(ENDPOINT_ENV_VAR, "").strip()
    if url:
        return url.rstrip("/")
    try:
        cfg = json.loads(ENDPOINT_CONFIG_FILE.read_text(encoding="utf-8"))
        url = str(cfg.get("url", "")).strip()
        if url:
            return url.rstrip("/")
    except (OSError, ValueError):
        pass
    return DEFAULT_ENDPOINT


def _request_json(
    url: str,
    timeout: float,
    payload: dict | None = None,
) -> object:
    """GET (payload None) or POST-JSON `url`; return the decoded JSON body."""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_health(endpoint: str | None = None, timeout: float = 5.0) -> dict:
    """GET /api/health. Returns the HealthStatus dict
    ({status, database, redis, embedding_service, llm}).
    Raises RagUnavailable if the endpoint cannot be reached at all."""
    base = (endpoint or resolve_endpoint()).rstrip("/")
    try:
        body = _request_json(base + HEALTH_PATH, timeout)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as exc:
        raise RagUnavailable(f"RAG health check failed for {base}: {exc}") from exc
    if not isinstance(body, dict):
        raise RagUnavailable(f"RAG health check returned non-object JSON from {base}")
    return body


def check_index_health(endpoint: str | None = None, timeout: float = 5.0) -> dict | None:
    """GET /health/index (freshness). Returns the dict, or None when the
    server predates the endpoint (404). Raises RagUnavailable when unreachable."""
    base = (endpoint or resolve_endpoint()).rstrip("/")
    try:
        body = _request_json(base + INDEX_HEALTH_PATH, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405):
            return None  # pre-v1 server: freshness unknown
        raise RagUnavailable(f"RAG index-health failed for {base}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as exc:
        raise RagUnavailable(f"RAG index-health failed for {base}: {exc}") from exc
    return body if isinstance(body, dict) else None


def search(
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
    *,
    endpoint: str | None = None,
    policy: FallbackPolicy = DEFAULT_POLICY,
    rerank: bool | None = None,
    corpus: str | None = None,
    kb: str | list[str] | None = None,
) -> list[dict]:
    """POST the search request per the contract and return the hit list.

    Tries /api/v1/search first; a 404/405 there means an older server and
    falls through to /api/search WITHOUT consuming a retry. Availability
    failures (5xx/429/timeout/connection) retry per `policy`, then raise
    RagUnavailable carrying the fallback advice. Other 4xx raise
    RagRequestError immediately (the request itself is wrong).

    `corpus` (contract section 8) scopes hits to documents whose stored
    filepath starts with that prefix; servers predating the field ignore it
    and return unscoped hits.

    `kb` selects knowledge base(s) on a multi-KB deployment: a KB name,
    a list of names, or "all" (broadcast). When set, /api/v2/search is
    tried FIRST; if the server lacks the v2 gateway (404/405) or has it
    unconfigured (503 single-corpus deploy), the call degrades gracefully
    to v1 WITHOUT consuming a retry — a RuntimeWarning is emitted because
    the kb filter is NOT honored on v1 (hits come from the server's single
    corpus). `kb=None` is byte-identical to the pre-kb behavior. v2 responses
    arrive as a `{results, mode_used, total}` envelope and are unwrapped to
    the bare hit list, so the return shape is identical across v1 and v2.
    """
    base = (endpoint or resolve_endpoint()).rstrip("/")
    payload: dict = {"query": query, "limit": limit, "mode": mode}
    if rerank is not None:
        payload["rerank"] = rerank
    if corpus is not None:
        payload["corpus"] = corpus

    paths = list(SEARCH_PATHS)
    if kb is not None:
        payload["kb"] = kb
        paths.insert(0, V2_SEARCH_PATH)

    def _degrade_to_v1(reason: str) -> None:
        """Drop the v2 path + kb filter; warn that hits will be unscoped."""
        paths.pop(0)
        payload.pop("kb", None)
        warnings.warn(
            f"RAG server at {base} {reason}; falling back to v1 search — "
            f"kb={kb!r} is NOT honored (hits come from the single corpus)",
            RuntimeWarning,
            stacklevel=3,
        )

    attempt = 0
    while True:
        url = base + paths[0]
        on_v2 = paths[0] == V2_SEARCH_PATH
        status: int | None = None
        try:
            body = _request_json(url, policy.timeout_seconds, payload)
            if on_v2 and isinstance(body, dict):
                # v2 gateway wraps hits in an envelope
                # {"results": [...], "mode_used": ..., "total": ...} —
                # unwrap so callers get the same hit list shape as v1.
                results = body.get("results")
                if isinstance(results, list):
                    return results
                raise RagUnavailable(
                    f"RAG v2 search returned an envelope without a 'results' list from {url}"
                )
            if not isinstance(body, list):
                raise RagUnavailable(f"RAG search returned non-list JSON from {url}")
            return body
        except urllib.error.HTTPError as exc:
            if on_v2 and exc.code in (404, 405, 501):
                _degrade_to_v1("has no multi-KB (v2) gateway")
                continue
            if on_v2 and exc.code == 503:
                # v2 mounted but multi-KB not configured (single-corpus deploy).
                _degrade_to_v1("has multi-KB not configured (HTTP 503)")
                continue
            if exc.code in (404, 405) and len(paths) > 1:
                # Version probe: server predates the /api/v1 alias.
                paths.pop(0)
                continue
            if 400 <= exc.code < 500 and exc.code != 429:
                raise RagRequestError(
                    f"RAG rejected the request (HTTP {exc.code} {exc.reason}) at {url}"
                ) from exc
            status = exc.code
            last_error = f"HTTP {exc.code} {exc.reason} from {url}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc} ({url})"

        if not policy.should_retry(attempt, status):
            raise RagUnavailable(
                f"RAG search failed after {attempt + 1} attempt(s): {last_error}"
            )
        attempt += 1
        time.sleep(policy.backoff_seconds)


def format_citation(result: dict) -> str:
    """Contract section 5 citation format: [[RAG:doc_path#chunk_index@score]].

    Multi-KB (v2) hits carrying a `kb` field gain the kb prefix:
    [[RAG:{kb}:{doc_path}#{chunk_index}@{score}]]. v1 hits are unchanged.
    """
    kb = result.get("kb")
    kb_prefix = f"{kb}:" if kb else ""
    path = result.get("document_filepath") or result.get("document_filename") or "?"
    chunk_index = result.get("chunk_index", "?")
    try:
        score = f"{float(result.get('score', 0.0)):.3f}"
    except (TypeError, ValueError):
        score = "?"
    return f"[[RAG:{kb_prefix}{path}#{chunk_index}@{score}]]"
