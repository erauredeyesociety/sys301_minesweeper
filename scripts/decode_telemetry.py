#!/usr/bin/env python3
"""decode_telemetry.py -- read a telemetry CSV and say, in plain words, what the robot did.

The companion to hub_telemetry_log.py: that logs raw numbers on the hub, this turns a downloaded log
into a human-readable summary. Host-side, pure Python, no numpy. It reuses the src/ pure modules so
the wheel diameter and the mirror sign live in ONE place, not two.

    scripts/decode_telemetry.py                       # newest file in tmp/telemetry/
    scripts/decode_telemetry.py path/to/run.csv       # a specific log
    scripts/decode_telemetry.py --verbose             # also print the notable rows

The log's raw encoders are equal-and-opposite on this mirrored chassis (forward = A negative,
B positive), so this applies hub_api's measured sign convention before reporting forward motion --
the same fix that keeps odometry from integrating a forward move to zero.
"""
import glob
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import config                                                    # noqa: E402
import hub_api                                                   # noqa: E402
import motion_tuning                                             # noqa: E402
from odometry import degrees_to_mm, normalize_angle             # noqa: E402

TMP_DIR = os.path.join(ROOT, "tmp", "telemetry")


def load(path):
    """Return (header list, list of row dicts). Skips '#' metadata lines."""
    header, rows = None, []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if header is None:
            header = fields
            continue
        if len(fields) != len(header):
            continue
        rows.append(dict(zip(header, fields)))
    return header or [], rows


def col(rows, name, cast=float):
    out = []
    for r in rows:
        v = r.get(name, "")
        if v in ("", "None"):
            continue
        try:
            out.append(cast(v))
        except ValueError:
            pass
    return out


def span(vals):
    return (min(vals), max(vals)) if vals else (0.0, 0.0)


def phase_groups(rows):
    """Split rows into consecutive runs of the same 'phase' value. [(phase, [rows]), ...]."""
    groups = []
    for r in rows:
        ph = r.get("phase", "")
        if not groups or groups[-1][0] != ph:
            groups.append((ph, []))
        groups[-1][1].append(r)
    return groups


def phase_report(rows):
    """When a log carries a 'phase' column with side*/turn* labels (a square-drive run), report
    motors-vs-IMU PER SEGMENT: forward distance and heading drift on each straight side, and gyro
    degrees plus the MEASURED track width on each turn. Returns True if it ran.

    Track width from an in-place spin: each wheel travels arc = (track/2)*theta, so
    track = 2*arc/theta -- gyro gives the true heading (theta), encoders the wheel travel (arc).
    This closes the [ASSUMED] TRACK_WIDTH_MM against real hardware, one turn at a time.
    """
    if not rows or "phase" not in rows[0]:
        return False
    labels = set(r.get("phase", "") for r in rows)
    if not any(l.startswith("side") or l.startswith("turn") for l in labels):
        return False

    ls, rs = hub_api.LEFT_MOTOR_FORWARD_SIGN, hub_api.RIGHT_MOTOR_FORWARD_SIGN
    d = config.WHEEL_DIAMETER_MM

    def num(row, name):
        v = row.get(name, "")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    print("  PHASE BREAKDOWN (motors vs IMU, per segment)")
    track_estimates = []
    for ph, grp in phase_groups(rows):
        if ph.startswith("stop") or not ph:
            continue
        a0, a1 = num(grp[0], "relA_deg"), num(grp[-1], "relA_deg")
        b0, b1 = num(grp[0], "relB_deg"), num(grp[-1], "relB_deg")
        y0, y1 = num(grp[0], "yaw_ddeg"), num(grp[-1], "yaw_ddeg")
        if None in (a0, a1, b0, b1):
            continue
        d_a, d_b = a1 - a0, b1 - b0
        gyro = normalize_angle((y1 - y0) / 10.0) if (y0 is not None and y1 is not None) else None
        if ph.startswith("side"):
            fwd = (degrees_to_mm(ls * d_a, d) + degrees_to_mm(rs * d_b, d)) / 2.0
            drift = "%+5.1f" % gyro if gyro is not None else "  n/a"
            print("    %-6s fwd %+6.0f mm   heading drift %s deg" % (ph, fwd, drift))
        elif ph.startswith("turn"):
            arc = (degrees_to_mm(abs(d_a), d) + degrees_to_mm(abs(d_b), d)) / 2.0
            theta = math.radians(abs(gyro)) if gyro else 0.0
            tw = 2.0 * arc / theta if theta > 0.01 else None
            if tw:
                track_estimates.append(tw)
            g = "%+6.1f" % gyro if gyro is not None else "   n/a"
            print("    %-6s gyro %s deg   arc %5.0f mm  -> track %s mm"
                  % (ph, g, arc, ("%.0f" % tw) if tw else "n/a"))
    if track_estimates:
        mean_tw = sum(track_estimates) / len(track_estimates)
        print("    >> MEASURED track width (mean of %d turns): %.0f mm   [config TRACK_WIDTH_MM = %.0f]"
              % (len(track_estimates), mean_tw, config.TRACK_WIDTH_MM))
    return True


