"""Detect a mine by how much light comes back -- the rule that MEASUREMENT chose, 2026-09-08.

WHY THIS REPLACED THE CHROMATICITY DETECTOR
    `floor_anomaly.py` learns the floor's COLOUR and flags anything unlike it. On the real classroom
    carpet that was measured to FAIL, and to fail silently in both directions at once:

        yellow note   median deviation 5.99   0% of samples cleared the threshold  -> INVISIBLE
        blue tape     median deviation 11.30  100% cleared it                      -> FALSE POSITIVE

    So the shipped robot would have armed cleanly, swept, missed every yellow mine and counted the
    boundary tape instead. The mechanism is QUANTISATION, not hue collision: the carpet returns only
    ~79 ADC counts total, so its fitted colour sigma is smaller than ONE ADC count, and that
    quantisation noise is exactly what the sigma-normalised rule divides by. Raising the band count
    would not have helped -- the band limit never overflowed.
    Full write-up: docs/findings/colour-survey-and-first-detection-2026-09-08.md

WHAT REPLACED IT, MEASURED on the mission's own surfaces at the mounted height:

        carpet       reflection  3 - 9
        blue tape    reflection  7 - 9        <-- INSIDE the carpet band
        yellow note  reflection 51 - 73
        pink note    reflection 97+

    Zero overlap and a 43-point gap. Three properties make this the right rule here:

      * COLOUR-AGNOSTIC. The mine colour may change on demo day; brightness does not care.
      * THE TAPE IS INVISIBLE TO IT. Tape sits inside the carpet band, so the mine detector cannot
        see the boundary at all -- there is NO blue veto, and interior tape costs the count nothing.
        The boundary is detected separately, by blue fraction, and the two rules cannot interfere.
      * SHADOWS ARE ASYMMETRIC IN OUR FAVOUR. The rule fires on HIGH reflectance, so a shadow can
        only cause a MISS, never a phantom. Chromaticity has no such asymmetry.

    PROVEN ON HARDWARE: examples/find_note.py found a real note while MOVING, untethered, twice --
    PINK at reflection 99 and YELLOW at 62, both correctly named. That closed GATE 1.

THE RESIDUAL RISK, stated honestly: a patch of carpet as bright as paper, somewhere we did not
sample. Two independent defences exist -- the event WIDTH gate (a bright fleck is too_narrow, a
bright patch too_wide), and the arming gate below, which REFUSES TO RUN on a floor that is too
bright rather than counting phantoms.

PURE (MicroPython subset): no f-strings, no numpy. Feeds detector.EdgeCounter unchanged.
"""

import calibration
import mission_config as config


class BrightnessCal(object):
    """A Calibration-shaped shim so detector.EdgeCounter runs on raw reflectance UNCHANGED.

    Reflectance IS the signal (identity map) and a mine is always the BRIGHTER value, so polarity is
    +1. detector.py never learns it is looking at brightness rather than colour distance -- which is
    the whole point: one counter, now three possible front ends (this, calibration.py, floor_anomaly).
    """

    def __init__(self, on_threshold, off_threshold, floor_level, floor_noise):
        self.floor_level = floor_level
        self.target_level = on_threshold
        self.on_threshold = on_threshold
        self.off_threshold = off_threshold
        self.polarity = 1
        self.floor_noise = floor_noise

    def signal(self, reading):
        return reading

    def contrast(self):
        return abs(self.target_level - self.floor_level)

    def describe(self):
        return ("brightness floor med={0:.1f} mad={1:.1f} on>{2:.1f} off<{3:.1f}".format(
            self.floor_level, self.floor_noise, self.on_threshold, self.off_threshold))


def derive_thresholds(floor_samples):
    """Floor reflectance readings -> a BrightnessCal, or raise CalibrationError.

    The thresholds are FIXED and measured (config.MINE_REFL_ON / _OFF) rather than derived from the
    floor, because the measured separation is enormous -- 43 points -- and a fixed number cannot be
    dragged upward by a run-start burst that happens to cross something bright. What the floor burst
    IS used for is the ARMING GATE: it must confirm the floor really is dark here.

    Refusing to arm is a CORRECT outcome (CONOPS OS-5). A phantom count read aloud to the instructor
    is not. This gate is the one structural protection the chromaticity path never had -- its own
    docstring concedes it has no calibrate-time contrast check.
    """
    usable = [s for s in floor_samples if s is not None]
    if not usable:
        raise calibration.CalibrationError(
            "no usable floor reflectance samples: every reading was unreadable")

    floor_med = calibration.median(usable)
    floor_mad = calibration.median_absolute_deviation(usable)

    # ⚠ A PERCENTILE, NOT THE MAX. Using max() meant a SINGLE bright sample refused the whole run --
    # one fleck in the carpet, or a mine lying in the 450 mm calibration creep path, and the robot
    # will not start in front of the instructor. The 90th percentile tolerates a few outliers while
    # still refusing a floor that is genuinely bright. Guarded on sample count so a short burst
    # cannot make the percentile meaningless.
    ordered = sorted(usable)
    if len(ordered) >= 20:
        floor_high = ordered[int(0.90 * (len(ordered) - 1))]
    else:
        floor_high = ordered[-1]        # too few samples to percentile honestly -- fall back to max

    # BOTH conditions: the bulk of the floor must be dark (median below the falling-edge threshold)
    # AND its 90th percentile must clear the on-threshold by the margin.
    if floor_med > config.MINE_REFL_OFF:
        raise calibration.CalibrationError(
            "floor median {0:.0f} is at or above the off-threshold {1:.0f} -- this surface is too "
            "bright to be the dark carpet the rule was measured on.".format(
                floor_med, config.MINE_REFL_OFF))
    if floor_high > config.MINE_REFL_ON - config.MINE_FLOOR_MARGIN:
        raise calibration.CalibrationError(
            "floor is too bright to detect mines against: 90th-percentile floor {0:.0f} against an "
            "on-threshold of {1:.0f} (needs to stay {2:.0f} below it). Either the sensor is not "
            "seeing the floor, or this surface is not the dark carpet the rule was measured on."
            .format(floor_high, config.MINE_REFL_ON, config.MINE_FLOOR_MARGIN))

    return BrightnessCal(config.MINE_REFL_ON, config.MINE_REFL_OFF, floor_med, floor_mad)


def fuse(readings):
    """Several sensors' reflectance -> ONE scalar for the counter, or None if none could be read.

    MAX, deliberately. Each sensor covers a different strip of floor, so the pair's swath is their
    UNION -- and taking the maximum means one physical mine crossing EITHER sensor produces exactly
    ONE event. That is what keeps the count right: two independent counters would count a mine twice
    whenever it passed under both, and lane overlap makes that common.

    The honest cost: two DIFFERENT mines passing under the two sensors at the same instant read as
    one event, and undercount by one. That needs two mines less than the sensor spacing apart and
    aligned across the lane, which is rarer than the double-count it prevents -- and an undercount is
    the safer error to make when the number is read aloud.

    None (not 0) when nothing could be read: a failed read is missing data, not a dark floor.
    """
    usable = [r for r in readings if r is not None]
    if not usable:
        return None
    return max(usable)
