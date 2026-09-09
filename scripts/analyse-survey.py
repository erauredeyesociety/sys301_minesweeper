#!/usr/bin/env python3
"""analyse-survey.py — answer the three GATE-1 questions from a scan-surface capture.

    ./scripts/analyse-survey.py                 # today's capture
    ./scripts/analyse-survey.py <file>

Runs the REAL detection code (src/floor_anomaly.py, src/classify.py) over the labelled samples,
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

import calibration        # noqa: E402
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
    """-> {label: {port: [(r,g,b,i), ...]}}, dropping any row without usable chromaticity."""
    by_label = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("SV,"):
                continue
            f = line.split(",")
            if len(f) < 11:
                continue
            label, port_name = f[1], f[2]
            try:
                r, g, b, i = int(f[7]), int(f[8]), int(f[9]), int(f[10])
            except ValueError:
                continue
            if max(r, g, b) >= SATURATED_AT:
                continue                       # ratios have collapsed; no colour information left
            if r + g + b < MIN_TOTAL:
                continue                       # nothing under the sensor
            by_label.setdefault(label, {}).setdefault(port_name, []).append((r, g, b, i))
    return by_label


def chroma(samples):
    pts = [classify._features(s) for s in samples]
    pts = [p for p in pts if p is not None]
    if not pts:
        return None
    return (calibration.median([p[0] for p in pts]),
            calibration.median([p[1] for p in pts]),
            calibration.median([p[2] for p in pts]),
            len(pts))


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
    print("  ANOMALY SCORE vs this floor   (trips the detector when dev > on-threshold)")
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

    by_label = load(path)
    if not by_label:
        print("no SV rows in %s" % path)
        return 1

    print("")
    print("SURFACE SURVEY ANALYSIS -- %s" % os.path.relpath(path, REPO))
    print("surfaces captured: %s" % ", ".join(sorted(by_label)))

    all_verdicts = {}
    for port_name in ("C", "D"):
        v = report_port(by_label, port_name)
        if v:
            all_verdicts[port_name] = v

    # The one line that decides whether the sweep needs a blue veto before Demo Day.
    print("")
    print("=" * 76)
    print("WHAT THIS MEANS FOR THE RUN")
    print("=" * 76)
    for port_name, v in all_verdicts.items():
        tape = [l for l in v if "TAPE" in l and v[l][0] >= 50.0]
        mines = [l for l in v if l not in ("FLOOR",) and "TAPE" not in l]
        missed = [l for l in mines if v[l][0] < 90.0]
        print("")
        print("  sensor %s:" % port_name)
        if missed:
            print("    MINES NOT RELIABLY DETECTED: %s" % ", ".join(missed))
            print("      -> the sweep would drive over these and count nothing.")
        elif mines:
            print("    all captured mine colours trip the detector reliably.")
        if tape:
            print("    BOUNDARY TAPE ALSO TRIPS THE DETECTOR: %s" % ", ".join(tape))
            print("      -> an unmodified sweep counts the boundary as mines.")
            print("      -> needs the blue veto (mines are never blue -- operator 2026-09-08).")
        elif any("TAPE" in l for l in v):
            print("    boundary tape does NOT trip the detector -- no veto needed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
