#!/usr/bin/env python3
"""compare-runs.py — one table: did the last edit make the robot better or worse?

    ./scripts/compare-runs.py                 # every distinct run in tmp/telemetry/
    ./scripts/compare-runs.py followtape      # only that program's runs

`analyse-run.py` answers "what happened on THIS run". This answers the question you actually ask
while tuning a program: what changed since last time. One row per run, newest last, so a regression
is a column that moves the wrong way.

IT DEDUPLICATES BY THE HUB-SIDE STAMP, and that is the point. `download.py --all` re-fetches every
log the hub still holds, so one run lands on the host under a new filename every time you download.
Counted on 2026-09-08: 44 CSVs on disk were 15 distinct runs — 29 of them were re-downloads of a run
already there. A naive "last five files" comparison would have compared a run against copies of
itself and concluded that nothing had changed.

Pure host-side. Opens CSVs. Touches no hardware.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runlog                                                             # noqa: E402


def distinct_runs(prefix=None):
    """One Run per hub-side stamp, keeping the EARLIEST download (the others are byte copies)."""
    seen, out = {}, []
    for path in sorted(glob.glob(os.path.join(runlog.TMP_DIR, "*.csv"))):
        run = runlog.load(path)
        if prefix and run.prefix != prefix:
            continue
        key = (run.prefix, run.hub_stamp or os.path.basename(path))
        if key in seen:
            seen[key][1] += 1
            continue
        seen[key] = [run, 1]
        out.append(key)
    # Group each program's runs together, in first-seen order, so a regression is adjacent rows.
    out.sort(key=lambda k: (k[0], seen[k][0].path))
    return [(seen[k][0], seen[k][1]) for k in out]


def metrics(run):
    """The handful of numbers worth watching between runs. None where the log cannot support one."""
    m = {"rows": len(run.rows), "reason": (run.end or {}).get("reason", "NO #end"),
         "hz": None, "mm": None, "div": None, "wander": None,
         "peak_refl": None, "peak_blue": None}
    if not run.rows:
        return m
    t = [runlog.num(r, "t_ms") for r in run.rows]
    moving = [i for i, r in enumerate(run.rows)
              if not (r.get("phase") or "").startswith("stop")]
    mt = [t[i] for i in moving if t[i] is not None]
    if len(mt) > 1 and mt[-1] > mt[0]:
        m["hz"] = (len(mt) - 1) / ((mt[-1] - mt[0]) / 1000.0)
    a0, a1 = runlog.num(run.rows[0], "relA_deg"), runlog.num(run.rows[-1], "relA_deg")
    b0, b1 = runlog.num(run.rows[0], "relB_deg"), runlog.num(run.rows[-1], "relB_deg")
    if None not in (a0, a1, b0, b1):
        fl = runlog.LEFT_FWD_SIGN * (a1 - a0)
        fr = runlog.RIGHT_FWD_SIGN * (b1 - b0)
        m["mm"] = runlog.fwd_mm((fl + fr) / 2.0)
        m["div"] = 100.0 * abs(fl - fr) / max(1.0, (abs(fl) + abs(fr)) / 2.0)
    yaw, _ = runlog.series(run.rows, "yaw_ddeg")
    if yaw and len(yaw) > 1:
        hd = runlog.unwrap([v / 10.0 for v in yaw])
        m["wander"] = max(hd) - min(hd)
    for port in ("C", "D"):
        for key, kind in (("peak_refl", "reflection"), ("peak_blue", "blue_frac")):
            vals = [v for _, v in runlog.signal(run.rows, port, kind)]
            if vals:
                m[key] = max(vals) if m[key] is None else max(m[key], max(vals))
    return m


def cell(value, fmt, width, threshold=None):
    """A number, or an em dash when the log cannot support one. '+' marks a peak that cleared its
    rule; a blank there means it did not, which is the fact worth seeing at a glance."""
    if value is None:
        return "%*s " % (width, "—")
    mark = "" if threshold is None else ("+" if value >= threshold else " ")
    return (("%" + fmt) % value).rjust(width) + (mark or " ")


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if len(argv) - 1 != len(args):
        print("usage: compare-runs.py [PREFIX]", file=sys.stderr)
        return 64
    prefix = args[0] if args else None
    runs = [(r, c) for r, c in distinct_runs(prefix)]
    empty = [(r, c) for r, c in runs if not r.rows]
    runs = [(r, c) for r, c in runs if r.rows]
    if not runs:
        where = "program '%s'" % prefix if prefix else "any program"
        print("No logs for %s in %s." % (where, runlog.TMP_DIR), file=sys.stderr)
        return 2

    # Thresholds are printed in the header so a peak column can be read without a second lookup.
    refl_thr = [t for _, k, _, t, _ in runlog.RULES if k == "reflection"][0]
    blue_thr = [t for _, k, _, t, _ in runlog.RULES if k == "blue_frac"][0]
    print("Distinct runs in %s%s — %d run(s)."
          % (os.path.relpath(runlog.TMP_DIR, runlog.ROOT),
             " for '%s'" % prefix if prefix else "", len(runs)))
    print("Peaks are the best either sensor reached. Mine rule >= %.0f, tape rule >= %.2f."
          % (refl_thr, blue_thr))
    print()
    head = ("%-13s %-11s %5s %6s %8s %6s %8s %8s %8s %s"
            % ("program", "hub stamp", "rows", "Hz", "fwd mm", "L-R%", "wander", "pk refl",
               "pk blue", "verdict"))
    print(head)
    print("-" * len(head))
    for run, copies in runs:
        m = metrics(run)
        note = run.end_raw or ""
        if copies > 1:
            note = "%s   [%d duplicate download(s) ignored]" % (note or "no #end", copies - 1)
        print("%-13s %-11s %5d %s %s %s %s %s %s %s"
              % (run.prefix[:13], run.hub_stamp or "?", m["rows"],
                 cell(m["hz"], ".1f", 5), cell(m["mm"], "+.0f", 7), cell(m["div"], ".1f", 5),
                 cell(m["wander"], ".1f", 7), cell(m["peak_refl"], ".0f", 7, refl_thr),
                 cell(m["peak_blue"], ".3f", 7, blue_thr), m["reason"]))
        if note:
            print("%s%s" % (" " * 14, note))
    print()
    if empty:
        print("Skipped %d file(s) with no parseable data rows (BLE captures and the like):"
              % len(empty))
        for r, _ in empty:
            print("  %s" % os.path.basename(r.path))
        print()
    print("A dash is data the log does not carry, never a zero. '+' means that peak cleared its")
    print("rule's threshold. Read one run in full with:")
    print("  ./scripts/analyse-run.py tmp/telemetry/<file>.csv")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)
