#!/usr/bin/env python3
"""fetch_paper.py — download an academic PDF, file it, and add a citation stub.

Touches the LEGO hub: NO. Network only, every request bounded by an explicit timeout.
Stdlib only — no pip installs, no frameworks (see docs/directives/code-discipline.md).

Convention comes from docs/plans/2026-08-25-docs-rag-and-literature-workflow.md and is not
reinvented here:
  * PDFs land in docs/research/papers/ named <firstauthor><year>-<short-topic>.pdf
  * a .txt sidecar sits alongside so `grep` works on the corpus
  * PDFs are gitignored; sidecars and citations are TRACKED

Usage:
  scripts/fetch_paper.py <url | doi | arxiv-id> [--topic SLUG] [--name KEY] [--force] [--no-sidecar]

  scripts/fetch_paper.py 2301.12345
  scripts/fetch_paper.py 10.1109/ICRA.2011.5980357 --topic boustrophedon-coverage
  scripts/fetch_paper.py https://example.org/paper.pdf --name choset2001-coverage-survey

Exit codes: 0 ok · 1 error · 3 PDF saved but the .txt sidecar could not be made (degraded).
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TIMEOUT = 30  # seconds, every network call
UA = "sys301-minesweeper/1.0 (ERAU SYS 301 course project; mailto:gnelsonerau@gmail.com)"

REPO = pathlib.Path(__file__).resolve().parent.parent
PAPERS = REPO / "docs" / "research" / "papers"
BIB = PAPERS / "bibliography.md"

ARXIV_RE = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)$", re.I)
DOI_RE = re.compile(r"^(?:doi:|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.I)

STOPWORDS = {
    "a", "an", "and", "for", "of", "on", "the", "to", "with", "in", "using", "via",
    "towards", "toward", "based", "study", "approach", "novel", "new",
}


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def note(msg: str):
    print(msg, file=sys.stderr)


def get(url: str, accept: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # nosec - operator-supplied URL
        return r.read()


def slug(text: str, words: int = 4) -> str:
    text = re.sub(r"[^a-z0-9\s-]", " ", (text or "").lower())
    keep = [w for w in text.split() if w not in STOPWORDS]
    return "-".join(keep[:words]) or "untitled"


def surname(author: str) -> str:
    """'Howie Choset' / 'Choset, Howie' -> 'choset'."""
    author = author.strip()
    if "," in author:
        author = author.split(",")[0]
    else:
        author = author.split()[-1] if author.split() else author
    return re.sub(r"[^a-z]", "", author.lower()) or "anon"


# --------------------------------------------------------------------------- metadata resolution
# Each resolver returns (meta_dict, pdf_url_or_None). meta keys: authors, year, title, venue, source.


def resolve_arxiv(arxiv_id: str):
    url = f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    root = ET.fromstring(get(url))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        die(f"arXiv returned no entry for {arxiv_id}")
    title = " ".join((entry.findtext("a:title", "", ns) or "").split())
    published = entry.findtext("a:published", "", ns) or ""
    authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
    meta = {
        "authors": [a for a in authors if a],
        "year": published[:4],
        "title": title,
        "venue": f"arXiv:{arxiv_id}",
        "source": f"https://arxiv.org/abs/{arxiv_id}",
    }
    return meta, f"https://arxiv.org/pdf/{arxiv_id}"


def resolve_doi(doi: str):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    msg = json.loads(get(url, accept="application/json"))["message"]
    authors = [
        " ".join(x for x in (a.get("given"), a.get("family")) if x)
        for a in msg.get("author", [])
    ]
    dparts = (msg.get("issued", {}).get("date-parts") or [[None]])[0]
    meta = {
        "authors": authors,
        "year": str(dparts[0]) if dparts and dparts[0] else "",
        "title": " ".join(msg.get("title") or ["untitled"]),
        "venue": " ".join(msg.get("container-title") or []) or msg.get("type", ""),
        "source": f"https://doi.org/{doi}",
    }
    # Crossref sometimes advertises a PDF link; often it is paywalled and returns HTML.
    pdf = None
    for link in msg.get("link", []):
        if link.get("content-type") == "application/pdf":
            pdf = link.get("URL")
            break
    return meta, pdf


def resolve_url(url: str):
    """A bare URL carries no metadata. Take what the path gives and let --name/--topic fix it."""
    stem = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).stem
    m = ARXIV_RE.match(stem) or re.search(r"(\d{4}\.\d{4,5})", stem)
    if m:
        return resolve_arxiv(m.group(1))
    return {"authors": [], "year": "", "title": stem.replace("_", " ").replace("-", " "),
            "venue": "", "source": url}, url


def resolve(target: str):
    m = ARXIV_RE.match(target)
    if m:
        return resolve_arxiv(m.group(1))
    if target.startswith(("http://", "https://")):
        host = urllib.parse.urlparse(target).netloc
        if "arxiv.org" in host:
            m = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", target)
            if m:
                return resolve_arxiv(m.group(1))
        if "doi.org" in host:
            return resolve_doi(urllib.parse.urlparse(target).path.lstrip("/"))
        return resolve_url(target)
    m = DOI_RE.match(target)
    if m:
        return resolve_doi(m.group(1))
    die(f"cannot tell what {target!r} is — pass a URL, a DOI (10.xxxx/...), or an arXiv id")


# ------------------------------------------------------------------------------------ filesystem
GITIGNORE = """\
# PDFs of published papers are NOT tracked: copyright, and they bloat the repo.
# The .txt sidecars and bibliography.md ARE tracked so grep and the Intro Report keep working.
# Convention: docs/plans/2026-08-25-docs-rag-and-literature-workflow.md
*.pdf
"""

BIB_HEADER = """\
# Bibliography — papers fetched for the Intro Report