def decode(path, verbose):
    header, rows = load(path)
    if not rows:
        print("no data rows in %s" % path)
        return 1
    print("Telemetry decode: %s" % os.path.relpath(path, ROOT))

    t = col(rows, "t_ms")
    dur_s = (t[-1] - t[0]) / 1000.0 if len(t) > 1 else 0.0
    hz = (len(t) - 1) / dur_s if dur_s > 0 else 0.0
    print("  samples: %d over %.1f s  =>  %.1f Hz" % (len(rows), dur_s, hz))

    # A phase-labelled run (the square drive) gets a per-segment breakdown; it is the primary view.
    phase_report(rows)

    # --- MOTION -------------------------------------------------------------
    ra = col(rows, "relA_deg")
    rb = col(rows, "relB_deg")
    print("  MOTION")
    if ra and rb:
        # Apply the measured mirror sign so both wheels read forward-positive.
        fl = hub_api.LEFT_MOTOR_FORWARD_SIGN * (ra[-1] - ra[0])
        fr = hub_api.RIGHT_MOTOR_FORWARD_SIGN * (rb[-1] - rb[0])
        dl = degrees_to_mm(fl, config.WHEEL_DIAMETER_MM)
        dr = degrees_to_mm(fr, config.WHEEL_DIAMETER_MM)
        fwd = (dl + dr) / 2.0
        # Encoder heading change: (right - left) arc over the track width.
        enc_turn = math.degrees((dr - dl) / config.TRACK_WIDTH_MM) if config.TRACK_WIDTH_MM else 0.0
        print("    left wheel : %+7.1f mm  (fwd-adjusted enc %+d deg)" % (dl, int(fl)))
        print("    right wheel: %+7.1f mm  (fwd-adjusted enc %+d deg)" % (dr, int(fr)))
        print("    net forward: %+7.1f mm   net rotation (encoders): %+.1f deg" % (fwd, enc_turn))
        yaw = col(rows, "yaw_ddeg")
        gyro_turn = None
        if yaw:
            # Yaw wraps at +-180, so a multi-turn spin must be UNWRAPPED before differencing --
            # otherwise the total collapses to a meaningless residual. motion_tuning.unwrap_degrees
            # is the shared implementation; do not reinvent it here.
            unwrapped = motion_tuning.unwrap_degrees([v / 10.0 for v in yaw])
            gyro_turn = unwrapped[-1] - unwrapped[0]
            agree = abs(gyro_turn - enc_turn) < max(5.0, 0.05 * abs(gyro_turn))
            # The fault-detection case: wheels turned a lot (encoders) but the body did not
            # rotate (gyro) -> the robot is HELD, BLOCKED, or the wheels are SLIPPING. This is
            # the turn_slip / stuck signal (motion_tuning, odometry-fusion research).
            if abs(enc_turn) > 90.0 and abs(gyro_turn) < 0.25 * abs(enc_turn):
                verdict = "WHEELS SPUN, ROBOT DID NOT ROTATE -> held / blocked / slipping (slip-fault case)"
            elif agree:
                verdict = "gyro/encoder agree"
            else:
                verdict = "both rotated but differ -> track width off or partial slip; see estimate"
            print("    net rotation (gyro yaw): %+.1f deg   [%s]" % (gyro_turn, verdict))
        moved = abs(fwd) > 3.0 or (gyro_turn is not None and abs(gyro_turn) > 5.0)
        print("    verdict: %s" % ("MOVED" if moved else "ESSENTIALLY STILL (this run characterises the pipeline, not motion)"))
        # An in-place spin (near-zero net forward, real rotation) MEASURES the track width:
        # gyro is the true heading, encoders the wheel travel. This closes an [ASSUMED] constant.
        if gyro_turn is not None and abs(gyro_turn) > 90.0 and abs(fwd) < 0.2 * (abs(dl) + abs(dr) + 1):
            hd = motion_tuning.unwrap_degrees([v / 10.0 for v in yaw])
            n = min(len(ra), len(rb), len(hd))
            try:
                tw = motion_tuning.track_width_from_samples_mm(
                    [hub_api.LEFT_MOTOR_FORWARD_SIGN * v for v in ra[:n]],
                    [hub_api.RIGHT_MOTOR_FORWARD_SIGN * v for v in rb[:n]],
                    hd[:n], config.WHEEL_DIAMETER_MM)
                print("    >> TRACK WIDTH measured from this spin: %.1f mm  (config assumes %.1f mm)"
                      % (tw, config.TRACK_WIDTH_MM))
            except Exception as exc:
                print("    (track-width estimate failed: %s)" % type(exc).__name__)
    else:
        print("    no encoder columns")

    # --- IMU ----------------------------------------------------------------
    print("  IMU")
    ax, ay, az = col(rows, "accx_mg"), col(rows, "accy_mg"), col(rows, "accz_mg")
    if ax and ay and az:
        means = [sum(ax) / len(ax), sum(ay) / len(ay), sum(az) / len(az)]
        axis = ["X", "Y", "Z"][max(range(3), key=lambda i: abs(means[i]))]
        print("    gravity on %s axis (mean a = %.0f/%.0f/%.0f mg) => %s"
              % (axis, means[0], means[1], means[2],
                 "upright/flat" if axis == "Z" and means[2] > 800 else "tilted/other mount"))
        # Disturbance = how far |a| strays from 1 g across the run.
        worst = max(abs(math.sqrt(x * x + y * y + z * z) - 989.0) for x, y, z in zip(ax, ay, az))
        print("    accel disturbance: worst |a|-1g = %.0f mg  => %s"
              % (worst, "handled/shaken" if worst > 60 else "held still"))
    pit, rol = col(rows, "pitch_ddeg"), col(rows, "roll_ddeg")
    if pit:
        pl, ph = span(pit)
        rl, rh = span(rol) if rol else (0, 0)
        print("    tilt range: pitch %.1f..%.1f deg, roll %.1f..%.1f deg"
              % (pl / 10.0, ph / 10.0, rl / 10.0, rh / 10.0))

    # --- COLOUR -------------------------------------------------------------
    print("  COLOUR")
    for s in ("C", "D"):
        refl = col(rows, "refl%s_pct" % s)
        r = col(rows, "r%s" % s)
        g = col(rows, "g%s" % s)
        b = col(rows, "b%s" % s)
        if not refl:
            continue
        lo, hi = span(refl)
        mr = sum(r) / len(r) if r else 0
        mg = sum(g) / len(g) if g else 0
        mb = sum(b) / len(b) if b else 0
        tot = mr + mg + mb or 1
        dom = ["R", "G", "B"][max(range(3), key=lambda i: (mr, mg, mb)[i])]
        event = "reflection swings %.0f%% -> a surface change crossed the sensor" % (hi - lo) \
            if (hi - lo) > 15 else "reflection stable (%.0f-%.0f%%), no surface event" % (lo, hi)
        print("    sensor %s: mean rgb %.0f/%.0f/%.0f (dominant %s, %.0f%%/%.0f%%/%.0f%%); %s"
              % (s, mr, mg, mb, dom, 100 * mr / tot, 100 * mg / tot, 100 * mb / tot, event))

    if verbose:
        print("  NOTABLE ROWS (largest accel deviation):")
        scored = sorted(rows, key=lambda r: _dev(r), reverse=True)[:5]
        for r in scored:
            print("    t=%sms  yaw=%s  a=(%s,%s,%s)  Cref=%s Dref=%s"
                  % (r.get("t_ms"), r.get("yaw_ddeg"), r.get("accx_mg"), r.get("accy_mg"),
                     r.get("accz_mg"), r.get("reflC_pct"), r.get("reflD_pct")))
    return 0


def _dev(r):
    try:
        a = (float(r["accx_mg"]), float(r["accy_mg"]), float(r["accz_mg"]))
        return abs(math.sqrt(sum(x * x for x in a)) - 989.0)
    except (KeyError, ValueError):
        return 0.0


def main(argv):
    verbose = "--verbose" in argv
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args:
        path = args[0]
    else:
        files = sorted(glob.glob(os.path.join(TMP_DIR, "*.csv")))
        if not files:
            print("no CSV in %s -- pass a path, or download a run first" % TMP_DIR)
            return 64
        path = files[-1]
    return decode(path, verbose)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
