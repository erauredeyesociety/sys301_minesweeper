#!/usr/bin/env python3
"""Sweep coverage time budget -- the arithmetic behind docs/findings/coverage-time-budget.md.

    ./scripts/coverage-budget.py            the tables as the finding prints them
    ./scripts/coverage-budget.py --turn 1.5 optimistic turn overhead instead of 3.0 s

Everything here is ARITHMETIC over parameters, not a measurement. Two inputs are MEASURED on our
hub (the 930 deg/s motor ceiling, the fact that we own two colour sensors); every other number is
marked [ASSUMED] in the PARAMS block and in the finding. Edit the PARAMS and the ARENAS list --
that is the whole point of this file existing rather than a spreadsheet.

The one thing to understand before reading the output: SPEED IN deg/s DOES NOT CONVERT TO mm/s
WITHOUT THE WHEEL DIAMETER, and the wheel diameter is UNMEASURED. So every time is printed once
per candidate wheel, and one ruler across a tyre deletes two thirds of this output.
"""

import argparse
import math

# --- PARAMS ------------------------------------------------------------------
W_MM = 76.0          # [ASSUMED] sticky-note width. Standard 3 in note; the real pack is unseen.
E_MM = 15.0          # [ASSUMED] one-sided cross-track error. UMBmark run must measure it (KU-M4).
MARGIN_MM = 5.0      # deliberate overlap, = config.LANE_OVERLAP_MM
BAR_TOL_MM = 3.0     # [ASSUMED] one-sided error in the SPACING between two sensors on a rigid bar.
                     # This is a BUILD tolerance, not an odometry one -- see the finding.

MOTOR_MAX_DPS = 930.0    # MEASURED 2026-08-27: motor.info(port.A) -> (device_id=48, max_speed=930)
HEADING_HEADROOM = 0.80  # [ASSUMED] fraction of the command ceiling we may sweep at, so the
                         # heading-hold loop still has one-sided correction authority.

V_CLASSIFY = 195.0   # mm/s sensing ceiling WITH colour classification (trade study 7.1)
V_PRESENCE = 650.0   # mm/s sensing ceiling for presence-only ([ASSUMED] 3 pure samples at 100 Hz,
                     # and the LOOP rate is unmeasured -- KU-M5)

WHEELS_MM = (24.0, 56.0, 88.0)   # the three candidate wheels. WHICH ONE WE OWN IS UNMEASURED.

ARENAS = [
    ("10 inches",          254.0),
    ("10 x 76 mm cells",   760.0),
    ("10 x 6 in tiles",   1524.0),
    ("10 x 30 cm tiles",  3000.0),
    ("10 feet",           3048.0),
    ("10 metres",        10000.0),
]


def lane_pitch(n_sensors, spacing_mm=None):
    """Lateral advance between successive PASSES of the robot, in mm.

    N=1: the classic pitch, W - 2e - margin.
    N=2: the inter-pass gap still pays 2e (two passes, independent errors), but the INTRA-pass gap
    between the two sensors pays only the bar's own spacing tolerance, because both sensors ride
    the same bar and drift together. So P = S + (W - 2e - margin), capped by S <= W - 2b - margin.
    """
    base = W_MM - 2.0 * E_MM - MARGIN_MM
    if base <= 0.0:
        raise ValueError("cross-track error too large for the target size")
    if n_sensors == 1:
        return base
    if spacing_mm is None:
        spacing_mm = max_spacing()
    if spacing_mm > max_spacing():
        raise ValueError("spacing {0:.0f} mm exceeds {1:.0f} mm: a note can fall BETWEEN the two "
                         "sensors and coverage is no longer guaranteed".format(
                             spacing_mm, max_spacing()))
    return spacing_mm + base


def max_spacing():
    """Widest defensible spacing between two sensors on one bar."""
    return W_MM - 2.0 * BAR_TOL_MM - MARGIN_MM


def sweep_speed(wheel_mm, sensing_ceiling):
    """mm/s actually available: the motor command ceiling, derated, capped by sensing."""
    v_motor = math.pi * wheel_mm * MOTOR_MAX_DPS / 360.0
    return min(HEADING_HEADROOM * v_motor, sensing_ceiling), v_motor


