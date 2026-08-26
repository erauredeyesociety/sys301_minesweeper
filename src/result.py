"""What the robot reports at the end of a run.

The honest-instrumentation rule applies hardest here: a reading the classifier could not place
is reported as UNKNOWN with a reason, never quietly dropped and never forced into whichever
class happens to be nearest. "We found 7 and could not classify 2" is a true answer;
"we found 9" when two were guesses is not.

The invariant detected == classified + unknown is asserted, not assumed -- if it is ever false
the accounting is broken and we want to know on the bench, not on Demo Day.
"""

UNKNOWN = "unknown"

# Why a detection could not be classified.
REASON_LOW_SIGNAL = "low_signal"       # too dim / too few samples to trust
REASON_NO_MATCH = "no_match"           # far from every calibrated colour
REASON_AMBIGUOUS = "ambiguous"         # two classes too close to call


class ResultAccountingError(Exception):
    """The counts do not add up. A bug, not a bad run."""


class MissionResult(object):
    def __init__(self):
        self.by_color = {}        # colour name -> count
        self.unknown_by_reason = {}
        self.rejected = 0         # events the detector refused (noise, merged plateau)
        self.detected = 0         # events the detector ACCEPTED

    def add_detection(self, color=None, reason=None):
        """Record one accepted detection, classified or not."""
        self.detected += 1
        if color is None:
            key = REASON_NO_MATCH if reason is None else reason
            self.unknown_by_reason[key] = self.unknown_by_reason.get(key, 0) + 1
        else:
            self.by_color[color] = self.by_color.get(color, 0) + 1

    def add_rejected(self):
        """Record one event the detector rejected. Not a detection; tracked for diagnosis."""
        self.rejected += 1

    def classified_total(self):
        return sum(self.by_color.values())

    def unknown_total(self):
        return sum(self.unknown_by_reason.values())

    def total(self):
        return self.detected

    def check(self):
        """Assert the accounting invariant. Raises rather than returning a wrong total."""
        if self.classified_total() + self.unknown_total() != self.detected:
            raise ResultAccountingError(
                "detected={0} but classified={1} + unknown={2}".format(
                    self.detected, self.classified_total(), self.unknown_total()))
        return True

    def describe(self):
        self.check()
        parts = []
        for color in sorted(self.by_color):
            parts.append("{0}={1}".format(color, self.by_color[color]))
        if self.unknown_total():
            reasons = ",".join(
                "{0}:{1}".format(r, self.unknown_by_reason[r])
                for r in sorted(self.unknown_by_reason))
            parts.append("unknown={0}({1})".format(self.unknown_total(), reasons))
        if self.rejected:
            parts.append("rejected={0}".format(self.rejected))
        return "total={0} ".format(self.detected) + " ".join(parts)
