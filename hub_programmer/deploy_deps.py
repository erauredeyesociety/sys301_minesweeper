#!/usr/bin/env python3
"""deploy_deps.py -- deploy a slot program AND every local src/ module it imports.

THE PROBLEM this solves. A slot program like src/main.py `import`s a dozen sibling
modules (config, odometry, sweep, ...). slot_upload.py uploads only the ONE entry
file as program.py; to actually RUN, every module it imports must ALSO be present in
/flash/lib. Until now the operator deployed each dependency by hand
(docs/runbooks/first-main-run.md step 0 flagged this as a KU). This automates it:
resolve the entry file's transitive local imports, deploy each with the PROVEN
upload.py path, then upload the entry as a slot program with slot_upload.py.

    ./hub_programmer/deploy_deps.py src/main.py            # DRY RUN: print the deploy plan, touch nothing
    ./hub_programmer/deploy_deps.py src/main.py --apply     # deploy every dep, then upload+start the entry

TWO HALVES, ONE HOST-ONLY.
  * The RESOLVER (resolve_deps / parse_imports below) is pure host logic -- it parses
    the source with the `ast` module (NOT regex, so an "import" inside a docstring or a
    comment is never mistaken for one) and walks the transitive import graph. It touches
    no hardware and is fully host-testable: the DRY RUN above IS its test -- it prints
    exactly the set it resolved.
  * The DEPLOY half shells out to the two EXISTING, proven tools -- hub_programmer/upload.py
    (module -> /flash/lib, SHA-256 verified on the hub) and hub_programmer/slot_upload.py
    (entry -> program slot, CRC-checked, started). This script adds NO new hub-touching
    code; it orchestrates the ones we already trust.

    [UNVERIFIED] The --apply path has NOT been run against our hardware from this script.
    Its two building blocks behave as documented (upload.py PROVEN 2026-08-27; slot_upload.py
    still UNTESTED per its own header), but the orchestration of the two is unrun. Run it over
    USB to make it MEASURED and file the transcript under docs/findings/runs/.

WHAT COUNTS AS A DEPENDENCY. A `local` module is one that resolves to a file src/<name>.py.
Everything else -- stdlib (time, math, os), hub-only (motor, color_sensor, runloop, hub, ...) --
is NOT deployed: it either ships with MicroPython or is provided by the firmware. The rule is
purely "does src/<name>.py exist"; there is no stdlib allowlist to keep in sync. The dry run
prints the ignored names too, so you can eyeball that nothing load-bearing was dropped.

This file runs on the HOST (CPython 3.10), so it uses host Python freely; it is never uploaded.

Exit codes: 0 ok / dry-run · 1 a deploy step failed · 3 entry file missing · 64 usage
"""

import ast
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, "src")
UPLOAD = os.path.join(HERE, "upload.py")
SLOT_UPLOAD = os.path.join(HERE, "slot_upload.py")


# --- the RESOLVER (pure, host-only, no hardware) ----------------------------