def run_time_s(side_mm, pitch_mm, speed_mms, turn_s):
    passes = math.ceil(side_mm / pitch_mm)
    path_mm = passes * side_mm
    return passes, path_mm, path_mm / speed_mms + (passes - 1) * turn_s


def speed_needed_mms(side_mm, pitch_mm, limit_s, turn_s):
    """The traverse speed that would just meet limit_s. None if the turns alone blow the limit."""
    passes = math.ceil(side_mm / pitch_mm)
    drive_s = limit_s - (passes - 1) * turn_s
    if drive_s <= 0.0:
        return None
    return (passes * side_mm) / drive_s


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turn", type=float, default=3.0,
                    help="[ASSUMED] seconds per end-of-lane turn (default 3.0, optimistic 1.5)")
    args = ap.parse_args()
    turn = args.turn

    p1 = lane_pitch(1)
    p2_narrow = lane_pitch(2, p1)
    p2_wide = lane_pitch(2, max_spacing())

    print("PARAMETERS  W={0:.0f} mm [ASSUMED]  e={1:.0f} mm [ASSUMED]  margin={2:.0f} mm  "
          "bar tol={3:.0f} mm [ASSUMED]  t_turn={4:.1f} s [ASSUMED]".format(
              W_MM, E_MM, MARGIN_MM, BAR_TOL_MM, turn))
    print("PASS PITCH  N=1: {0:.0f} mm   N=2 @ S={1:.0f} mm: {2:.0f} mm ({3:.2f}x)   "
          "N=2 @ S={4:.0f} mm (widest): {5:.0f} mm ({6:.2f}x)".format(
              p1, p1, p2_narrow, p2_narrow / p1, max_spacing(), p2_wide, p2_wide / p1))
    print()

    print("SPEED -- mm/s is NOT known until the wheel is measured. "
          "v_cmd = pi * D * {0:.0f} / 360.".format(MOTOR_MAX_DPS))
    print("{0:<10} {1:>12} {2:>14} {3:>16} {4:>16}".format(
        "wheel D", "v_cmd max", "sweep @80%", "presence-only", "classification"))
    for d in WHEELS_MM:
        vp, vmotor = sweep_speed(d, V_PRESENCE)
        vc, _ = sweep_speed(d, V_CLASSIFY)
        print("{0:<10} {1:>10.0f}   {2:>12.0f}   {3:>14.0f}   {4:>14.0f}".format(
            "{0:.0f} mm".format(d), vmotor, HEADING_HEADROOM * vmotor, vp, vc))
    print()

    for label, ceiling in (("PRESENCE-ONLY", V_PRESENCE), ("WITH CLASSIFICATION", V_CLASSIFY)):
        print("RUN TIME, minutes -- {0} (sensing ceiling {1:.0f} mm/s)".format(label, ceiling))
        head = "{0:<20} {1:>7}".format("arena", "side m")
        for d in WHEELS_MM:
            head += "  {0:>15}".format("D={0:.0f}: 1 / 2".format(d))
        print(head)
        for name, side in ARENAS:
            row = "{0:<20} {1:>7.2f}".format(name, side / 1000.0)
            for d in WHEELS_MM:
                v, _ = sweep_speed(d, ceiling)
                _, _, t1 = run_time_s(side, p1, v, turn)
                _, _, t2 = run_time_s(side, p2_wide, v, turn)
                row += "  {0:>6.1f} /{1:>6.1f}".format(t1 / 60.0, t2 / 60.0)
            print(row)
        print()

    print("SPEED REQUIRED to hit a time gate (mm/s). '--' = the turns alone exceed the gate.")
    print("{0:<20} {1:>10} {2:>10} {3:>10} {4:>10}".format(
        "arena", "3min N=1", "3min N=2", "5min N=1", "5min N=2"))
    for name, side in ARENAS:
        cells = []
        for limit in (180.0, 300.0):
            for pitch in (p1, p2_wide):
                need = speed_needed_mms(side, pitch, limit, turn)
                cells.append("--" if need is None else "{0:.0f}".format(need))
        print("{0:<20} {1:>10} {2:>10} {3:>10} {4:>10}".format(name, *cells))
    print()
    print("Compare each cell against the sweep column above: a gate is REACHABLE only if the "
          "required speed sits under 80% of pi*D*930/360 for the wheel we actually own.")


if __name__ == "__main__":
    main()
