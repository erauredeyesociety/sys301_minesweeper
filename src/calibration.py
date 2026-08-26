"""Derive detection thresholds from samples taken on the real floor at run start.

Why this exists: a reflectance threshold is meaningless without the floor, the lighting, and the
note pack it was measured against. Hard-coding one guarantees a re-tune every time anything
changes (scope TR-4). Instead we sample the actual surfaces immediately before the run.

Polarity is DETECTED, not assumed. A yellow note on dark carpet reads brighter than the floor;
the same note on white tile reads darker. The rest of the pipeline works in "signal" space where
on-target is always the high state, so nothing downstream needs to care.
"""

import config


def median(values):
    """Median without importing statistics (absent on MicroPython)."""
    if not values:
        raise ValueError("median of no samples")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def median_absolute_deviation(values):
    """MAD -- robust spread. Preferred over stdev: one stray sample cannot inflate it."""
    med = median(values)
    return median([abs(v - med) for v in values])


class CalibrationError(Exception):
    """Calibration could not produce usable thresholds. Fail loud, never guess."""


class Calibration(object):
    """Thresholds and polarity derived from measured samples.

    polarity is +1 when a target reads HIGHER than the floor, -1 when it reads LOWER.
    signal() maps a raw reading into a space where on-target is always the larger number,
    so the detector never has to branch on polarity.
    """

    def __init__(self, floor_level, target_level, on_threshold, off_threshold,
                 polarity, floor_noise):
        self.floor_level = floor_level
        self.target_level = target_level
        self.on_threshold = on_threshold
        self.off_threshold = off_threshold
        self.polarity = polarity
        self.floor_noise = floor_noise

    def contrast(self):
        return abs(self.target_level - self.floor_level)

    def signal(self, reading):
        """Raw reading -> polarity-normalised signal (on-target is always higher)."""
        return reading * self.polarity

    def describe(self):
        return ("floor={0:.1f} target={1:.1f} contrast={2:.1f} "
                "on>{3:.1f} off<{4:.1f} polarity={5:+d} floor_noise={6:.1f}").format(
                    self.floor_level, self.target_level, self.contrast(),
                    self.on_threshold, self.off_threshold, self.polarity, self.floor_noise)


def check_floor_stability(floor_samples, max_mad):
    """Raise CalibrationError unless the floor reading is steady enough to build on.

    calibrate() checks that floor and target are far apart, but a floor whose OWN reading
    wanders invalidates every threshold derived from it and shows up later as phantom counts.
    The measured MAD and the limit are both in the message because "calibration failed" tells
    the Builder nothing on the day -- the fix is almost always sensor height or a loose mount.
    """
    if not floor_samples:
        raise CalibrationError("no floor samples: floor stability cannot be judged")

    mad = median_absolute_deviation(floor_samples)
    if mad > max_mad:
        raise CalibrationError(
            "floor is not stable: MAD {0:.2f} > limit {1:.2f}".format(mad, max_mad))


def calibrate(floor_samples, target_samples):
    """Build a Calibration from measured floor and target samples.

    Raises CalibrationError when the two surfaces are not separable -- which is a real,
    expected outcome (a pale note on a pale floor), and must stop the run rather than
    produce a threshold that fires forever or never.
    """
    if not floor_samples:
        raise CalibrationError("no floor samples")
    if not target_samples:
        raise CalibrationError("no target samples")

    floor_level = median(floor_samples)
    target_level = median(target_samples)
    contrast = abs(target_level - floor_level)

    if contrast < config.MIN_CONTRAST:
        raise CalibrationError(
            "floor and target are not separable: contrast {0:.1f} < required {1:.1f} "
            "(floor {2:.1f}, target {3:.1f})".format(
                contrast, config.MIN_CONTRAST, floor_level, target_level))

    # The RATIO gate, not just the absolute one. MIN_CONTRAST and MAX_FLOOR_MAD are set as a pair so
    # their ratio lands on the research rule, but a hand-edit of either silently breaks that -- and the
    # result is a run that arms on separation the research says to refuse, then counts phantoms.
    # Checking the ratio itself is what makes the guarantee survive an edit.
    #
    # The rule is contrast >= 6 * floor_SD (detection-and-sweep-techniques.md). Our spread statistic is
    # MAD, and MAD ~ 0.6745 * SD for Gaussian noise, so 6 SD = 6/0.6745 = 8.90 MAD. Comparing a MAD
    # against a rule written in SD is exactly the 1.48x unit error that has already bitten this project
    # three times, so the conversion is done here once and named.
    floor_noise = median_absolute_deviation(floor_samples)
    if floor_noise > 0.0 and contrast < config.MIN_SNR_MAD * floor_noise:
        raise CalibrationError(
            "floor and target are not separable enough: contrast {0:.2f} is {1:.2f} MAD of floor "
            "noise, need {2:.2f} MAD (= 6 SD). floor {3:.1f} +/- {4:.2f} MAD, target {5:.1f}".format(
                contrast, contrast / floor_noise, config.MIN_SNR_MAD,
                floor_level, floor_noise, target_level))

    polarity = 1 if target_level > floor_level else -1

    # Work in signal space so the thresholds are ordered regardless of polarity.
    floor_signal = floor_level * polarity
    target_signal = target_level * polarity
    gap = config.HYSTERESIS_FRACTION * contrast
    midpoint = (floor_signal + target_signal) / 2.0

    on_threshold = midpoint + gap / 2.0     # must exceed this to turn ON
    off_threshold = midpoint - gap / 2.0    # must fall below this to turn OFF

    return Calibration(floor_level, target_level, on_threshold, off_threshold,
                       polarity, floor_noise)
