#!/usr/bin/env python3
"""analyse-survey.py — answer the three GATE-1 questions from a scan-surface capture.

    ./scripts/analyse-survey.py                 # today's capture
    ./scripts/analyse-survey.py <file>

Reports the SHIPPED brightness rule (reflection >= 30) first, then the REFUTED chromaticity rule for
comparison only. Runs the real src/ code for both,
so this is not a parallel re-implementation that could agree with the robot by accident and
disagree in the arena. What it reports:

  1. DO THE MINES TRIP THE DETECTOR?  Each non-floor surface is scored as a deviation from the
     learned FLOOR, against the same threshold main.py derives at run start. A mine that does not
     clear it is a mine the robot drives over and does not count.

  2. DOES THE BOUNDARY TAPE ALSO TRIP IT?  The anomaly front-end flags anything unlike the floor,
     and blue tape is unlike the floor. If the tape trips the detector, an unmodified sweep counts
     the boundary as mines. The professor has guaranteed mines are never blue (operator,
     2026-09-08), which is exactly what makes a blue veto safe to add.

  3. ARE THE SURFACES SEPARABLE FROM EACH OTHER?  classify.separability_report — scope FR-2b.

Pure host analysis. Touches no hardware.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))

import brightness         # noqa: E402
import calibration        # noqa: E402
import mission_config as config  # noqa: E402
import classify           # noqa: E402
import floor_anomaly      # noqa: E402

FLOOR_LABEL = "FLOOR"

# Both MEASURED 2026-09-08 from the first real note captures (docs/findings/runs/surface-survey-2026-09-08.txt):
#   * Held against the sensor, every channel pins at 1018-1024 and the ratios collapse to 33/33/33.
#     A saturated sample carries NO colour information, so it must never reach a centroid.
#   * With nothing under the sensor the reading is r=1,g=0,b=0 (total 1). classify._features only
#     rejects total <= 0, so that garbage point survives as chromaticity (1.0, 0.0) and would drag a
#     class centroid hard. Real surfaces measured 263-1715 total, so 30 is a safe floor.
SATURATED_AT = 1000
MIN_TOTAL = 30


def load(path):
    """-> (by_label, by_refl).

    by_label holds (r,g,b,i) for the CHROMATICITY analysis and drops saturated / near-dark rows.
    by_refl holds raw reflectance and drops NOTHING -- because the two questions need opposite
    hygiene. ⚠ MEASURED 2026-09-09: the chromaticity filters throw away 298 of 497 YELLOW_NOTE
    samples, and they are the BRIGHTEST ones (reflectance 98-99). Scoring a BRIGHTNESS rule on the
    dim survivors is how this tool came to report that yellow mines were undetectable.
    """
    by_label = {}
    by_refl = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("SV,"):
                continue
            f = line.split(",")
            if len(f) < 11:
                continue
            label, port_name = f[1], f[2]
            try:                                  # reflectance FIRST, before any filtering
                by_refl.setdefault(label, {}).setdefault(port_name, []).append(int(f[6]))
            except (ValueError, IndexError):
                pass
            try:
                r, g, b, i = int(f[7]), int(f[8]), int(f[9]), int(f[10])
            except ValueError:
                continue
            if max(r, g, b) >= SATURATED_AT:
                continue                       # ratios have collapsed; no colour information left
            if r + g + b < MIN_TOTAL:
                continue                       # nothing under the sensor
            by_label.setdefault(label, {}).setdefault(port_name, []).append((r, g, b, i))
    return by_label, by_refl


def chroma(samples):
    pts = [classify._features(s) for s in samples]
    pts = [p for p in pts if p is not None]
    if not pts:
        return None
    return (calibration.median([p[0] for p in pts]),
            calibration.median([p[1] for p in pts]),
            calibration.median([p[2] for p in pts]),
            len(pts))


def report_shipped_rule(by_refl, port_name):
    """THE RULE THE ROBOT ACTUALLY RUNS: reflection >= mission_config.MINE_REFL_ON.

    This section is the point of the tool on demo morning. It answers, from the real capture, the
    only two questions that matter: would each surface trip the shipped detector, and would the floor
    let the robot ARM at all.
    """
    labels = [l for l in sorted(by_refl) if port_name in by_refl[l] and by_refl[l][port_name]]
    if not labels:
        return
    print("")
    print("=" * 76)
    print("SENSOR %s -- THE SHIPPED RULE: reflection >= %.0f   (this is what the robot runs)"
          % (port_name, config.MINE_REFL_ON))
    print("=" * 76)
    print("  %-18s %5s %6s %6s %6s %6s   %s" % ("surface", "n", "min", "med", "p90", "max", "% >= on"))
    print("  " + "-" * 66)
    for label in labels:
        v = sorted(by_refl[label][port_name])
        n = len(v)
        med = v[n // 2]
        p90 = v[int(0.90 * (n - 1))]
        pct = 100.0 * sum(1 for x in v if x >= config.MINE_REFL_ON) / n
        print("  %-18s %5d %6d %6d %6d %6d   %5.1f%%" % (label, n, v[0], med, p90, v[-1], pct))

    if FLOOR_LABEL in by_refl and port_name in by_refl[FLOOR_LABEL]:
        print("")
        try:
            cal = brightness.derive_thresholds(by_refl[FLOOR_LABEL][port_name])
            print("  ARMING GATE: ARMS.  %s" % cal.describe())
        except Exception as exc:
            print("  ARMING GATE: REFUSES -- %s" % exc)
            print("  (That is the run refusing to start. Fix the floor or the mount, not the rule.)")


def report_port(by_label, port_name):
    labels = sorted(by_label)
    present = [l for l in labels if port_name in by_label[l] and by_label[l][port_name]]
    if not present:
        return
    print("")
    print("=" * 76)
    print("SENSOR %s" % port_name)
    print("=" * 76)

    print("")
    print("  %-14s %5s  %6s %6s  %8s" % ("surface", "n", "r_n", "g_n", "total"))
    print("  " + "-" * 48)
    for label in present:
        c = chroma(by_label[label][port_name])
        if c is None:
            print("  %-14s   -- no usable chromaticity" % label)
            continue
        print("  %-14s %5d  %6.4f %6.4f  %8.0f" % (label, c[3], c[0], c[1], c[2]))

    if FLOOR_LABEL not in present:
        print("")
        print("  NO '%s' CAPTURE on this sensor -- cannot score anomalies." % FLOOR_LABEL)
        print("  Run: ./scripts/scan-surface.py %s" % FLOOR_LABEL)
        return

    floor_samples = by_label[FLOOR_LABEL][port_name]
    try:
        model = floor_anomaly.build_floor_model(floor_samples)
        cal = floor_anomaly.derive_thresholds(model, floor_samples)
    except Exception as exc:
        print("")
        print("  FLOOR MODEL FAILED: %s" % exc)
        print("  That is a real answer: this floor cannot be modelled, and main.py would")
        print("  refuse to arm on it (CALIBRATION_FAILED) rather than count phantoms.")
        return

    print("")
    print("  floor model: %d band(s)   %s" % (len(model.exemplars), cal.describe()))
    print("")
    print("  ⚠ REFUTED chromaticity rule -- kept ONLY for comparison. This is NOT what the robot")
    print("    runs: it was measured to make yellow INVISIBLE and blue tape a 100%% false positive")
    print("    on this carpet (docs/findings/colour-survey-and-first-detection-2026-09-08.md).")
    print("  anomaly score vs this floor   (would trip when dev > on-threshold)")
    print("  %-14s %8s %8s %8s   %s" % ("surface", "med_dev", "min_dev", "%above", "verdict"))
    print("  " + "-" * 62)

    verdicts = {}
    for label in present:
        devs = [model.deviation(s) for s in by_label[label][port_name]]
        devs = [d for d in devs if d is not None]
        if not devs:
            continue
        above = sum(1 for d in devs if d > cal.on_threshold)
        pct = 100.0 * above / len(devs)
        if label == FLOOR_LABEL:
            verdict = "baseline" if pct < 5.0 else "FLOOR ITSELF TRIPS -- too noisy"
        elif pct >= 90.0:
            verdict = "TRIPS (reliable)"
        elif pct >= 50.0:
            verdict = "TRIPS (marginal)"
        elif pct > 5.0:
            verdict = "MOSTLY MISSED"
        else:
            verdict = "INVISIBLE"
        verdicts[label] = (pct, verdict)
        print("  %-14s %8.2f %8.2f %7.1f%%   %s"
              % (label, calibration.median(devs), min(devs), pct, verdict))

    # Separability, on the same samples, for FR-2b classification.
    try:
        classes = classify.build_classes(
            dict((l, by_label[l][port_name]) for l in present))
        fails = classify.separability_report(classes)
    except Exception as exc:
        print("")
        print("  separability: could not build classes (%s)" % exc)
        return
    print("")
    if fails:
        print("  NOT SEPARABLE as colour classes (distance < %.1f sigma):"
              % classify.SEPARATION_SIGMAS)
        for a, b, dist, req in fails:
            print("    %-13s vs %-13s  %.4f  needed %.4f  (short by %.4f)"
                  % (a, b, dist, req, req - dist))
    else:
        print("  All captured surfaces are separable as colour classes.")

    return verdicts


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if args:
        path = args[0]
    else:
        import glob
        runs = sorted(glob.glob(os.path.join(REPO, "docs", "findings", "runs",
                                             "surface-survey-*.txt")))
        if not runs:
            print("no surface-survey-*.txt in docs/findings/runs/ -- run scan-surface.py first")
            return 64
        path = runs[-1]
    if not os.path.exists(path):
        print("no such file: %s" % path)
        return 64

    by_label, by_refl = load(path)
    if not by_label:
        print("no SV rows in %s" % path)
        return 1

    print("")
    print("SURFACE SURVEY ANALYSIS -- %s" % os.path.relpath(path, REPO))
    print("surfaces captured: %s" % ", ".join(sorted(by_label)))

    for port_name in ("C", "D"):
        report_shipped_rule(by_refl, port_name)

    all_verdicts = {}
    for port_name in ("C", "D"):
        v = report_port(by_label, port_name)
        if v:
            all_verdicts[port_name] = v

    # ⚠ THE OLD "WHAT THIS MEANS FOR THE RUN" VERDICT WAS DELETED 2026-09-09. It scored the REFUTED
    # chromaticity rule and then told the operator, in confident prose, that his yellow mines were
    # undetectable and that he needed a blue veto -- both the exact OPPOSITE of what was measured and
    # of what src/brightness.py ships. On demo morning that would have pushed the Builder to change
    # the detector away from the rule GATE 1 was closed with. One accountable path per concern: the
    # SHIPPED-RULE section above is the verdict, and src/brightness.py owns the rule itself.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