def _imported_names(tree):
    """Top-level module names imported anywhere in an AST -- `import a.b` -> 'a',
    `from a.b import c` -> 'a'. Walks the WHOLE tree, so imports nested in a
    try/except or a function are found too (main.py imports hub_telemetry_log
    inside a try; hub_runtime imports runloop inside a try)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (`from . import x`) have level>0. Flat src/ (ADR-0004)
            # has no packages and thus none of these; skip defensively rather than
            # mis-resolve one to a sibling name.
            if node.level:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def parse_imports(path):
    """Return (set_of_imported_module_names, error_or_None) for one .py file.
    A missing file or a syntax error is reported, never raised -- the caller keeps going."""
    try:
        with open(path, "r") as fh:
            source = fh.read()
    except OSError as exc:
        return None, "cannot read %s (%s)" % (path, exc)
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return None, "syntax error in %s (%s)" % (path, exc)
    return _imported_names(tree), None


def resolve_deps(entry_path, src_dir=SRC_DIR):
    """Transitively resolve the LOCAL src/ modules an entry file needs.

    Returns (deps, external, problems):
      deps      -- sorted list of local module names to deploy, EXCLUDING the entry itself
                   (the entry goes to a slot as program.py, not to /flash/lib).
      external  -- sorted list of imported names that are NOT local (stdlib / hub-only);
                   reported for transparency, never deployed.
      problems  -- list of (module, reason) for anything unreadable or unparseable; the
                   resolver skips it and carries on rather than crashing.

    Cycle-safe: each module's file is parsed at most once (`parsed` set), so a mutual
    import (A<->B) terminates instead of looping."""
    entry_mod = os.path.splitext(os.path.basename(entry_path))[0]

    def is_local(name):
        return os.path.isfile(os.path.join(src_dir, name + ".py"))

    deps = set()
    external = set()
    problems = []
    parsed = set()
    # Worklist of (module_name, file_path) to parse. Seed with the entry file itself;
    # its own module name is booked as parsed so a dep that imports it back is a no-op.
    worklist = [(entry_mod, entry_path)]
    parsed.add(entry_mod)
    while worklist:
        mod, path = worklist.pop()
        names, err = parse_imports(path)
        if err:
            problems.append((mod, err))
            continue
        for name in names:
            if name == entry_mod:
                continue
            if is_local(name):
                if name not in deps:
                    deps.add(name)
                if name not in parsed:
                    parsed.add(name)
                    worklist.append((name, os.path.join(src_dir, name + ".py")))
            else:
                external.add(name)
    return sorted(deps), sorted(external), problems


# --- the ORCHESTRATOR (dry-run by default; --apply shells out to proven tools) ---

def _run(cmd):
    """Run one child tool, streaming its output; return its exit code."""
    print("\n$ " + " ".join(cmd))
    return subprocess.call(cmd)


def deploy(entry_path, deps, apply_it):
    """Deploy every dependency to /flash/lib, then upload+start the entry as a slot program.
    DRY RUN by default: prints the exact commands and touches nothing without --apply."""
    dep_cmds = [[sys.executable, UPLOAD, os.path.join(SRC_DIR, m + ".py"), "--apply"]
                for m in deps]
    entry_cmd = [sys.executable, SLOT_UPLOAD, entry_path, "--apply"]

    if not apply_it:
        print("\nDRY RUN -- nothing was deployed. With --apply this would run, in order:")
        for cmd in dep_cmds:
            print("  " + " ".join(cmd))
        print("  " + " ".join(entry_cmd) + "        # the entry, as program.py in a slot")
        print("\nRe-run with --apply to deploy. [UNVERIFIED] the --apply orchestration is unrun on hardware.")
        return 0

    # --apply: the hub-touching half. Each step is a proven tool; a non-zero exit STOPS
    # the sequence so we never start a program whose dependencies are not all present.
    print("\n[UNVERIFIED] deploying for real via upload.py / slot_upload.py -- unrun-from-here path.")
    for m, cmd in zip(deps, dep_cmds):
        rc = _run(cmd)
        if rc != 0:
            print("\nFAILED: upload.py exited %d on '%s'. Stopping -- the program is NOT started." % (rc, m))
            return 1
    rc = _run(entry_cmd)
    if rc != 0:
        print("\nFAILED: slot_upload.py exited %d on the entry. Dependencies are in /flash/lib, "
              "but the program did not upload/start." % rc)
        return 1
    print("\nDone: %d dependency module(s) in /flash/lib, entry uploaded and started." % len(deps))
    return 0


def main(argv):
    apply_it = "--apply" in argv
    files = [a for a in argv[1:] if not a.startswith("--")]
    if not files:
        print(__doc__.split("TWO HALVES")[0].strip())
        return 64
    entry_path = files[0]
    if not os.path.isfile(entry_path):
        print("no such entry file: %s" % entry_path)
        return 3

    deps, external, problems = resolve_deps(entry_path)

    print("entry     : %s" % entry_path)
    print("src dir   : %s" % SRC_DIR)
    print("resolved %d local dependency module(s) -> /flash/lib:" % len(deps))
    for m in deps:
        print("    %s  (%s)" % (m, os.path.join(SRC_DIR, m + ".py")))
    if external:
        print("ignored (stdlib / hub-only, not deployed): %s" % ", ".join(external))
    for mod, reason in problems:
        print("WARNING: could not analyse '%s': %s" % (mod, reason))

    return deploy(entry_path, deps, apply_it)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
