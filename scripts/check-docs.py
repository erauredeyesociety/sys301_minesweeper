#!/usr/bin/env python3
"""Repo hygiene: the checks that were being re-typed by hand every session.

    ./scripts/check-docs.py             run every check
    ./scripts/check-docs.py --fix-rag   also re-ingest the docs-rag afterwards

Exit 0 if everything passes, 1 if anything fails. Each check prints PASS or FAIL and, when it fails,
the exact offenders -- never a bare "something is wrong".

Why this exists: these five checks were being run as ad-hoc shell one-liners over and over, which is
the thing docs/directives/automation-first.md says to stop doing the second time. Scripting them makes
them repeatable, reviewable, and identical every run.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Not ours: docs-rag/ is a vendored deployment, .git is git's.
SKIP_DIRS = {".git", "docs-rag", "__pycache__", ".venv"}
# Hub-only modules. Importing any of these outside a hub_*.py file breaks the ADR-0004 boundary.
HUB_MODULES = ("hub", "motor", "motor_pair", "color_sensor", "distance_sensor",
               "force_sensor", "motion_sensor", "runloop", "spike")
HUB_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(" + "|".join(HUB_MODULES) + r")\b", re.M)
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def markdown_files():
    for p in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        yield p


def check_links():
    """Every relative markdown link resolves to a file that exists."""
    bad = []
    count = 0
    for md in markdown_files():
        count += 1
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in LINK.finditer(text):
            target = m.group(2).split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                bad.append("{0} -> {1}".format(md.relative_to(ROOT), target))
    return bad, "{0} markdown files scanned".format(count)


def check_indexes():
    """Every docs/ subfolder has an INDEX.md or README.md to navigate by."""
    bad = []
    docs = ROOT / "docs"
    for d in sorted(p for p in docs.rglob("*") if p.is_dir()):
        if SKIP_DIRS & set(d.relative_to(ROOT).parts):
            continue
        if not ((d / "INDEX.md").exists() or (d / "README.md").exists()):
            bad.append(str(d.relative_to(ROOT)))
    return bad, "every docs/ subfolder needs INDEX.md or README.md"


def check_stray_markdown():
    """No *.md in the repo root except the four that belong there."""
    # test_methodology.md sits in root by explicit operator request (2026-08-26) — it answers
    # "why does it look like you are writing tests when I said not to", and they wanted it findable.
    allowed = {"README.md", "CLAUDE.md", "MEMORY.md", "test_methodology.md"}
    bad = [p.name for p in ROOT.glob("*.md")
           if p.name not in allowed and not p.name.startswith("tmp")]
    return bad, "root may hold only README/CLAUDE/MEMORY (and tmp*.md)"


def _is_hub_facing(name):
    """Hub-facing modules are named hub_*.py. Everything else in src/ must stay pure.

    The naming convention IS the rule: you can see which side of the boundary a file is on from its
    name alone, without opening it or consulting a list here. One file per device, each small enough
    to read in one sitting -- which is what replaces the test suite and the debugger we do not carry.
    """
    return name.startswith("hub_")


def check_src_purity():
    """src/ imports nothing hub-only, except the hub_*.py modules that exist to.

    This IS the architecture boundary from ADR-0004. There is no test suite (ADR-0005), so this
    check is the only thing standing between us and a src/ that stops running on the host.
    """
    bad = []
    src = ROOT / "src"
    if not src.is_dir():
        return bad, "no src/ yet"
    for py in sorted(src.glob("*.py")):
        if _is_hub_facing(py.name):
            continue
        for m in HUB_IMPORT.finditer(py.read_text(encoding="utf-8", errors="replace")):
            line = py.read_text().count("\n", 0, m.start()) + 1
            bad.append("{0}:{1} imports hub-only '{2}'".format(
                py.relative_to(ROOT), line, m.group(1)))
    return bad, "only hub_*.py may touch the LEGO API"


def check_src_imports():
    """Every pure src/ module actually imports on this host, with no robot attached."""
    bad = []
    src = ROOT / "src"
    if not src.is_dir():
        return bad, "no src/ yet"
    for py in sorted(src.glob("*.py")):
        r = subprocess.run([sys.executable, "-c", "import " + py.stem],
                           cwd=src, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            last = (r.stderr.strip().splitlines() or ["(no output)"])[-1]
            bad.append("{0}: {1}".format(py.name, last))
    return bad, "all src/ modules import on the host"


MAX_DOC_LINES = 1200


def check_doc_length():
    """No documentation file over MAX_DOC_LINES — past that it must be split.

    Operator standard, 2026-08-26. A document nobody can hold in their head stops being read, and
    a docs-rag chunk from a sprawling file is harder to place in context.
    """
    bad = []
    for md in markdown_files():
        n = md.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        if n > MAX_DOC_LINES:
            bad.append("{0}: {1} lines (limit {2}) — split it".format(
                md.relative_to(ROOT), n, MAX_DOC_LINES))
    return bad, "no doc over {0} lines".format(MAX_DOC_LINES)


CHECKS = [
    ("relative links resolve", check_links),
    ("docs under the line limit", check_doc_length),
    ("docs folders have an INDEX", check_indexes),
    ("no stray markdown in root", check_stray_markdown),
    ("src/ purity boundary (ADR-0004)", check_src_purity),
    ("src/ modules import on host", check_src_imports),
]


def main():
    args = sys.argv[1:]
    fix_rag = args == ["--fix-rag"]
    if args and not fix_rag:
        print("usage: check-docs.py [--fix-rag]", file=sys.stderr)
        return 64

    failed = 0
    for name, fn in CHECKS:
        try:
            bad, note = fn()
        except Exception as exc:                       # a check that cannot run is a FAIL, not a pass
            print("FAIL  {0}\n        check errored: {1!r}".format(name, exc))
            failed += 1
            continue
        if bad:
            failed += 1
            print("FAIL  {0}  ({1})".format(name, note))
            for b in bad:
                print("        " + b)
        else:
            print("PASS  {0}  ({1})".format(name, note))

    if fix_rag:
        rag = ROOT / "docs-rag" / "rag"
        if rag.exists():
            r = subprocess.run([str(rag), "ingest"], cwd=ROOT / "docs-rag",
                               capture_output=True, text=True, timeout=300)
            tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
            print("\ndocs-rag ingest: " + tail.strip())
        else:
            print("\ndocs-rag ingest: SKIPPED — docs-rag/rag not found")

    print("\n{0}".format("all checks passed" if not failed
                         else "{0} check(s) FAILED".format(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
