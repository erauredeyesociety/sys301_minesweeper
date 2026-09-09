#!/usr/bin/env python3
"""Shared, offline primitives for reading one of this robot's run logs.

    import runlog
    run = runlog.load(path)          # -> Run(meta, header, rows, end, schema)
    runlog.series(run.rows, "reflC_pct")

WHY THIS EXISTS. `analyse-run.py` (one run, deep) and `compare-runs.py` (many runs, wide) both need
the same decoder, the same MEASURED threshold table and the same statistics. Without this module
there would be two copies of the mine rule and the tape rule, and a threshold that disagrees between
two of our own tools is worse than no tool. Pattern borrowed from the operator's drone project
(`~/tmp/tmp_drone/scripts/loglib.py`), which exists for exactly this reason.

Nothing here opens a serial port, imports a hub module, or touches `/dev/spike`. Everything is
arithmetic over a CSV already on disk.

KNOWN DUPLICATION, stated rather than hidden: the detection thresholds below are transcribed from
`examples/drive_to_tape.py` and `examples/find_note.py`, which are hub programs and cannot import
host code. They agree today; nothing enforces that. If a hub program's threshold changes, change it
here too, or this tool will report crossings the robot did not make.
"""

import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(ROOT, "tmp", "telemetry")

# ── THE EDITABLE TABLES ────────────────────────────────────────────────────────────────────────
# Everything a reader might want to change lives here, in plain lists, and nowhere else.

# The 24-column schema every mission program writes (motor_poc, drive_to_tape, find_note,
# follow_tape, find_corner all share this exact HEADER string), so one decoder serves all of them.
STD24 = ("seq,t_ms,phase,relA_deg,relB_deg,velL,velR,statusL,statusR,yaw_ddeg,accx_mg,accy_mg,"
         "accz_mg,reflC_pct,rC,gC,bC,iC,reflD_pct,rD,gD,bD,iD,reason")

# Older captures on disk use different headers. Named so a report says which one it got instead of
# silently reporting nothing.
SCHEMAS = (
    (STD24, "STD24", "the 24-column mission schema"),
    ("seq,t_ms,relA_deg,velA_dps", "AB-FUSION", "the 2026-09-03 motor+IMU+colour fusion capture"),
    ("seq,t_ms,absA_deg,relA_deg", "VERBOSE-V1", "the 2026-09-03 30-column verbose motor capture"),
    ("seq,t_ms,yaw_ddeg,pitch_ddeg", "IMU-ONLY", "the 2026-09-03 standalone IMU+colour capture"),
)

# Port map — docs/hardware/port-map.md, sides confirmed on hardware 2026-09-08.
PORT_SIDE = {"C": "RIGHT", "D": "LEFT"}

# Drive geometry. MEASURED 2026-09-03 (wheel) / 2026-09-01 (encoder counts, mirror signs).
WHEEL_DIAMETER_MM = 63.5
WHEEL_CIRCUM_MM = 199.49       # pi * 63.5, the figure the hub programs themselves use
COUNTS_PER_REV = 360.0
LEFT_FWD_SIGN = -1             # forward = A negative, B positive (the measured mirror)
RIGHT_FWD_SIGN = +1

# Detection rules the hub programs actually apply. (label, signal, comparison, threshold, source)
RULES = (
    ("MINE (brightness)", "reflection", ">=", 30.0,
     "examples/find_note.py NOTE_REFL_MIN — carpet+tape max 9, yellow min 51"),
    ("BLUE TAPE (blue fraction)", "blue_frac", ">=", 0.44,
     "examples/drive_to_tape.py BLUE_FRAC_MIN — carpet max 0.408, tape min 0.476"),
)

# Reported alongside a mine detection, never as a trip: which mine colour it was.
PINK_RED_FRAC_MIN = 0.41       # examples/find_note.py — yellow 0.355, pink 0.464

# MEASURED bands, docs/findings/colour-survey-and-first-detection-2026-09-08.md § 3.
# (low, high, label). Order matters: first match wins.
REFLECTANCE_BANDS = (
    (0.0, 9.0, "carpet or blue tape (they overlap here)"),
    (9.1, 20.0, "between bands — off the floor, in shadow, or mid-crossing"),
    (20.1, 50.0, "approaching a note, or a note at an unusual height"),
    (50.1, 96.0, "yellow note"),
    (96.1, 100.0, "pink note, or a saturated sensor"),
)

# Any rgbi channel at or above this carries no colour information — the sensor's own LED has pinned
# it and the ratios collapse to 33/33/33. MEASURED 2026-09-08.
SATURATED_AT = 1000

# The OTHER end of the same problem, and the same floor scripts/analyse-survey.py already applies:
# with nothing under the sensor a row reads r=1,g=0,b=0, whose "blue fraction" is a perfectly
# confident 0.000 and whose red fraction is 1.000 — pure quantisation garbage that sails past a 0.44
# threshold. Real surfaces MEASURED 263-1715 total (colour-survey-and-first-detection-2026-09-08 § 3),
# so 30 is a safe floor. Below it a fraction is None, not a number.
MIN_CHROMA_TOTAL = 30

