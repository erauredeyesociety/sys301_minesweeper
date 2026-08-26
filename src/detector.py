"""Turn a noisy stream of reflectance readings into a count of discrete targets.

The failure modes this exists to prevent, all of them real:
  - one note counted twice, because the signal dipped in the middle of it
  - two adjacent notes counted as one
  - sensor noise or a floor seam counted as a note
  - a note missed because the signal only grazed the threshold

The mechanism is a four-state machine with Schmitt-trigger hysteresis and a minimum dwell:
a state change must persist for MIN_DWELL_SAMPLES before it is believed. MAYBE_OFF is the
important state -- it absorbs a brief dropout inside a target instead of splitting the count.

Counting happens on the FALLING edge, once the event's width is known, so a too-narrow blip
(noise) or a too-wide plateau (a seam, or two merged notes) can be rejected with a reason.
"""

import config

OFF = "off"
MAYBE_ON = "maybe_on"
ON = "on"
MAYBE_OFF = "maybe_off"

# Why an event was rejected -- reported, never silently dropped.
REJECT_TOO_NARROW = "too_narrow"
REJECT_TOO_WIDE = "too_wide"


class Event(object):
    """One accepted or rejected target crossing."""

    def __init__(self, start_index, end_index, peak_signal, accepted, reason=None):
        self.start_index = start_index
        self.end_index = end_index
        self.peak_signal = peak_signal
        self.accepted = accepted
        self.reason = reason

    def width(self):
        return self.end_index - self.start_index

    def describe(self):
        return "event[{0}..{1}] width={2} peak={3:.1f} {4}{5}".format(
            self.start_index, self.end_index, self.width(), self.peak_signal,
            "ACCEPTED" if self.accepted else "REJECTED",
            "" if self.reason is None else " (" + self.reason + ")")


class EdgeCounter(object):
    """Feeds on readings one at a time; emits an Event when a crossing completes."""

    def __init__(self, calibration, min_dwell=None, min_width=None, max_width=None):
        self.cal = calibration
        self.min_dwell = config.MIN_DWELL_SAMPLES if min_dwell is None else min_dwell
        self.min_width = config.MIN_EVENT_SAMPLES if min_width is None else min_width
        self.max_width = config.MAX_EVENT_SAMPLES if max_width is None else max_width

        self.state = OFF
        self.index = -1
        self.count = 0
        self.events = []

        self._pending = 0          # samples the candidate state has persisted
        self._start_index = None   # index where the current ON run began
        self._peak = None

    def update(self, reading):
        """Consume one raw reading. Returns an Event when one completes, else None."""
        self.index += 1
        signal = self.cal.signal(reading)
        above = signal > self.cal.on_threshold
        below = signal < self.cal.off_threshold

        if self.state == OFF:
            if above:
                self._pending += 1
                if self._pending >= self.min_dwell:
                    self.state = ON
                    self._start_index = self.index - (self._pending - 1)
                    self._peak = signal
                    self._pending = 0
                else:
                    self.state = MAYBE_ON
            else:
                self._pending = 0

        elif self.state == MAYBE_ON:
            if above:
                self._pending += 1
                if self._pending >= self.min_dwell:
                    self.state = ON
                    self._start_index = self.index - (self._pending - 1)
                    self._peak = signal
                    self._pending = 0
            else:
                # Never confirmed -- it was noise. Discard without counting.
                self.state = OFF
                self._pending = 0

        elif self.state == ON:
            if signal > self._peak:
                self._peak = signal
            if below:
                self._pending = 1
                self.state = MAYBE_OFF
            else:
                self._pending = 0

        elif self.state == MAYBE_OFF:
            if signal > self._peak:
                self._peak = signal
            if below:
                self._pending += 1
                if self._pending >= self.min_dwell:
                    # Confirmed falling edge. The target ended when the dip began.
                    end_index = self.index - self._pending
                    event = self._close(end_index)
                    self.state = OFF
                    self._pending = 0
                    return event
            else:
                # A dropout INSIDE the target -- absorb it, do not split the count.
                self.state = ON
                self._pending = 0

        return None

    def finish(self):
        """Close an event still open at end of stream. Returns an Event or None."""
        if self.state in (ON, MAYBE_OFF):
            event = self._close(self.index)
            self.state = OFF
            self._pending = 0
            return event
        self.state = OFF
        self._pending = 0
        return None

    def _close(self, end_index):
        width = end_index - self._start_index + 1
        if width < self.min_width:
            event = Event(self._start_index, end_index, self._peak, False, REJECT_TOO_NARROW)
        elif width > self.max_width:
            event = Event(self._start_index, end_index, self._peak, False, REJECT_TOO_WIDE)
        else:
            event = Event(self._start_index, end_index, self._peak, True)
            self.count += 1
        self.events.append(event)
        self._start_index = None
        self._peak = None
        return event


def count_stream(calibration, readings, **kwargs):
    """Convenience: run a whole sequence through a counter and return (count, events)."""
    counter = EdgeCounter(calibration, **kwargs)
    for reading in readings:
        counter.update(reading)
    counter.finish()
    return counter.count, counter.events
