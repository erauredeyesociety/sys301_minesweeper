"""Decide which telemetry samples are worth logging -- report by exception.

Logging every tick fills /flash and buries the run: a 45 s run at 100 Hz is 4500 rows, and almost
all of them say "nothing changed". This gate keeps only the SIGNIFICANT samples --

  - a monitored channel moved past its DEADBAND (the robot turned, a colour shifted), or
  - a discrete EVENT fired (a detection, a fault, a phase change), forced by the caller, or
  - a HEARTBEAT interval elapsed, so even a quiet stretch is bounded and provably still alive.

Everything else is dropped and counted. That is the significant-event stream the mapping / SLAM
math wants (operator, 2026-09-03: "telemetry might be too large ... filter to only log significant
events"), and it shrinks a log by the ratio summary() reports without losing a single transition.

PURE -- no hub imports, no I/O. The caller reads the sensors and owns the file; this module only
answers "log this one?" and says WHY. Written to the MicroPython subset: no f-strings, no typing.
"""


class EventFilter(object):
    """Report-by-exception gate. Feed it every tick; it tells you which ticks to write.

    deadbands maps a channel name to the smallest change that counts as significant IN THAT
    CHANNEL'S OWN UNITS -- e.g. {"yaw_ddeg": 30, "fwd_mm": 20, "reflC_pct": 8}. A channel absent
    from deadbands is never a trigger on its own (but is still written when some other trigger
    fires, because the caller logs the whole row). heartbeat_ms=0 disables the heartbeat.
    """

    def __init__(self, deadbands, heartbeat_ms=2000):
        self.deadbands = dict(deadbands)
        self.heartbeat_ms = heartbeat_ms
        self._last_logged = {}     # channel -> its value at the last emitted row (the live baseline)
        self._last_t = None        # t_ms of the last emitted row
        self.kept = 0
        self.dropped = 0

    def consider(self, t_ms, values, event=None):
        """Return a reason string if this sample should be logged, else None.

        values: a dict of the monitored channels this tick. A channel that is None or absent is
                skipped for the deadband test (a failed read is not a change).
        event:  a non-empty string that FORCES a log and becomes part of the reason -- for things
                that are not a smooth channel at all (a mine detected, a stall, "countdown->run").

        When it returns a reason, the current values become the new baseline; a returned None
        leaves the baseline untouched, so many sub-deadband ticks in a row still compare against
        the last row actually written, not against each other (no slow drift slips through).
        """
        reasons = []
        if event:
            reasons.append(event)
        if self._last_t is None:
            reasons.append("first")
        elif self.heartbeat_ms and (t_ms - self._last_t) >= self.heartbeat_ms:
            reasons.append("heartbeat")
        for name in self.deadbands:
            v = values.get(name)
            if v is None:
                continue
            prev = self._last_logged.get(name)
            if prev is None or abs(v - prev) >= self.deadbands[name]:
                reasons.append(name)

        if reasons:
            self._commit(t_ms, values)
            return "+".join(reasons)
        self.dropped += 1
        return None

    def _commit(self, t_ms, values):
        self._last_t = t_ms
        for name in self.deadbands:
            v = values.get(name)
            if v is not None:
                self._last_logged[name] = v
        self.kept += 1

    def summary(self):
        """(kept, dropped, kept_fraction) -- what the filter did, for the log trailer and the report."""
        total = self.kept + self.dropped
        frac = (float(self.kept) / total) if total else 0.0
        return (self.kept, self.dropped, frac)