# motor.status() — MEASURED, docs/findings/hub-api-surface-2026-09-01.md § 1 (KU-M15).
# 3 is ambiguous by design: CONTINUE and CANCELLED share the value.
STATUS_NAMES = {0: "READY", 1: "RUNNING", 2: "STALLED", 3: "CONTINUE/CANCELLED (ambiguous)",
                5: "DISCONNECTED (empty port)"}

# `#end reason=` values, in plain words. An unknown reason is printed raw, never guessed at.
REASONS = {
    "complete": "the program ran its whole planned sequence and ended by design",
    "TAPE_DETECTED": "the blue-fraction rule tripped — the robot stopped ON the boundary tape",
    "TAPE_ENDED": "the tape the robot was following ran out under both sensors",
    "NOTE_FOUND": "the brightness rule tripped — a mine was detected while moving",
    "time_cap": "the hard time cap expired before anything was detected",
    "distance_cap": "the hard distance cap expired before anything was detected",
    "STOP_button": "a human pressed the hub button to abort the run",
    "LOST_EDGE": "the edge being tracked was lost and could not be reacquired",
}


# ── loading ────────────────────────────────────────────────────────────────────────────────────

class Run(object):
    """One downloaded log. Attributes only; no behaviour, so nothing here can hide a decision."""

    def __init__(self, path):
        self.path = path
        self.meta = []          # '#' lines before the data
        self.header = []
        self.rows = []          # list of dict, header name -> raw string
        self.end = None         # dict of the '#end' key=value pairs, or None if absent
        self.end_raw = None
        self.schema = "UNKNOWN"
        self.schema_note = "header matches no schema this tool knows"
        self.malformed = 0      # data lines whose field count did not match the header

    @property
    def prefix(self):
        """The program that wrote it: '20260908T112501-followtape-0000360435.csv' -> 'followtape'."""
        m = re.match(r"^\d{8}T\d{6}-(.+?)-(\d+)\.csv$", os.path.basename(self.path))
        return m.group(1) if m else os.path.basename(self.path).rsplit(".", 1)[0]

    @property
    def hub_stamp(self):
        """The hub-side name stamp — THE RUN'S IDENTITY. The leading host timestamp is only when the
        file was DOWNLOADED, and the same run re-downloaded lands under a new one."""
        m = re.match(r"^\d{8}T\d{6}-.+?-(\d+)\.csv$", os.path.basename(self.path))
        return m.group(1) if m else None


def load(path):
    run = Run(path)
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            if line.startswith("#end"):
                run.end_raw = line
                run.end = dict(re.findall(r"(\w+)=(\S+)", line))
                continue
            if line.startswith("#"):
                run.meta.append(line)
                continue
            fields = line.split(",")
            if not run.header:
                run.header = fields
                joined = ",".join(fields)
                for probe, name, note in SCHEMAS:
                    if joined.startswith(probe):
                        run.schema, run.schema_note = name, note
                        break
                continue
            if len(fields) != len(run.header):
                run.malformed += 1
                continue
            run.rows.append(dict(zip(run.header, fields)))
    return run


def newest(directory=TMP_DIR):
    """The newest RUN, which is not the same thing as the newest file.

    `download.py --all` re-fetches every log the hub still holds, so after one download the newest
    file on disk is whichever old run sorted last — not the run just performed. So: group files by
    hub-side stamp, take each group's EARLIEST download time as when that run first appeared, and
    return the group that appeared most recently. Returns (path, why) so the report can say which
    rule picked the file rather than leaving the reader to guess.
    """
    files = glob.glob(os.path.join(directory, "*.csv"))
    if not files:
        return None, ""
    groups = {}
    for path in files:
        key = re.sub(r"^\d{8}T\d{6}-", "", os.path.basename(path))
        groups.setdefault(key, []).append(path)
    first_seen = {k: min(os.path.getmtime(p) for p in v) for k, v in groups.items()}
    key = max(first_seen, key=lambda k: first_seen[k])
    pick = sorted(groups[key])[0]
    if len(groups[key]) == 1:
        return pick, "newest run in %s" % os.path.relpath(directory, ROOT)
    return pick, ("newest run in %s — first of %d downloads of it"
                  % (os.path.relpath(directory, ROOT), len(groups[key])))


def siblings(run, directory=TMP_DIR):
    """Other files in the directory that are the SAME hub-side run, re-downloaded."""
    if not run.hub_stamp:
        return []
    pat = os.path.join(directory, "*-%s-%s.csv" % (run.prefix, run.hub_stamp))
    return [p for p in sorted(glob.glob(pat)) if os.path.abspath(p) != os.path.abspath(run.path)]


# ── column access ──────────────────────────────────────────────────────────────────────────────

def num(row, name):
    """One numeric cell, or None. An empty cell means the hub's read failed — never 0."""
    v = row.get(name)
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def series(rows, name):
    """(values, missing_count). Values are in row order with unreadable cells DROPPED, so the count
    of what was thrown away travels with the data instead of quietly vanishing."""
    vals, missing = [], 0
    if not rows or name not in rows[0]:
        return None, 0                      # column absent from this schema: distinct from empty
    for r in rows:
        v = num(r, name)
        if v is None:
            missing += 1
        else:
            vals.append(v)
    return vals, missing


