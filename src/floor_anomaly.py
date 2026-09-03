"""Flag a surface that deviates from the LEARNED FLOOR -- colour-agnostic mine detection.

WHY THIS EXISTS alongside calibration.py: calibration.py needs a KNOWN target exemplar to derive a
threshold. On competition day we may not have one -- the mine colour may not be yellow, and the floor
may not be what we tuned on (it may be the multicolour carpet). Operator, 2026-09-03: "the floor
might change ... we have to calibrate the robot with what the 'floor' is on competition day". So we
learn the FLOOR at run start and flag anything UNLIKE it, with no idea what a mine looks like.

The metric is classify.py's sigma-distance turned INSIDE OUT: instead of "distance to the nearest
colour CLASS", it is "distance to the nearest floor BAND" -- large means unlike every floor colour we
saw. It works in chromaticity (r/(r+g+b), g/(r+g+b)), which divides brightness out, so it survives the
~50 mm loose mount height and battery sag that move the raw numbers. The scalar it produces feeds
detector.py's four-state counter UNCHANGED, through FloorDeviationCal.

Design, threshold derivation and the mandatory bench validation:
docs/research/floor-relative-colour-anomaly-2026-09-03.md.

PURE (MicroPython subset) -- reuses calibration + classify + config, no numpy, no f-strings.
The blind spot is irreducible and NOT a tuning: a note whose chromaticity matches a floor band reads
deviation ~ 0 and is invisible to any colour-only metric. That is a professor question, not a knob.
"""

import config
import calibration
import classify

# Greedy-clustering knobs. Self-scaling off the floor's own spread, so there is no magic chromaticity
# constant here. [ASSUMED] shapes, settled by the bench recording in the research doc.
K_MAX = 6              # more than this many floor bands => the floor is too busy to model; FAIL LOUD
MERGE_SIGMAS = 4.0     # a sample within this many GLOBAL sigmas of a band seed joins that band
# The deviation scalar is sigma-normalised, so its floor noise cannot be allowed to collapse to zero
# (a perfectly uniform floor) or the threshold would sit exactly on the median and fire on noise.
MIN_DEV_MAD = 0.1     # [ASSUMED] floor on the deviation-space MAD; settled by the bench recording


class FloorModel(object):
    """The floor as a small set of colour bands (classify.ColorClass exemplars), plus the deviation."""

    def __init__(self, exemplars):
        self.exemplars = exemplars

    def deviation(self, rgbi):
        """One (r,g,b,i) reading -> scalar distance to the NEAREST floor band, or None if unreadable.

        Higher = more unlike the floor. None (not 0.0) when the sample has no usable chromaticity --
        the caller skips it and counts it, never fabricates a reading of zero deviation."""
        f = classify._features(rgbi)
        if f is None:
            return None
        r_n, g_n = f[0], f[1]
        best = None
        for c in self.exemplars:
            d = classify._dist(r_n, g_n, c.cx, c.cy) / c.sigma
            if best is None or d < best:
                best = d
        return best


def build_floor_model(floor_samples):
    """N run-start floor (r,g,b,i) samples -> a multi-modal FloorModel via robust greedy clustering.

    Multi-modal because the floor is not one colour: the carpet is a few colour bands, so a single
    centroid would call the band boundaries themselves anomalies. Each band becomes one exemplar.
    """
    points = []
    for s in floor_samples:
        f = classify._features(s)
        if f is not None:
            points.append((f[0], f[1]))
    if not points:
        raise calibration.CalibrationError("no usable floor samples: every reading was unreadable")

    # One robust pass for scale: spread about the global median sets the merge radius without a magic
    # number, so the same code fits a tight tile floor and a loose carpet.
    gx = calibration.median([p[0] for p in points])
    gy = calibration.median([p[1] for p in points])
    dists = [classify._dist(p[0], p[1], gx, gy) for p in points]
    global_sigma = 1.4826 * calibration.median_absolute_deviation(dists)
    if global_sigma < classify.MIN_SIGMA:
        global_sigma = classify.MIN_SIGMA
    merge_radius = MERGE_SIGMAS * global_sigma

    # Greedy radius clustering: a point joins the first band whose running-median centre is within
    # merge_radius, else it seeds a new band. More than K_MAX bands means this is not a floor.
    clusters = []      # each: [xs, ys]
    for (x, y) in points:
        placed = False
        for cluster in clusters:
            cx = calibration.median(cluster[0])
            cy = calibration.median(cluster[1])
            if classify._dist(x, y, cx, cy) <= merge_radius:
                cluster[0].append(x)
                cluster[1].append(y)
                placed = True
                break
        if not placed:
            if len(clusters) >= K_MAX:
                raise calibration.CalibrationError(
                    "floor has more than {0} colour bands: too busy to model as floor".format(K_MAX))
            clusters.append([[x], [y]])

    exemplars = []
    for cluster in clusters:
        cx = calibration.median(cluster[0])
        cy = calibration.median(cluster[1])
        ds = [classify._dist(px, py, cx, cy) for px, py in zip(cluster[0], cluster[1])]
        sigma = 1.4826 * calibration.median_absolute_deviation(ds)
        if sigma < classify.MIN_SIGMA:
            sigma = classify.MIN_SIGMA
        # total_median is unused in deviation space; n carries the band's sample count for reporting.
        exemplars.append(classify.ColorClass("floor", cx, cy, sigma, 0.0, len(cluster[0])))
    return FloorModel(exemplars)


class FloorDeviationCal(object):
    """A Calibration-shaped shim so detector.EdgeCounter runs on the deviation scalar UNCHANGED.

    The deviation scalar IS the signal (identity map), and a mine is always the HIGHER value, so
    polarity is +1. detector.py never learns it is looking at anomaly distance, not reflectance --
    which is the whole point: one counter, two front ends (calibration.py or this).
    """

    def __init__(self, floor_dev_median, floor_dev_mad, on_threshold, off_threshold):
        self.floor_level = floor_dev_median
        self.target_level = on_threshold
        self.on_threshold = on_threshold
        self.off_threshold = off_threshold
        self.polarity = 1
        self.floor_noise = floor_dev_mad

    def signal(self, reading):
        return reading

    def contrast(self):
        return abs(self.target_level - self.floor_level)

    def describe(self):
        return ("floor_dev med={0:.3f} mad={1:.3f} on>{2:.3f} off<{3:.3f} (anomaly space)".format(
            self.floor_level, self.floor_noise, self.on_threshold, self.off_threshold))


def derive_thresholds(model, floor_samples):
    """Self-calibrating thresholds in deviation space, tied to the 6-SD (8.90-MAD) rule.

    The threshold is measured on the floor's OWN deviation distribution (its distance to its own
    bands), so it is set entirely on the day. Unlike calibration.py there is NO calibrate-time
    contrast gate -- with no target sample we cannot check separation up front, so the bench
    recording in the research doc is mandatory, not optional.
    """
    devs = []
    for s in floor_samples:
        d = model.deviation(s)
        if d is not None:
            devs.append(d)
    if not devs:
        raise calibration.CalibrationError("no usable floor deviations to set a threshold")
    med = calibration.median(devs)
    mad = calibration.median_absolute_deviation(devs)
    if mad < MIN_DEV_MAD:
        mad = MIN_DEV_MAD
    excess = config.MIN_SNR_MAD * mad
    on_threshold = med + excess
    off_threshold = med + (1.0 - config.HYSTERESIS_FRACTION) * excess   # whole hysteresis band below on
    return FloorDeviationCal(med, mad, on_threshold, off_threshold)
