#!/usr/bin/env python3
"""ragq — query a rag-bootstrap stack from the command line.

Thin CLI over :mod:`fallback_policy`, implementing the consumer rules in
``docs/integration/CONSUMING_AGENTS_CONTRACT.md``. Stdlib-only: copy or
symlink the two files in ``client/`` into any consuming project and it works
without installs.

Usage::

    ragq.py "how does the watcher archive files?"        # human-readable hits
    ragq.py -n 3 -m semantic --json "chunking strategy"  # raw JSON hit list
    ragq.py --corpus /repo/docs "deploy steps"           # filepath-prefix scope
    ragq.py --kb hpc-automation "qsub wrapper"           # one KB (multi-KB v2)
    ragq.py --kb hpc-automation,expert-curation "spec"   # subset federation
    ragq.py --kb all "training loss curve"               # broadcast to all KBs
    ragq.py --health                                     # liveness probe
    ragq.py --index-health                               # freshness probe
    RAG_ENDPOINT_URL=http://127.0.0.1:10020 ragq.py "q"  # another stack's band

--kb targets the /api/v2 multi-KB gateway. Against a server without it (or
with multi-KB unconfigured), the query degrades gracefully to v1 with a
warning on stderr — the kb filter is NOT honored there (single corpus).

Exit codes (stable interface for orchestrators):

    0  success (hits returned / health "healthy")
    1  request rejected (4xx) or health "degraded"
    2  usage error (argparse)
    3  RAG unavailable after retry — fall back to grep + Read for this turn
"""

from __future__ import annotations

import argparse
import json
import sys

if __package__:
    from .fallback_policy import (
        RagRequestError,
        RagUnavailable,
        check_health,
        check_index_health,
        format_citation,
        resolve_endpoint,
        search,
    )
else:
    from fallback_policy import (
        RagRequestError,
        RagUnavailable,
        check_health,
        check_index_health,
        format_citation,
        resolve_endpoint,
        search,
    )

EXIT_OK = 0
EXIT_REQUEST_ERROR = 1
EXIT_UNAVAILABLE = 3


def _parse_kb(value: str) -> str | list[str]:
    """Parse --kb: a KB name, a comma-separated list, or "all".

    Returns a single name as a string, several names as a list, and
    collapses any list containing "all" to the "all" broadcast.
    """
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise argparse.ArgumentTypeError(
            "--kb requires a KB name, a comma-separated list, or 'all'"
        )
    if "all" in names:
        return "all"
    if len(names) == 1:
        return names[0]
    return names


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ragq",
        description="Query the rag-bootstrap RAG stack (see docs/integration/CONSUMING_AGENTS_CONTRACT.md).",
    )
    parser.add_argument("query", nargs="?", help="search query text")
    parser.add_argument(
        "-n", "--limit", type=int, default=5, metavar="N",
        help="max hits to return, 1-100 (default: 5)",
    )
    parser.add_argument(
        "-m", "--mode", choices=("semantic", "keyword", "hybrid"), default="hybrid",
        help="search mode (default: hybrid)",
    )
    rerank = parser.add_mutually_exclusive_group()
    rerank.add_argument(
        "--rerank", dest="rerank", action="store_true", default=None,
        help="force cross-encoder reranking on",
    )
    rerank.add_argument(
        "--no-rerank", dest="rerank", action="store_false",
        help="force cross-encoder reranking off",
    )
    parser.add_argument(
        "--corpus", metavar="PREFIX",
        help="scope hits to documents whose filepath starts with PREFIX "
        "(older servers ignore this and return unscoped hits)",
    )
    parser.add_argument(
        "--kb", type=_parse_kb, metavar="NAME[,NAME...]|all", default=None,
        help="knowledge base(s) to search on a multi-KB deployment "
        "(single name, comma-separated list, or 'all' to broadcast); "
        "servers without the v2 gateway degrade to unscoped v1 search "
        "with a warning; composes with --corpus",
    )
    parser.add_argument(
        "--endpoint", metavar="URL",
        help="override endpoint (default: RAG_ENDPOINT_URL -> "
        "~/.config/rag/endpoint.json -> http://127.0.0.1:10000)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the raw JSON response instead of formatted hits",
    )
    parser.add_argument(
        "--content-chars", type=int, default=300, metavar="N",
        help="chars of chunk content per formatted hit, 0 = citations only (default: 300)",
    )
    parser.add_argument(
        "--health", action="store_true",
        help="GET /api/health and exit (0 healthy, 1 degraded, 3 unreachable)",
    )
    parser.add_argument(
        "--index-health", action="store_true",
        help="GET /health/index (freshness) and exit",
    )
    return parser


def _print_hits(hits: list[dict], content_chars: int) -> None:
    for hit in hits:
        print(format_citation(hit))
        if content_chars > 0:
            content = str(hit.get("content", "")).strip()
            snippet = content[:content_chars]
            if len(content) > content_chars:
                snippet += " ..."
            print("  " + snippet.replace("\n", "\n  "))


def _run_health(endpoint: str | None, as_json: bool) -> int:
    body = check_health(endpoint)
    print(json.dumps(body, indent=None if as_json else 2))
    return EXIT_OK if body.get("status") == "healthy" else EXIT_REQUEST_ERROR


def _run_index_health(endpoint: str | None, as_json: bool) -> int:
    body = check_index_health(endpoint)
    if body is None:
        print(
            "index health: unknown (server predates /health/index; "
            "treat freshness as unverified)",
            file=sys.stderr,
        )
        return EXIT_OK
    print(json.dumps(body, indent=None if as_json else 2))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.health:
            return _run_health(args.endpoint, args.json)
        if args.index_health:
            return _run_index_health(args.endpoint, args.json)
        if not args.query:
            parser.error("a query is required unless --health/--index-health is given")
        hits = search(
            args.query,
            limit=args.limit,
            mode=args.mode,
            endpoint=args.endpoint,
            rerank=args.rerank,
            corpus=args.corpus,
            kb=args.kb,
        )
    except RagRequestError as exc:
        print(f"ragq: request error: {exc}", file=sys.stderr)
        return EXIT_REQUEST_ERROR
    except RagUnavailable as exc:
        endpoint = args.endpoint or resolve_endpoint()
        print(f"ragq: {exc} (endpoint: {endpoint})", file=sys.stderr)
        print(f"ragq: {exc.advice}", file=sys.stderr)
        return EXIT_UNAVAILABLE

    if args.json:
        print(json.dumps(hits))
    else:
        _print_hits(hits, args.content_chars)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