def paired(rows, name):
    """[(row_index, value)] for a column, so a crossing can be traced back to its row."""
    out = []
    if not rows or name not in rows[0]:
        return out
    for i, r in enumerate(rows):
        v = num(r, name)
        if v is not None:
            out.append((i, v))
    return out


def frac(row, port, channel):
    """One chromaticity fraction, e.g. blue = b/(r+g+b).

    None when any channel is unreadable, when the row is saturated, or when the total is below
    MIN_CHROMA_TOTAL — all three are cases where a fraction can still be computed and means nothing.
    """
    r = num(row, "r%s" % port)
    g = num(row, "g%s" % port)
    b = num(row, "b%s" % port)
    if None in (r, g, b):
        return None
    total = r + g + b
    if total < MIN_CHROMA_TOTAL or saturated(row, port):
        return None
    return {"r": r, "g": g, "b": b}[channel] / total


def chroma_rejected(rows, port):
    """(too_dim, saturated) — rows whose r/g/b read fine but whose chromaticity was discarded."""
    dim = sat = 0
    for row in rows:
        vals = [num(row, "%s%s" % (ch, port)) for ch in ("r", "g", "b")]
        if None in vals:
            continue
        if saturated(row, port):
            sat += 1
        elif sum(vals) < MIN_CHROMA_TOTAL:
            dim += 1
    return dim, sat


def signal(rows, port, kind):
    """[(row_index, value)] for one named signal on one port. The single place a rule name in
    RULES is turned into numbers, so analyse-run and compare-runs cannot disagree about it."""
    if kind == "reflection":
        return paired(rows, "refl%s_pct" % port)
    out = []
    channel = {"blue_frac": "b", "red_frac": "r"}[kind]
    for i, r in enumerate(rows):
        v = frac(r, port, channel)
        if v is not None:
            out.append((i, v))
    return out


def saturated(row, port):
    """True if any rgbi channel on this port has pinned. A pinned sample carries no colour."""
    for ch in ("r", "g", "b", "i"):
        v = num(row, "%s%s" % (ch, port))
        if v is not None and v >= SATURATED_AT:
            return True
    return False


# ── statistics ─────────────────────────────────────────────────────────────────────────────────

def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def stats(vals):
    if not vals:
        return None
    s = sorted(vals)
    return {"n": len(s), "min": s[0], "max": s[-1], "mean": sum(s) / len(s),
            "p50": pct(s, 50), "p95": pct(s, 95)}


def unwrap(degrees):
    """Undo the +-180 wrap so a heading total is the angle actually turned, not the residual.
    Yaw wrapping is a MEASURED property of this IMU (CLAUDE.md, Hard facts)."""
    out, offset = [], 0.0
    for i, v in enumerate(degrees):
        if i:
            step = v - degrees[i - 1]
            if step > 180.0:
                offset -= 360.0
            elif step < -180.0:
                offset += 360.0
        out.append(v + offset)
    return out


def crossing(pairs, threshold, above=True):
    """How a signal behaved against a threshold — including when it never got there.

    Returns a dict: peak (the most extreme value in the trip direction), margin (peak - threshold,
    signed so positive always means 'tripped'), first (row index and value of the first crossing),
    and hits (how many samples were on the trip side). `first` is None when it never crossed, and
    `margin` then says by how much it fell short. That gap is the whole point: a run that peaked at
    0.408 against a 0.44 threshold is a different fact from one that never came close.
    """
    if not pairs:
        return None
    vals = [v for _, v in pairs]
    peak = max(vals) if above else min(vals)
    margin = (peak - threshold) if above else (threshold - peak)
    hits = [(i, v) for i, v in pairs if (v >= threshold if above else v <= threshold)]
    return {"peak": peak, "margin": margin, "hits": len(hits),
            "first": hits[0] if hits else None, "n": len(pairs)}


def band(value):
    for lo, hi, label in REFLECTANCE_BANDS:
        if lo <= value <= hi:
            return label
    return "outside every measured band"


# ── display ────────────────────────────────────────────────────────────────────────────────────

BLOCKS = "▁▂▃▄▅▆▇█"


def spark(vals, width=60):
    """A one-line trace, scaled to its own min..max. Terminal only — docs get mermaid, never this."""
    if not vals:
        return "(no data)"
    lo, hi = min(vals), max(vals)
    if len(vals) > width:                       # decimate by bucket max, so a spike survives
        step = len(vals) / float(width)
        picked = []
        for k in range(width):
            chunk = vals[int(k * step):max(int((k + 1) * step), int(k * step) + 1)]
            picked.append(max(chunk) if chunk else lo)
        vals = picked
    if hi - lo < 1e-9:
        return BLOCKS[0] * len(vals)
    return "".join(BLOCKS[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in vals)


def fwd_mm(deg):
    return deg / COUNTS_PER_REV * WHEEL_CIRCUM_MM


if __name__ == "__main__":
    import sys
    sys.exit("runlog.py is a MODULE, not a tool. Run: ./scripts/analyse-run.py [FILE]")
