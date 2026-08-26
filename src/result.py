"""What the robot reports at the end of a run.

The honest-instrumentation rule applies hardest here: a reading the classifier could not place
is reported as UNKNOWN with a reason, never quietly dropped and never forced into whichever
class happens to be nearest. "We found 7 and could not classify 2" is a true answer;
"we found 9" when two were guesses is not.

The invariant detected == classified + unknown is asserted, not assumed -- if it is ever false
the accounting is broken and we want to know on the bench, not on Demo Day.
"""

import config

UNKNOWN = "unknown"

# Why a detection could not be classified.
REASON_LOW_SIGNAL = "low_signal"       # too dim / too few samples to trust
REASON_NO_MATCH = "no_match"           # far from every calibrated colour
REASON_AMBIGUOUS = "ambiguous"         # two classes too close to call


class ResultAccountingError(Exception):
    """The counts do not add up. A bug, not a bad run."""


# How the run ended. A count without one of these is not a result -- "7" from a run that covered a
# third of the arena and "7" from a completed sweep mean different things, and only one of them is
# an answer. Reporting the bare number was the sharpest honesty gap in this module.
STATUS_COMPLETE = "complete"          # every planned lane swept
STATUS_TIMEBOX = "timebox"            # stopped on the clock, mid-sweep
STATUS_ABORTED = "aborted"            # operator stopped it
STATUS_DEGRADED = "degraded"          # finished, but a sensor or the pose was not trusted throughout
STATUS_FAULT = "fault"                # a device failed
STATUS_UNKNOWN = "unknown"            # nobody said -- the honest default

# Page glyphs, named here and DRAWN in hub_ui.show_glyph(). This module stays pure: it decides
# what each page means, never what pixels it is.
#
# Every name below MUST be a key of hub_ui._GLYPHS: show_glyph() raises KeyError on an unknown
# name, deliberately, and a KeyError on report page 2 ends the run with a dark matrix -- which is
# the one failure commitment 5 exists to prevent. Checked by eye against hub_ui.py, not by code:
# result.py stays pure and cannot import sensors to assert it.
GLYPH_TOTAL = "border"
GLYPH_UNKNOWN = "checker"
GLYPH_REJECTED = "bars"

# One glyph per class page, in config.CLASSES order; class 1 is the solid block (spec page table).
# hub_ui._GLYPHS has exactly one class glyph, so a second class needs one ADDED THERE and listed
# here. Indexing raises IndexError on the host the moment config.CLASSES outgrows this tuple --
# loud on the bench, which is where that must surface, not mid-report on Demo Day.
CLASS_GLYPHS = ("block",)

# Status glyph per terminal status. A watcher across the room has to tell "finished" from "ran out
# of time" from "broke" without reading a word, so the four shapes are deliberately unlike.
STATUS_GLYPHS = {
    STATUS_COMPLETE: "border",
    STATUS_TIMEBOX: "hourglass",
    STATUS_ABORTED: "diagonal",
    STATUS_DEGRADED: "diagonal",
    STATUS_UNKNOWN: "diagonal",
    STATUS_FAULT: "x",
}


class MissionResult(object):
    def __init__(self):
        self.by_color = {}        # colour name -> count
        self.unknown_by_reason = {}
        self.rejected = 0         # events the detector refused (noise, merged plateau)
        self.detected = 0         # events the detector ACCEPTED
        # Run context. Defaults are deliberately "we do not know", not "it went fine".
        self.status = STATUS_UNKNOWN
        self.status_detail = None
        self.lanes_completed = 0
        self.lanes_planned = 0
        self.duration_s = None
        self.none_samples = 0     # readings the sensor could not give us

    def set_status(self, status, detail=None):
        """Record how the run ended. Call this on EVERY exit path, including the bad ones."""
        self.status = status
        self.status_detail = detail

    def coverage_fraction(self):
        """Fraction of planned lanes actually swept. None when nobody set the plan."""
        if not self.lanes_planned:
            return None
        return float(self.lanes_completed) / float(self.lanes_planned)

    def is_trustworthy(self):
        """Is this count an answer, or just a number? Conservative on purpose.

        A count is only trustworthy if the sweep completed. Anything else -- truncated, aborted,
        faulted, or a run nobody labelled -- means the number understates reality by an unknown
        amount, and it must never be reported as though it were the total.
        """
        return self.status == STATUS_COMPLETE

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

    def display_pages(self):
        """The DONE report as data: a list of (glyph_name, number), in the order shown.

        The order IS the pass criterion for FR-4 (gap G-3) -- the Builder reads these numbers aloud
        to the instructor, and "which number was that?" is answered by the page's position, so the
        sequence has to be written down somewhere the Builder can countersign rather than living in
        the shape of the display loop.

        One page per class regardless of count, because the beep count before each page is its page
        number: a class page that vanished when its count was zero would renumber every page after
        it, and the Builder would be counting beeps against a cycle that changed shape between runs.

        Raises ResultAccountingError. This is the one place the invariant is checked before the
        first number is shown, so REPORT has exactly one thing to catch (degraded mode C3).
        """
        self.check()
        pages = [(GLYPH_TOTAL, self.detected)]
        i = 0
        for name in config.CLASSES:
            pages.append((CLASS_GLYPHS[i], self.by_color.get(name, 0)))
            i += 1
        pages.append((GLYPH_UNKNOWN, self.unknown_total()))
        pages.append((GLYPH_REJECTED, self.rejected))
        pages.append((STATUS_GLYPHS.get(self.status, "diagonal"), self.lanes_completed))
        return pages

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
        if self.none_samples:
            parts.append("unreadable={0}".format(self.none_samples))

        # The status leads, and a partial count says so IN the number line -- not in a footnote
        # somebody skims past.
        head = "total={0}".format(self.detected)
        if not self.is_trustworthy():
            head = "PARTIAL total>={0}".format(self.detected)
        parts.append("status={0}".format(self.status))
        if self.status_detail:
            parts.append("({0})".format(self.status_detail))
        if self.lanes_planned:
            frac = self.coverage_fraction()
            parts.append("lanes={0}/{1}({2}%)".format(
                self.lanes_completed, self.lanes_planned, int(frac * 100.0)))
        if self.duration_s is not None:
            parts.append("{0:.0f}s".format(self.duration_s))
        return head + " " + " ".join(parts)