Appended by `scripts/fetch_paper.py`. One section per paper, newest at the bottom.
The PDFs next to this file are gitignored; the `.txt` sidecars and this file are tracked.

**Cite, never recopy** ([../../directives/documentation-discipline.md](../../directives/documentation-discipline.md)):
a finding cites the entry below, it does not reproduce the paper's prose.
"""


def ensure_dirs():
    created = []
    if not PAPERS.exists():
        PAPERS.mkdir(parents=True)
        created.append(str(PAPERS))
    gi = PAPERS / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE)
        created.append(str(gi))
    if not BIB.exists():
        BIB.write_text(BIB_HEADER)
        created.append(str(BIB))
    for c in created:
        note(f"created {c}")


def make_sidecar(pdf: pathlib.Path) -> bool:
    """pdftotext -> .txt. Returns False (loudly) if it cannot be produced."""
    txt = pdf.with_suffix(".txt")
    exe = shutil.which("pdftotext")
    if not exe:
        note("WARN: pdftotext not found, so NO .txt sidecar was made — this paper will not be")
        note("      greppable. Install it:  sudo apt install poppler-utils")
        note(f"      then re-run with --force, or: pdftotext {pdf} {txt}")
        return False
    try:
        subprocess.run([exe, "-q", str(pdf), str(txt)], check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        note(f"WARN: pdftotext failed ({e}) — no sidecar. The PDF is still saved at {pdf}")
        return False
    if not txt.exists() or txt.stat().st_size == 0:
        note(f"WARN: pdftotext produced an empty sidecar — {pdf.name} is probably a scan with no")
        note("      text layer. Left in place so the emptiness is visible rather than silent.")
        return False
    note(f"sidecar: {txt.relative_to(REPO)} ({txt.stat().st_size} bytes)")
    return True


def append_citation(key: str, meta: dict, sidecar_ok: bool):
    existing = BIB.read_text()
    if f"\n## {key}\n" in existing or existing.startswith(f"## {key}\n"):
        note(f"bibliography already has a '{key}' entry — not appending a duplicate")
        return
    authors = "; ".join(meta.get("authors") or []) or "UNKNOWN — fill in"
    entry = (
        f"\n## {key}\n\n"
        f"- **Authors:** {authors}\n"
        f"- **Year:** {meta.get('year') or 'UNKNOWN'}\n"
        f"- **Title:** {meta.get('title') or 'UNKNOWN'}\n"
        f"- **Venue:** {meta.get('venue') or 'UNKNOWN'}\n"
        f"- **Source:** {meta.get('source')}\n"
        f"- **Local:** `docs/research/papers/{key}.pdf` (gitignored)"
        f"{f' · sidecar `{key}.txt`' if sidecar_ok else ' · **NO SIDECAR** — not greppable'}\n"
        f"- **Fetched:** {datetime.date.today().isoformat()}\n"
        f"- **Relevance to the sweep problem:** TODO — one line, why we kept it\n"
    )
    with BIB.open("a") as fh:
        fh.write(entry)
    note(f"citation appended to {BIB.relative_to(REPO)}")


# ------------------------------------------------------------------------------------------ main
def show_meta(meta: dict):
    """Print what we DID resolve. The citation is most of the value even when the PDF is not
    reachable — the operator can go find an open-access copy with it."""
    note("resolved metadata:")
    for k in ("authors", "year", "title", "venue", "source"):
        note(f"  {k}: {meta.get(k)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a paper into docs/research/papers/.")
    ap.add_argument("target", help="URL, DOI (10.xxxx/...), or arXiv id (2301.12345)")
    ap.add_argument("--topic", help="short-topic slug for the filename; default from the title")
    ap.add_argument("--name", help="full key, overriding <firstauthor><year>-<topic>")
    ap.add_argument("--force", action="store_true", help="re-download over an existing PDF")
    ap.add_argument("--no-sidecar", action="store_true", help="skip pdftotext")
    args = ap.parse_args()

    ensure_dirs()

    note(f"resolving {args.target} ...")
    try:
        meta, pdf_url = resolve(args.target)
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError,
            json.JSONDecodeError, KeyError, TimeoutError) as e:
        die(f"metadata lookup failed: {e}")

    if not pdf_url:
        show_meta(meta)
        die("no PDF URL could be resolved (a paywalled DOI is the usual cause). "
            "Find the open-access PDF and pass its URL directly, with --name.")

    if args.name:
        key = args.name
    else:
        first = surname(meta["authors"][0]) if meta.get("authors") else "anon"
        year = meta.get("year") or "nd"
        key = f"{first}{year}-{args.topic or slug(meta.get('title', ''))}"
    key = re.sub(r"[^a-z0-9.-]", "-", key.lower()).strip("-")

    pdf = PAPERS / f"{key}.pdf"
    if pdf.exists() and not args.force:
        note(f"{pdf.relative_to(REPO)} already exists — use --force to re-download")
    else:
        note(f"downloading {pdf_url}")
        try:
            data = get(pdf_url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            # A paywalled DOI typically DOES advertise a PDF link, which then 403s. The citation
            # is still worth having, so print it before failing.
            show_meta(meta)
            die(f"download failed: {e}. If this is a paywall, find the open-access PDF "
                "and re-run with its URL and --name.")
        # Assert a known-correct payload, not merely "HTTP 200". Publishers happily return a
        # paywall/interstitial HTML page with a 200. docs/directives/honest-instrumentation.md
        if not data.startswith(b"%PDF"):
            head = data[:120].decode("utf-8", "replace").replace("\n", " ")
            show_meta(meta)
            die(f"that URL did not return a PDF ({len(data)} bytes, starts {head!r}). "
                "Nothing was saved. Likely a paywall or a landing page.")
        pdf.write_bytes(data)
        note(f"saved {pdf.relative_to(REPO)} ({len(data)} bytes)")

    sidecar_ok = False if args.no_sidecar else make_sidecar(pdf)
    append_citation(key, meta, sidecar_ok)

    print(pdf)
    return 0 if (sidecar_ok or args.no_sidecar) else 3


if __name__ == "__main__":
    sys.exit(main())
