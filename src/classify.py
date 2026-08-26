"""Tell one note colour from another, from raw (r, g, b, i) colour-sensor samples.

The method is docs/research/color-discrimination.md section 4.3 (chromaticity centroids,
nearest-centroid match, three rejection gates) and section 4.4 (the pairwise separability
gate). It is implemented here, not re-derived.

Two consequences of that research are load-bearing in the code below:

  - Everything happens in chromaticity, r/(r+g+b) and g/(r+g+b). The rgbi() scale is
    undocumented on SPIKE 3, and brightness moves with sensor height, battery charge and the
    room regardless. Chromaticity is scale-free, so nothing here depends on the absolute
    numbers the sensor happens to return.
  - A reading that cannot be placed confidently comes back as None with a reason, never as the
    nearest class. Forcing the guess is how a run reports four pinks when two of them were
    orange -- and a wrong colour stated confidently is worse than an honest UNKNOWN.

NOTHING HERE HAS BEEN MEASURED. The hub has never been connected and no sample has ever been
taken, so the constants below are shapes, not tunings.
"""

import math

import calibration
import result

# [ASSUMED] Chosen for shape. MUST BE MEASURED by replaying recorded runs against known notes
# -- color-discrimination.md section 8. Record the value alongside the counts it produced.
K_FAR = 3.0              # reject when the nearest class is further than this many sigmas
K_MARGIN = 0.80          # reject when d_best / d_second exceeds this: too close to call
SEPARATION_SIGMAS = 3.0  # section 4.4: centroids must be this many mean-sigmas apart

# A cluster tighter than this would make the sigma-normalised distance divide by ~zero.
MIN_SIGMA = 1e-4


def _features(sample):
    """(r, g, b, i) -> (r_n, g_n, total), or None when there is no usable signal.

    None rather than zeros: a sample summing to zero is a black reading with no chromaticity
    at all, and (0.0, 0.0) is a legitimate place on the chromaticity plane that would drag a
    centroid. It is the absence of a reading, so it is dropped, not defaulted.

    sample itself may be None: sensors.read_rgb() returns None on an unreadable or unsupported
    port, so a burst collected straight off it will contain them. A failed read is one fewer
    point, not a crash halfway through a run with no test suite to have caught it.
    """
    if sample is None:
        return None
    total = sample[0] + sample[1] + sample[2]
    if total <= 0:
        return None
    return (float(sample[0]) / total, float(sample[1]) / total, float(total))


def _dist(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return math.sqrt(dx * dx + dy * dy)


class ColorClass(object):
    """One calibrated colour: where it sits in chromaticity, and how far it scatters.

    n is the count of USABLE samples that survived _features, which is the only place that
    number still exists once the raw bursts are gone -- it feeds the section 4.4 sample-count
    check, which the caller runs because only the caller knows how many it expected.
    """

    def __init__(self, name, cx, cy, sigma, total_median, n):
        self.name = name
        self.cx = cx
        self.cy = cy
        self.sigma = sigma
        self.total_median = total_median
        self.n = n


def build_classes(samples_by_name):
    """{name: [(r, g, b, i), ...]} -> {name: ColorClass}.

    One flat list per class: the placements of section 4.2 exist to widen the spread the
    operator captures, not to structure the arithmetic, so the caller concatenates them.

    Medians and MAD throughout, never means and stdev -- one flicker beat or stray highlight
    must not be able to move a centroid.
    """
    classes = {}
    for name in samples_by_name:
        points = []
        for sample in samples_by_name[name]:
            f = _features(sample)
            if f is not None:
                points.append(f)
        if not points:
            raise calibration.CalibrationError(
                "no usable samples for class '{0}': every reading was unreadable "
                "or summed to zero".format(name))
        cx = calibration.median([p[0] for p in points])
        cy = calibration.median([p[1] for p in points])
        dists = [_dist(p[0], p[1], cx, cy) for p in points]
        sigma = 1.4826 * calibration.median_absolute_deviation(dists)
        if sigma < MIN_SIGMA:
            sigma = MIN_SIGMA
        classes[name] = ColorClass(name, cx, cy, sigma,
                                   calibration.median([p[2] for p in points]), len(points))
    return classes


def classify(classes, rgb_samples):
    """Every raw sample from one detection event -> (name or None, reason).

    reason is None when a name is returned.

    The event is reduced to its MEDIAN chromaticity before matching. The samples at each end of
    an event straddle the note edge and mix note with floor; a median discards them, where a
    mean would blend them into the answer.
    """
    if not classes:
        return (None, result.REASON_NO_MATCH)

    points = []
    for sample in rgb_samples:
        f = _features(sample)
        if f is not None:
            points.append(f)
    if not points:
        return (None, result.REASON_LOW_SIGNAL)

    # S_MIN, section 4.3: half the dimmest thing we calibrated. Anything below that is not a
    # surface we have ever seen -- an empty port, a lifted sensor, or nothing there at all.
    if calibration.median([p[2] for p in points]) < 0.5 * min(
            [classes[name].total_median for name in classes]):
        return (None, result.REASON_LOW_SIGNAL)

    x = calibration.median([p[0] for p in points])
    y = calibration.median([p[1] for p in points])
    scored = sorted([(_dist(x, y, c.cx, c.cy) / c.sigma, c.name) for c in classes.values()])

    d_best, best = scored[0]
    if d_best > K_FAR:
        return (None, result.REASON_NO_MATCH)
    if len(scored) > 1:
        d_second = scored[1][0]
        # d_second == 0 means the point sits on two centroids at once: maximally ambiguous.
        if d_second <= 0.0 or d_best / d_second > K_MARGIN:
            return (None, result.REASON_AMBIGUOUS)
    return (best, None)


def separability_report(classes):
    """Which calibrated classes cannot be told apart today. Empty list means the gate passed.

    Section 4.4: a pair is separable when its centroids are at least SEPARATION_SIGMAS times
    their mean spread apart. This runs at DERIVE and can fail calibration, so each entry
    carries what the operator needs to act at 09:00 on Demo Day rather than a bare failure:

        (name_a, name_b, distance, required)

    both names, how far apart the two colours actually are in chromaticity, and how far apart
    they needed to be. The shortfall is required - distance.
    """
    names = sorted(classes)
    failures = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = classes[names[i]]
            b = classes[names[j]]
            distance = _dist(a.cx, a.cy, b.cx, b.cy)
            required = SEPARATION_SIGMAS * (a.sigma + b.sigma) / 2.0
            if distance < required:
                failures.append((names[i], names[j], distance, required))
    return failures
