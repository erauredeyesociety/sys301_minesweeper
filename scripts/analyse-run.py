#!/usr/bin/env python3
"""analyse-run.py — one command, one report: what did the robot actually do on that run?

    ./scripts/analyse-run.py                  # the newest log in tmp/telemetry/
    ./scripts/analyse-run.py <FILE>           # a specific one
    ./scripts/analyse-run.py --trace          # ... and dump every row as a table

Written because each run was being picked apart with fresh `awk` and inline python, which is slow,
different every time, and loses the insight the moment the terminal scrolls. Modelled on the
sectioned diagnostic report in the operator's drone project (`~/tmp/tmp_drone/scripts/log_analyze.py`):
numbered sections, each answering ONE question, each ending in a plain-words verdict, and each
printing "NOT ASSESSED and why" rather than vanishing when its data is absent.

WHAT IT IS NOT. `scripts/decode_telemetry.py` stays — it owns the odometry question (gyro-vs-encoder
agreement, the square-drive per-segment breakdown, and MEASURING track width from a spin) by running
the real `src/` kinematics. This tool owns the mission question: did the run trip its rule, by how
much, when, and was the data healthy enough to believe. Run both on a square-drive log; run this one
on a mission log.

Honesty rules this obeys, so a number here can be quoted in the Intro Report:
  * an unreadable cell is reported as unreadable, never as 0;
  * a threshold that was never crossed says so AND says by how much it fell short;
  * every derived figure names the constant it used;
  * anything the schema does not carry is printed as "not in this log", not omitted.

Pure host-side. Opens one CSV. Touches no hardware.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runlog                                                             # noqa: E402

W = 92
MAX_EVENTS = 40         # beyond this the list stops being a timeline and becomes noise


def rule(title=None):
    print("-" * W)
    if title:
        print("  " + title)
        print("-" * W)


def is_moving(row):
    ph = row.get("phase")
    return not (ph or "").startswith("stop")


def tail_stop_block(rows):
    """Index of the first row of the CONTIGUOUS stopped block that runs to the end of the log,
    or None if the log does not end stopped. Only that block is a coast measurement."""
    if not rows or is_moving(rows[-1]):
        return None
    i = len(rows) - 1
    while i > 0 and not is_moving(rows[i - 1]):
        i -= 1
    return i


def phase_runs(rows):
    """[(phase, first_index, last_index)] — consecutive rows sharing a phase label."""
    out = []
    for i, r in enumerate(rows):
        ph = r.get("phase", "")
        if not out or out[-1][0] != ph:
            out.append([ph, i, i])
        else:
            out[-1][2] = i
    return [tuple(x) for x in out]


def wheel_travel(rows, lo, hi):
    """Sign-corrected forward degrees for each wheel between two row indexes, or (None, None)."""
    a0, a1 = runlog.num(rows[lo], "relA_deg"), runlog.num(rows[hi], "relA_deg")
    b0, b1 = runlog.num(rows[lo], "relB_deg"), runlog.num(rows[hi], "relB_deg")
    if None in (a0, a1, b0, b1):
        return None, None
    return runlog.LEFT_FWD_SIGN * (a1 - a0), runlog.RIGHT_FWD_SIGN * (b1 - b0)


# ── 1. identity ────────────────────────────────────────────────────────────────────────────────

def section_identity(run):
    print("=" * W)
    print("  RUN ANALYSIS  —  %s" % os.path.basename(run.path))
    print("=" * W)
    print("  chosen because : %s" % getattr(run, "why", "named on the command line"))
    print("  program        : %s" % run.prefix)
    print("  schema         : %s — %s" % (run.schema, run.schema_note))
    print("  data rows      : %d%s" % (len(run.rows),
                                       "   (%d malformed line(s) skipped)" % run.malformed
                                       if run.malformed else ""))
    for m in run.meta:
        print("  file note      : %s" % m)
    print("  hub-side stamp : %s   <- THIS is the run's identity" % (run.hub_stamp or "unparsed"))
    dupes = runlog.siblings(run)
    if dupes:
        print("  ⚠ SAME RUN, %d other copy(ies) on disk — the leading timestamp is the DOWNLOAD" % len(dupes))
        print("    time, not the run time. `download.py --all` re-fetches everything the hub still")
        print("    holds, so an old run reappears with a fresh name and can look like a new one:")
        for p in dupes:
            print("      %s" % os.path.basename(p))
    if not run.rows:
        print("\n  NO DATA ROWS. Nothing can be assessed. The program wrote a header and stopped,")
        print("  or the download truncated the file.")
        return False
    return True


# ── 2. verdict ─────────────────────────────────────────────────────────────────────────────────

def section_verdict(run):
    rule("1. VERDICT  (what the program itself said when it closed the log)")
    if not run.end:
        print("  NO '#end' LINE. The program did not close its log.")
        print("  That means one of: it crashed mid-run, the battery cut, the hub was stopped by")
        print("  hand, or the download truncated the file. The rows below are still real, but the")
        print("  run's own summary is MISSING and nothing here can substitute for it.")
        return
    reason = run.end.get("reason", "(none)")
    print("  %s" % run.end_raw)
    print()
    print("  reason '%s': %s" % (reason, runlog.REASONS.get(
        reason, "NOT A REASON THIS TOOL KNOWS — read the program that wrote it before assuming.")))
    for key, label in (("colour", "mine colour named"), ("refl", "reflection at the stop"),
                       ("corrections", "steering corrections applied")):
        if key in run.end:
            print("  %-28s: %s" % (label, run.end[key]))
    claimed = run.end.get("rows")
    if claimed is not None:
        got = len(run.rows)
        ok = int(claimed) == got
        print("  rows claimed vs found       : %s vs %d   %s"
              % (claimed, got, "consistent" if ok else "MISMATCH — the file is incomplete"))
    if "deg" in run.end and "mm" in run.end:
        deg = float(run.end["deg"])
        print("  distance the program reported: %s deg -> %s mm  (recomputed here: %.0f mm at the "
              "MEASURED %.1f mm wheel)" % (run.end["deg"], run.end["mm"],
                                           runlog.fwd_mm(deg), runlog.WHEEL_DIAMETER_MM))


# ── 3. motion ──────────────────────────────────────────────────────────────────────────────────

def section_motion(run):
    rule("2. MOTION  (distance, tick rate, straightness, heading, coast)")
    rows = run.rows
    t = [runlog.num(r, "t_ms") for r in rows]
    if any(v is None for v in t):
        print("  t_ms is unreadable on some rows — timing NOT ASSESSED.")
        return
    moving = [i for i, r in enumerate(rows) if is_moving(r)]
    tail = tail_stop_block(rows)

    # --- timing. The trailing 'stopped' rows sleep on a different interval, so mixing them into
    # the tick rate understates the rate the robot actually achieved while driving.
    dur = (t[-1] - t[0]) / 1000.0
    print("  duration           : %.2f s over %d rows" % (dur, len(rows)))
    if len(moving) > 1:
        mt = [t[i] for i in moving]
        gaps = sorted(mt[i + 1] - mt[i] for i in range(len(mt) - 1))
        span = (mt[-1] - mt[0]) / 1000.0
        hz = (len(mt) - 1) / span if span > 0 else 0.0
        med = runlog.pct(gaps, 50)
        print("  tick rate (moving) : %.1f Hz   interval median %.0f ms, min %.0f, max %.0f"
              % (hz, med, gaps[0], gaps[-1]))
        if gaps[-1] > 2.5 * med:
            print("    ⚠ worst interval is %.1fx the median — the loop stalled at least once."
                  % (gaps[-1] / med))
        else:
            print("    loop held its cadence (worst interval %.1fx median)." % (gaps[-1] / med))
    else:
        print("  tick rate (moving) : NOT ASSESSED — fewer than two moving rows.")
    if tail is not None:
        print("  rows after the stop: %d (phase '%s') — logged deliberately to catch the coast"
              % (len(rows) - tail, rows[tail].get("phase", "?")))

    # A run that deliberately turns has a large left-right encoder difference BY DESIGN, so the
    # divergence figure is not a straightness metric there. Decide from the log, not from the name.
    turned = any((r.get("phase") or "").startswith("turn") for r in rows)
    yaw_all, yaw_missing = runlog.series(rows, "yaw_ddeg")
    heading = runlog.unwrap([v / 10.0 for v in yaw_all]) if yaw_all and len(yaw_all) > 1 else None
    if heading and abs(heading[-1] - heading[0]) > 20.0:
        turned = True

    # --- distance and straightness
    print()
    fl, fr = wheel_travel(rows, 0, len(rows) - 1)
    if fl is None:
        print("  DISTANCE NOT ASSESSED — relA_deg/relB_deg missing or unreadable at an endpoint.")
    else:
        dl, dr = runlog.fwd_mm(fl), runlog.fwd_mm(fr)
        mean = (dl + dr) / 2.0
        div = abs(fl - fr)
        div_pct = 100.0 * div / max(1.0, (abs(fl) + abs(fr)) / 2.0)
        print("  left wheel  (A)    : %+8.1f mm  (%+.0f deg, forward-signed)" % (dl, fl))
        print("  right wheel (B)    : %+8.1f mm  (%+.0f deg, forward-signed)" % (dr, fr))
        print("  net forward        : %+8.1f mm      [deg/360 x %.2f mm, the MEASURED 63.5 mm wheel]"
              % (mean, runlog.WHEEL_CIRCUM_MM))
        print("  L-R divergence     : %8.1f deg = %.1f%% of mean travel%s"
              % (div, div_pct, "" if turned else "  <- the straightness metric"))
        if mean < -5.0 and not turned:
            print("    ⚠ NET TRAVEL IS NEGATIVE: by the measured mirror convention (forward = A:-v,")
            print("      B:+v) this robot drove BACKWARD. Check the program's DIRECTION constant.")
        if turned:
            print("    THIS RUN TURNED, so the wheels differ by design and the figure above is NOT")
            print("    a straightness metric. Read straightness per segment in the phase table.")
        elif div_pct > 10.0:
            print("    ⚠ the wheels disagree by >10% — one is slipping, dragging, or under load.")
        elif div_pct <= 3.0 and abs(mean) > 20:
            print("    tracked straight (divergence under 3%).")

    # --- speed, from encoders (whose unit is measured) not from velL/velR (whose unit is not)
    steps = []
    for k in range(len(moving) - 1):
        i, j = moving[k], moving[k + 1]
        a, b = wheel_travel(rows, i, j)
        dt = (t[j] - t[i]) / 1000.0
        if a is not None and dt > 0:
            steps.append(abs(runlog.fwd_mm((a + b) / 2.0)) / dt)
    if steps:
        s = runlog.stats(steps)
        print("  ground speed       : mean %.0f mm/s, median %.0f, max %.0f   (from encoder deltas)"
              % (s["mean"], s["p50"], s["max"]))
    else:
        print("  ground speed       : NOT ASSESSED — needs two consecutive moving rows with encoders.")

    # --- heading
    if yaw_all is None:
        print("  heading            : not in this log's schema.")
    elif heading is None:
        print("  heading            : NOT ASSESSED — %d readable yaw samples." % len(yaw_all))
    else:
        total = heading[-1] - heading[0]
        wander = max(heading) - min(heading)
        print("  heading            : start %.1f deg, end %.1f deg, net %+.1f deg"
              % (heading[0], heading[-1], total))
        print("  yaw wander         : %.1f deg (max-min of the unwrapped heading)" % wander)
        if abs(total) >= 10.0:
            print("    the robot turned a net %+.0f deg — read the per-phase table for where."
                  % total)
        elif wander < 10.0:
            print("    held its heading — this was a straight run, and it stayed straight.")
        else:
            print("    ⚠ ended on its start heading but wandered %.1f deg getting there." % wander)
        if yaw_missing:
            print("    (%d yaw reads returned nothing and were dropped, not counted as zero)"
                  % yaw_missing)

    # --- coast. Only the FINAL stop block measures a coast: an interleaved stop phase in a
    # multi-segment program is a pause mid-run, and integrating from it to the end of the file
    # would report the rest of the run as "coast". That bug was live until the square-drive log
    # reported 947 mm of coast.
    print()
    if tail is None:
        print("  coast after stop   : NOT MEASURED — this log does not end in a stopped phase, so")
        print("    the program never sampled after cutting the motors and the coast is unknown.")
    else:
        cl, cr = wheel_travel(rows, max(tail - 1, 0), len(rows) - 1)
        if cl is None:
            print("  coast after stop   : NOT ASSESSED — encoders unreadable across the stop.")
        else:
            cm = runlog.fwd_mm((cl + cr) / 2.0)
            print("  coast after stop   : %+.1f mm (%+.0f deg) over %.2f s, motors already cut"
                  % (cm, (cl + cr) / 2.0, (t[-1] - t[tail]) / 1000.0))
            print("    This is the stopping margin the boundary needs. Small is good.")


# ── 4. phase timeline ──────────────────────────────────────────────────────────────────────────

def section_phases(run):
    """Always prints, even when it has nothing — a section that silently disappears reads as
    'checked and fine'. (The same bug bit log_analyze.py on the drone project.)"""
    rule("3. PHASE TIMELINE  (every transition, with the distance and heading it covered)")
    rows = run.rows
    runs = phase_runs(rows) if "phase" in rows[0] else []
    if not runs:
        print("  NOT AVAILABLE — this log's schema carries no 'phase' column, so the run cannot be")
        print("  split into segments. Only the whole-run figures in section 2 apply.")
        print("  Per-segment gyro-vs-encoder fusion and the MEASURED track width from a spin are")
        print("  ./scripts/decode_telemetry.py's job, not this one.")
        return
    if len(runs) < 2:
        print("  One phase only ('%s') for the whole run — nothing transitioned." % (runs[0][0] or "(blank)"))
        return
    print("    %-8s %5s %5s  %9s  %9s  %8s" % ("phase", "rows", "seq", "t_start", "fwd mm", "yaw deg"))
    for ph, lo, hi in runs:
        fl, fr = wheel_travel(rows, lo, hi)
        mm = "%+9.1f" % runlog.fwd_mm((fl + fr) / 2.0) if fl is not None else "        ?"
        # Unwrap the WHOLE slice, not just its endpoints: a segment that turns more than 180 deg
        # is invisible to a two-point unwrap, which reported +139 deg for a follow phase that had
        # actually gone right round a taped box. Caught on the 3-corner follow run, 2026-09-08.
        ys = [runlog.num(r, "yaw_ddeg") for r in rows[lo:hi + 1]]
        ys = [v / 10.0 for v in ys if v is not None]
        if len(ys) < 2:
            yaw = "       ?"
        else:
            hd = runlog.unwrap(ys)
            yaw = "%+8.1f" % (hd[-1] - hd[0])
        print("    %-8s %5d %5s  %8s ms %s  %s"
              % (ph or "(blank)", hi - lo + 1, rows[lo].get("seq", "?"),
                 rows[lo].get("t_ms", "?"), mm, yaw))
    print("  Per-segment gyro-vs-encoder fusion and the MEASURED track width from the turns are")
    print("  ./scripts/decode_telemetry.py's job, not this one — run it on a square-drive log.")


# ── 5. sensors ─────────────────────────────────────────────────────────────────────────────────

def section_sensors(run):
    rule("4. SENSORS  (what each colour sensor saw, and how close it came to each rule)")
    rows = run.rows
    for port in ("C", "D"):
        side = runlog.PORT_SIDE[port]
        refl = runlog.signal(rows, port, "reflection")
        if not refl and "refl%s_pct" % port not in rows[0]:
            print("  port %s (%s): not in this log's schema." % (port, side))
            continue
        print("  ── port %s = %s sensor" % (port, side))
        if not refl:
            print("     reflectance : EVERY read failed. This sensor reported nothing all run.")
        else:
            s = runlog.stats([v for _, v in refl])
            print("     reflectance : min %.0f  median %.0f  p95 %.0f  max %.0f  (%d samples)"
                  % (s["min"], s["p50"], s["p95"], s["max"], s["n"]))
            print("                   median %.0f reads as: %s" % (s["p50"], runlog.band(s["p50"])))
            print("                   peak   %.0f reads as: %s" % (s["max"], runlog.band(s["max"])))
        blue = runlog.signal(rows, port, "blue_frac")
        red = runlog.signal(rows, port, "red_frac")
        if blue:
            sb, sr = runlog.stats([v for _, v in blue]), runlog.stats([v for _, v in red])
            print("     blue frac   : min %.3f  median %.3f  max %.3f      b/(r+g+b)"
                  % (sb["min"], sb["p50"], sb["max"]))
            print("     red frac    : min %.3f  median %.3f  max %.3f      r/(r+g+b)"
                  % (sr["min"], sr["p50"], sr["max"]))
        else:
            print("     chromaticity: no usable r/g/b — fractions NOT ASSESSED.")
        dim, sat = runlog.chroma_rejected(rows, port)
        if dim or sat:
            print("     discarded   : %d row(s) too dim (r+g+b < %d) and %d saturated — their"
                  % (dim, runlog.MIN_CHROMA_TOTAL, sat))
            print("                   fractions are meaningless and are NOT in the numbers above.")

        for label, kind, cmp_, thr, source in runlog.RULES:
            pairs = runlog.signal(rows, port, kind)
            c = runlog.crossing(pairs, thr, above=(cmp_ == ">="))
            if c is None:
                print("     %-27s NOT ASSESSED — no usable samples for this signal." % label)
                continue
            fmt = "%.0f" if kind == "reflection" else "%.3f"
            if c["first"] is None:
                print(("     %-27s NEVER CROSSED. Threshold " + fmt + ", peak " + fmt
                       + " — SHORT BY " + fmt + ".")
                      % (label, thr, c["peak"], -c["margin"]))
            else:
                idx, val = c["first"]
                r = rows[idx]
                print(("     %-27s CROSSED. Threshold " + fmt + ", peak " + fmt
                       + " — cleared by " + fmt + ".") % (label, thr, c["peak"], c["margin"]))
                print(("                   first crossing at seq %s, t=%s ms, value " + fmt
                       + "; %d of %d samples on the trip side.")
                      % (r.get("seq", "?"), r.get("t_ms", "?"), val, c["hits"], c["n"]))
                if kind == "reflection":
                    if runlog.saturated(r, port):
                        print("                   ⚠ THAT ROW IS SATURATED. A pinned sensor reads")
                        print("                   98-99 reflection on anything, so this crossing is")
                        print("                   NOT evidence of a mine. Check section 6 first.")
                    rf = runlog.frac(r, port, "r")
                    if rf is not None:
                        colour = "PINK" if rf >= runlog.PINK_RED_FRAC_MIN else "YELLOW"
                        print("                   red fraction there %.3f -> names it %s "
                              "(split at %.2f; reporting only, never gates the count)"
                              % (rf, colour, runlog.PINK_RED_FRAC_MIN))
            print("                   rule source: %s" % source)


# ── 6. events ──────────────────────────────────────────────────────────────────────────────────

def section_events(run):
    rule("5. EVENTS  (the ticks that mattered, in time order)")
    rows = run.rows
    events = []
    if "phase" in rows[0]:
        for ph, lo, _ in phase_runs(rows)[1:]:
            events.append((runlog.num(rows[lo], "t_ms") or 0, rows[lo].get("seq", "?"),
                           "phase -> %s" % (ph or "(blank)")))
    for port in ("C", "D"):
        for label, kind, cmp_, thr, _src in runlog.RULES:
            pairs = runlog.signal(rows, port, kind)
            prev_hit = False
            for idx, val in pairs:
                hit = val >= thr if cmp_ == ">=" else val <= thr
                if hit and not prev_hit:
                    fmt = "%.0f" if kind == "reflection" else "%.3f"
                    events.append((runlog.num(rows[idx], "t_ms") or 0, rows[idx].get("seq", "?"),
                                   ("%s on port %s (%s) rose past threshold, value " + fmt)
                                   % (label, port, runlog.PORT_SIDE[port], val)))
                prev_hit = hit
    for col, name in (("statusL", "left motor"), ("statusR", "right motor")):
        prev = None
        for i, r in enumerate(rows):
            v = runlog.num(r, col)
            if v is None or v == prev:
                continue
            if prev is not None:
                events.append((runlog.num(r, "t_ms") or 0, r.get("seq", "?"),
                               "%s status %s -> %s" % (name, runlog.STATUS_NAMES.get(
                                   int(prev), int(prev)), runlog.STATUS_NAMES.get(int(v), int(v)))))
            prev = v
    if not events:
        print("  Nothing happened worth marking: no phase change, no threshold crossing, no motor")
        print("  status change. For a mission run that is a finding, not a blank.")
        return
    # seq is a string in the CSV, so sort it numerically or "10" lands before "2".
    events.sort(key=lambda e: (e[0], int(e[1]) if str(e[1]).isdigit() else 0))
    for t, seq, what in events[:MAX_EVENTS]:
        print("    %7.0f ms  seq %-4s  %s" % (t, seq, what))
    if len(events) > MAX_EVENTS:
        print("    ... and %d more, not shown. %d events in one run usually means a sensor flapping"
              % (len(events) - MAX_EVENTS, len(events)))
        print("    across a threshold, not that many separate things happening.")


# ── 7. health ──────────────────────────────────────────────────────────────────────────────────

def section_health(run):
    rule("6. HEALTH  (is this data good enough to draw a conclusion from?)")
    rows = run.rows
    problems = 0

    blank = {}
    for r in rows:
        for k, v in r.items():
            if k != "reason" and (v == "" or v == "None"):
                blank[k] = blank.get(k, 0) + 1
    if blank:
        problems += 1
        print("  UNREADABLE CELLS — the hub's read returned nothing and was logged blank:")
        for k in sorted(blank, key=lambda x: -blank[x]):
            print("    %-12s %d of %d rows (%.1f%%)" % (k, blank[k], len(rows),
                                                        100.0 * blank[k] / len(rows)))
        print("    A blank is a FAILED READ, not a zero. Nothing above counted these as data.")
    else:
        print("  unreadable cells   : none — every sensor answered on every row.")

    if "reason" in rows[0]:
        filled = sum(1 for r in rows if (r.get("reason") or "").strip())
        print("  per-row 'reason'   : %s"
              % ("%d row(s) carry one" % filled if filled else
                 "empty on every row — the hub programs write a reason only into the '#end' "
                 "line, so this column is reserved, not lost data."))

    for port in ("C", "D"):
        if "r%s" % port not in rows[0]:
            continue
        sat = sum(1 for r in rows if runlog.saturated(r, port))
        if sat:
            problems += 1
            print("  ⚠ port %s saturated  : %d of %d rows have a channel >= %d. A pinned sample's"
                  % (port, sat, len(rows), runlog.SATURATED_AT))
            print("      ratios collapse to 33/33/33 and carry NO colour information. If this is")
            print("      most of the run the sensor was against a surface or facing a light.")
        else:
            print("  port %s saturation  : none (no channel reached %d)." % (port, runlog.SATURATED_AT))

    for col, name in (("statusL", "left motor"), ("statusR", "right motor")):
        vals, _ = runlog.series(rows, col)
        if vals is None:
            continue
        seen = sorted(set(int(v) for v in vals))
        bad = [v for v in seen if v in (2, 5)]
        print("  %-18s : %s" % (name + " status", ", ".join(
            "%d=%s" % (v, runlog.STATUS_NAMES.get(v, "UNDOCUMENTED VALUE")) for v in seen)))
        if bad:
            problems += 1
            print("    ⚠ STALLED and/or DISCONNECTED appeared. A stall means the wheel was held;")
            print("      DISCONNECTED means the port read empty mid-run — a cable.")

    # velL/velR against the encoders. Recorded, not resolved: the docs say motor.velocity() is deg/s
    # (hub-api-surface-2026-09-01), and on these logs it is consistently ~10x smaller than the rate
    # the encoders show. Reporting the ratio is honest; asserting a unit would not be.
    t = [runlog.num(r, "t_ms") for r in rows]
    ratios = []
    for i in range(len(rows) - 1):
        v = runlog.num(rows[i + 1], "velL")
        a0, a1 = runlog.num(rows[i], "relA_deg"), runlog.num(rows[i + 1], "relA_deg")
        if None in (v, a0, a1, t[i], t[i + 1]) or t[i + 1] == t[i] or abs(v) < 2:
            continue
        dps = (a1 - a0) / ((t[i + 1] - t[i]) / 1000.0)
        ratios.append(dps / v)
    if ratios:
        s = runlog.stats(ratios)
        print("  velL vs encoders   : encoder-derived deg/s is %.1fx the logged velL (median over "
              "%d ticks)" % (s["p50"], s["n"]))
        if abs(s["p50"] - 1.0) > 0.25:
            problems += 1
            print("    ⚠ These disagree. docs/findings/hub-api-surface-2026-09-01.md records")
            print("      motor.velocity() as deg/s; on this log it is not. The unit is UNRESOLVED,")
            print("      so every speed in section 2 is derived from ENCODERS, which are measured.")

    if run.malformed:
        problems += 1
        print("  ⚠ %d line(s) had the wrong field count and were skipped." % run.malformed)
    if run.end is None:
        problems += 1
    print()
    print("  >>> %s" % ("DATA LOOKS CLEAN — conclusions above are safe to quote." if not problems
                        else "%d health issue(s) above. Read them before quoting any number." % problems))


# ── 8. trace ───────────────────────────────────────────────────────────────────────────────────

def section_trace(run):
    rule("7. TRACE  (each signal over the whole run, scaled to its own min..max)")
    rows = run.rows
    lines = [
        ("reflC (RIGHT)", [v for _, v in runlog.signal(rows, "C", "reflection")], "%.0f"),
        ("reflD (LEFT) ", [v for _, v in runlog.signal(rows, "D", "reflection")], "%.0f"),
        ("blueC        ", [v for _, v in runlog.signal(rows, "C", "blue_frac")], "%.3f"),
        ("blueD        ", [v for _, v in runlog.signal(rows, "D", "blue_frac")], "%.3f"),
    ]
    yaw, _ = runlog.series(rows, "yaw_ddeg")
    if yaw:
        lines.append(("yaw deg      ", runlog.unwrap([v / 10.0 for v in yaw]), "%.1f"))
    for col, label in (("relA_deg", "encA (left) "), ("relB_deg", "encB (right)")):
        vals, _ = runlog.series(rows, col)
        if vals:
            lines.append((label, vals, "%.0f"))
    for name, vals, fmt in lines:
        if not vals:
            print("  %s  (no data)" % name)
            continue
        print(("  %s  %s   " + fmt + " .. " + fmt)
              % (name, runlog.spark(vals), min(vals), max(vals)))
    print("  (Terminal only. Documents get mermaid, never ASCII art — CLAUDE.md.)")


def full_trace(run):
    rule("8. EVERY ROW")
    cols = [c for c in ("seq", "t_ms", "phase", "relA_deg", "relB_deg", "velL", "velR",
                        "yaw_ddeg", "reflC_pct", "reflD_pct") if c in run.rows[0]]
    print("    " + "  ".join("%-9s" % c for c in cols))
    for r in run.rows:
        print("    " + "  ".join("%-9s" % (r.get(c) or "-") for c in cols))


# ── main ───────────────────────────────────────────────────────────────────────────────────────

def main(argv):
    trace = "--trace" in argv
    args = [a for a in argv[1:] if not a.startswith("-")]
    if [a for a in argv[1:] if a.startswith("-") and a != "--trace"]:
        print("usage: analyse-run.py [FILE] [--trace]", file=sys.stderr)
        return 64
    if args:
        path, why = args[0], "named on the command line"
    else:
        path, why = runlog.newest()
    if not path:
        print("No CSV in %s. Download a run first:" % runlog.TMP_DIR, file=sys.stderr)
        print("  python3 hub_programmer/download.py --all", file=sys.stderr)
        return 2
    if not os.path.exists(path):
        print("FILE NOT FOUND: %s" % path, file=sys.stderr)
        return 2

    run = runlog.load(path)
    run.why = why
    if not section_identity(run):
        return 2
    section_verdict(run)
    section_motion(run)
    section_phases(run)
    section_sensors(run)
    section_events(run)
    section_health(run)
    section_trace(run)
    if trace:
        full_trace(run)
    print("=" * W)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)
