#!/usr/bin/env python3
"""Ask the docs-rag about our own SOURCE CODE and get file:line citations back.

    ./scripts/rag-code.py "how is the lane pitch chosen"        # our code
    ./scripts/rag-code.py docs "how is the lane pitch chosen"   # our prose docs
    ./scripts/rag-code.py all  "how is the lane pitch chosen"   # both corpora
    ./scripts/rag-code.py --sync                                # re-index the code now

The code is a SECOND knowledge base inside the same docs-rag stack (database
`ragdb_code`, alongside the docs corpus in `ragdb`) -- see
docs/runbooks/docs-rag-code-kb.md. Nothing here touches the hub, and every call
is bounded by a timeout.

WHY A SCRIPT: the raw call is a POST to /api/v2/search with a `kb` field and a
JSON body, and the useful part of the reply (path, line span, symbol) is buried
in it. That pipeline was being retyped -- which is what automation-first says to
stop doing the second time.

WHY NO `--ask`: /api/ask takes the same `kb` field and answers in prose, but it
costs ~70 s and the prose is the weaker half. Retrieval is the trustworthy half:
these citations are line-exact, so open the file. For prose, curl /api/ask with
{"question": "...", "kb": "code"}.

Exit 0 on hits, 1 on no hits, 2 if the service could not answer.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ── Edit these ────────────────────────────────────────────────────────────────
RAG_URL = "http://127.0.0.1:10060"
KB = "code"          # default scope; "docs" and "all" are also accepted
LIMIT = 6            # hits printed -- upstream measures the right file inside the top 3
TIMEOUT = 40         # seconds; a search is fast, only /api/ask is slow
SNIPPET = 96         # characters of each chunk shown under its citation
# ──────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SCOPES = {"code", "docs", "all"}


def post(path, body, timeout=TIMEOUT):
    req = urllib.request.Request(
        RAG_URL + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def search(scope, question):
    try:
        raw = post("/api/v2/search",
                   {"query": question, "kb": scope, "limit": LIMIT})
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if "multi-KB not configured" in detail:
            print("The code KB is not active on this stack.\n"
                  "  Fix:  cd docs-rag && docker compose up -d api\n"
                  "  Then: docs/runbooks/docs-rag-code-kb.md", file=sys.stderr)
        else:
            print("docs-rag answered HTTP {0}: {1}".format(e.code, detail[:300]),
                  file=sys.stderr)
        return None
    except (urllib.error.URLError, OSError) as e:
        print("docs-rag is not answering at {0} ({1}).\n"
              "  Fix:  ./scripts/stack.sh up".format(RAG_URL, e), file=sys.stderr)
        return None
    return raw.get("results", raw) if isinstance(raw, dict) else raw


def show(hits):
    for h in hits:
        path = h.get("document_filepath", h.get("document_filename", "?"))
        try:
            path = str(Path(path).relative_to(ROOT))
        except ValueError:
            pass
        span = "{0}-{1}".format(h.get("start_line"), h.get("end_line"))
        symbol = h.get("symbol_path") or ""
        cos = h.get("cosine")
        print("{0}:{1}  [{2}]{3}  cos={4}".format(
            path, span, h.get("kb", "?"),
            "  " + symbol if symbol else "",
            "{0:.3f}".format(cos) if cos is not None else "n/a"))
        body = " ".join((h.get("content") or "").split())
        if body:
            print("    " + body[:SNIPPET] + ("..." if len(body) > SNIPPET else ""))


def sync():
    """Force an immediate re-index of the code KB.

    Usually unnecessary: the api reconciles every configured KB on its own timer
    (RECONCILE_INTERVAL_SECONDS, default 300 s), so an edited file is picked up
    within about five minutes with no command run. Use this when you cannot wait.
    """
    rag = ROOT / "docs-rag" / "rag"
    if not rag.exists():
        print("docs-rag/rag not found -- is the stack deployed?", file=sys.stderr)
        return 2
    r = subprocess.run([str(rag), "ingest-kb", "--kb", KB],
                       cwd=rag.parent, capture_output=True, text=True, timeout=900)
    last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    print(last)
    if r.returncode != 0:
        print((r.stderr.strip().splitlines() or ["(no stderr)"])[-1], file=sys.stderr)
    return r.returncode


def main():
    args = sys.argv[1:]
    if args == ["--sync"]:
        return sync()
    scope = KB
    if args and args[0] in SCOPES:
        scope, args = args[0], args[1:]
    question = " ".join(args).strip()
    if not question:
        print(__doc__.split("\n\n")[1].strip(), file=sys.stderr)
        return 64

    hits = search(scope, question)
    if hits is None:
        return 2
    if not hits:
        print("no hits above the relevance floor (RAG_MIN_SIMILARITY=0.6) in kb={0}"
              .format(scope))
        return 1
    show(hits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
