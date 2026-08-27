"""Format one run's telemetry as CSV lines. PURE -- no hub imports, no I/O, no transport.

WHY THIS IS NOT A "BLE HANDLER" -- the conclusion stands, the ORIGINAL REASON WAS WRONG.

    STRUCK 2026-08-27: this docstring used to say "`bluetooth`/`ble` do not appear in the hub's
    module list". They do. `help('modules')` on our own hub lists `bluetooth`, and it is the full
    standard MicroPython ubluetooth stack -- BLE, UUID, gap_advertise, gap_scan, gatts_*, gattc_*,
    irq. The old claim was drawn from an absence in a THIRD-PARTY module list and it is disproved.

The surviving reason is narrower and honest: API presence is not firmware permission. BLE() returns a
process-wide singleton, so a hub program calling it gets LEGO'S OWN stack, and .active(True) on top of
that risks a double-init under the C-level owner of the radio. It was deliberately never instantiated,
and docs/research/ble-bring-up.md now argues it MUST NOT be (KU-M18). It is also unnecessary: BLE from
the HOST side works and is proven -- docs/findings/ble-protocol-2026-08-27.md.

So telemetry still leaves the hub as ordinary `print()` output, which LEGO's firmware wraps in a
ConsoleNotification and sends over whichever link is attached. That choice is correct under BOTH
answers, which is why nothing here changes.

That is a gift, not a limitation:

    hub  ->  telemetry.record_line(...)  ->  print()  ->  [ USB serial | BLE ] -> laptop capture

**The hub side is identical under every transport**, so this module is worth writing now even though
no transport has been proven. Choosing BLE over USB later changes the laptop-side receiver and nothing
here. Deciding the format is also what tells the receiver what to expect.

Format and header fields: docs/plans/telemetry-over-bluetooth.md § 5.
Written to the MicroPython subset: no f-strings, no dataclasses, no typing.
"""

# v2 (2026-08-27): accx/accy/accz -> accx_mg/accy_mg/accz_mg, once the unit was measured.
# A receiver written against v1 must be told; that is the entire reason this string exists.
VERSION = "spike-telemetry v2"

# The unit is part of the column name so nobody has to guess millimetres from degrees.
#
# LOG EVERYTHING WE HAVE. The hub carries a SIX-axis IMU, not just yaw, and a field costs a few bytes
# a sample while a field nobody logged costs a whole re-run to recover. Class time is the scarce
# resource; bytes are not. Every column here is either free (already read for the control loop) or
# nearly so.
#
# Columns for hardware we do not own yet -- the distance sensor especially -- stay in the schema and
# write empty. A stable column order means one analysis script reads every run this project ever
# produces, instead of branching on which sensors were fitted that day.
COLUMNS = (
    "seq", "t_ms",
    # drive
    "encL_deg", "encR_deg", "cmdL_pct", "cmdR_pct",
    # IMU -- all six axes. yaw steers; the rest diagnose.
    # ddeg CONFIRMED and mg MEASURED on our hub 2026-08-27, derived from gravity rather than from a
    # datasheet: |a| = 989.3 at rest, so acceleration() is milli-g at ~989 per g; true tilt 0.705 deg
    # against a reported 6.7 gives ratio 9.53, so tilt_angles() is decidegrees.
    # docs/findings/imu-characterisation-2026-08-27.md
    # accx/accy/accz were RENAMED to *_mg on 2026-08-27 -- they broke this module's own rule above
    # while the unit was unknown. Renaming a column is a WIRE FORMAT change, so VERSION went to v2.
    "yaw_ddeg", "pitch_ddeg", "roll_ddeg", "accx_mg", "accy_mg", "accz_mg",
    # sensing
    "reflection_pct", "r", "g", "b", "distance_mm",
    # what the logic believed at that instant
    "state", "lane", "count", "det_state",
)

# What a field carries when the sensor could not be read. NOT zero -- zero is a measurement.
MISSING = ""


def header_lines(**context):
    """The `#` preamble. Everything needed to compare this run against another one.

    A run whose conditions were not recorded cannot be compared, and comparison is the whole point
    of logging. Unknown values are written as `?` rather than omitted, so a reader can tell
    "nobody recorded this" from "this field does not exist".
    """
    lines = ["#" + VERSION]
    for key in sorted(context):
        value = context[key]
        lines.append("#{0}={1}".format(key, "?" if value is None else value))
    lines.append("#" + ",".join(COLUMNS))
    return lines


def record_line(seq, t_ms, enc=None, cmd=None, tilt=None, accel=None,
                reflection=None, rgb=None, distance_mm=None,
                state=None, lane=None, count=None, det_state=None):
    """One sample as a CSV line, no trailing newline.

    Grouped arguments because that is the shape the readers return them in:
      enc    (left_deg, right_deg)       hub_motors.read_motor_degrees()
      cmd    (left_pct, right_pct)       what we last commanded -- the pair with `enc` is what
                                         reveals a stall: commanded hard, encoders not moving
      tilt   (yaw, pitch, roll) ddeg     hub_imu.read_tilt_ddeg()
      accel  (x, y, z)                   hub_imu.read_accel()
      rgb    (r, g, b) or (r, g, b, i)   hub_color.read_rgb()

    **Any argument, or the whole group, may be None** -- that is what the readers return when they
    cannot read, and a group that is None writes as empty fields rather than raising. Never
    substitute a default: a zero here is indistinguishable from a real reading of zero and would
    quietly corrupt every downstream statistic.
    """
    def part(group, n):
        if group is None:
            return [None] * n
        out = list(group[:n])
        while len(out) < n:
            out.append(None)
        return out

    fields = ([seq, t_ms]
              + part(enc, 2) + part(cmd, 2)
              + part(tilt, 3) + part(accel, 3)
              + [reflection] + part(rgb, 3) + [distance_mm]
              + [state, lane, count, det_state])
    return ",".join(MISSING if f is None else str(f) for f in fields)


def trailer_lines(seq_last, sum_seq, dropped=None):
    """Integrity trailer, so a truncated log is DETECTABLE rather than silently analysed.

    `sum_seq` is the running total of every `seq` emitted. The receiver recomputes
    `n*(n-1)/2` for `n = seq_last + 1` and compares: a mismatch means lines went missing, which a
    line count alone would not reveal if the loss happened to be at the end.
    """
    lines = ["#end seq_last={0} sum_seq={1}".format(seq_last, sum_seq)]
    if dropped is not None:
        lines.append("#dropped={0}".format(dropped))
    return lines


def expected_sum_seq(seq_last):
    """What `sum_seq` should be for a complete log ending at `seq_last`. Receiver-side check."""
    n = seq_last + 1
    return n * (n - 1) // 2


class Recorder(object):
    """Sequences and totals so the caller does not have to. Formatting only -- it never prints.

    The caller owns output, because on the hub that is `print()` and on the host it is a file, and
    this module refuses to care which.
    """

    def __init__(self):
        self.seq = 0
        self.sum_seq = 0
        self.dropped = 0

    def format(self, t_ms, **fields):
        """Sequence and format one sample. Pass whatever you have; the rest write empty."""
        line = record_line(self.seq, t_ms, **fields)
        self.sum_seq += self.seq
        self.seq += 1
        return line

    def note_dropped(self):
        """A sample we chose not to emit (rate limiting, a full buffer). Reported, never hidden."""
        self.dropped += 1

    def trailer(self):
        return trailer_lines(self.seq - 1, self.sum_seq,
                             self.dropped if self.dropped else None)
