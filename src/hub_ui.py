"""The hub's own I/O: 5x5 light matrix, speaker, buttons.

Part of the hub-facing layer. **Only `hub_*.py` modules may import the LEGO API** -- everything else in
`src/` stays pure and runs on the host ([ADR-0004], enforced by ./scripts/check-docs.py).

Split out of the old monolithic `sensors.py` on 2026-08-26: one file per device, so each stays small
enough to read in one sitting. That is load-bearing here -- this project carries no test suite and no
debugger, and smallness is what replaces both (test_methodology.md).

THE RULE: a reader returns None when it cannot read. NEVER 0, never a default, never a last-known
value. A caller that gets None knows it has no data; a caller that gets 0 does not.
"""
import hub_api
from hub_api import API, API_SPIKE2, API_SPIKE3

# --- Display: the 5x5 light matrix ------------------------------------------
# Brightness is 0-100 on both generations. rows[y][x], y = 0 at the top.
# UNVERIFIED: which physical edge is "top", and whether SPIKE 3's flat list of 25 runs row-major. That
# is a Stage 1 eyeball test with the hub on a desk, not something this file gets to assert.
#
# The hub submodules are imported INSIDE each call rather than in the detection block at the top: if a
# submodule name were wrong, importing it up there would drop the whole module to SIMULATED and every
# reader would silently start returning None on a healthy hub.

_GLYPHS = {
    # Exactly the glyphs docs/plans/mission-algorithm.md names -- stage vocabulary and report pages.
    "blank":     ("00000", "00000", "00000", "00000", "00000"),  # between the digits of a 2-digit number
    "dot":       ("00000", "00000", "00100", "00000", "00000"),  # SELF-CHECK
    "border":    ("11111", "10001", "10001", "10001", "11111"),  # READY, and report page 1 (total)
    "block":     ("11111", "11111", "11111", "11111", "11111"),  # class 1 / target prompt
    "x":         ("10001", "01010", "00100", "01010", "10001"),  # FAULT and CALIBRATION_FAILED
    "checker":   ("10101", "01010", "10101", "01010", "10101"),  # UNKNOWN count page
    "bars":      ("01010", "01010", "01010", "01010", "01010"),  # rejected-events page
    "hourglass": ("11111", "01110", "00100", "01110", "11111"),  # STATUS_TIMEBOX
    "diagonal":  ("10000", "01000", "00100", "00010", "00001"),  # STATUS_ABORTED / DEGRADED
    "arrow":     ("00100", "01110", "10101", "00100", "00100"),  # sweeping -- static, changed on state
}

# 3x5 font padded into the 5x5. Digits, not a dot tally: a misread digit is obviously a misread, a
# miscounted tally looks like an answer. UNVERIFIED that this is legible at demo distance -- Stage 1.
_DIGITS = (
    ("01110", "01010", "01010", "01010", "01110"),
    ("00100", "01100", "00100", "00100", "01110"),
    ("01110", "00010", "01110", "01000", "01110"),
    ("01110", "00010", "01110", "00010", "01110"),
    ("01010", "01010", "01110", "00010", "00010"),
    ("01110", "01000", "01110", "00010", "01110"),
    ("01110", "01000", "01110", "01010", "01110"),
    ("01110", "00010", "00010", "00010", "00010"),
    ("01110", "01010", "01110", "01010", "01110"),
    ("01110", "01010", "01110", "00010", "01110"),
)


def _expand(pattern):
    rows = []
    for line in pattern:
        row = []
        for ch in line:
            row.append(100 if ch == "1" else 0)
        rows.append(row)
    return rows


def show_frame(rows):
    """rows = 5 lists of 5 brightness ints, 0-100. A no-op returning None when there is no hub."""
    if API == API_SPIKE3:
        from hub import light_matrix                  # UNVERIFIED call site -- never run
        flat = []
        for row in rows:
            for value in row:
                flat.append(int(value))
        light_matrix.show(flat)                       # SPIKE 3: one list of 25, whole frame at once
        return None
    if API == API_SPIKE2:
        matrix = hub_api._hub_obj().light_matrix              # UNVERIFIED call site -- never run
        for y in range(5):
            for x in range(5):
                matrix.set_pixel(x, y, int(rows[y][x]))  # SPIKE 2: no whole-frame call, 25 writes
        return None
    return None


def show_glyph(name):
    """One named glyph from _GLYPHS. An unknown name raises KeyError -- a typo must be loud, because
    a silently blank matrix during a run is indistinguishable from a dead hub."""
    return show_frame(_expand(_GLYPHS[name]))


def show_digit(d):
    """One digit, 0-9. main.py splits a multi-digit number and shows "blank" between the digits."""
    if d < 0 or d > 9:
        raise ValueError("show_digit takes 0-9; split the number in main.py")
    return show_frame(_expand(_DIGITS[d]))


# --- Sound ------------------------------------------------------------------
# One beep per counted target is the Builder's tally, independent of the number the robot prints
# (docs/plans/conops.md section 5), so a beep that makes no noise silently destroys the most valuable
# observation of the run. Confirm audibility in the first hub session.

def beep(freq_hz, ms):
    """A tone of freq_hz for ms milliseconds. UNVERIFIED on both generations -- never run."""
    if API == API_SPIKE3:
        from hub import sound
        # SPIKE 3: sound.beep(freq, duration_ms, volume) returns an Awaitable. UNVERIFIED whether it
        # sounds at all when it is never awaited; if it does not, this call becomes runloop-aware and
        # every caller of beep() stays unchanged, which is why it is wrapped here.
        sound.beep(int(freq_hz), int(ms))
        return None
    if API == API_SPIKE2:
        # SPIKE 2 speaks MIDI NOTE NUMBERS (44-123) and SECONDS, not Hz and ms -- convert, do not guess.
        # It also BLOCKS for the duration; bounded by ms, so keep in-tick beeps short.
        note = 69.0 + 12.0 * hub_api._math.log(float(freq_hz) / 440.0) / hub_api._math.log(2.0)
        note = int(note + 0.5)
        if note < 44:
            note = 44
        elif note > 123:
            note = 123
        hub_api._hub_obj().speaker.beep(note, ms / 1000.0)
        return None
    return None


def tone_rising():
    """Two-tone up: calibration starting, and anything that means "carrying on"."""
    beep(660, 120)
    beep(990, 120)
    return None


def tone_falling():
    """Two-tone down: FAULT and CALIBRATION_FAILED. Diagnosable from across the room without the matrix.

    UNVERIFIED on SPIKE 3: if an unawaited sound.beep() returns immediately, the two tones overlap into
    one and rising and falling become indistinguishable. Check this at Stage 1 -- it is the whole point.
    """
    beep(990, 120)
    beep(660, 120)
    return None


# --- Buttons ----------------------------------------------------------------
# Polled in the tick (start in READY, soft abort AB1), so it MUST NOT BLOCK: no wait_until_pressed, no
# await. The CENTRE button belongs to the firmware -- it is the hard stop of last resort (AB2) and is
# not exposed to a program on either generation -- so "center" returns None, meaning CANNOT READ. It
# does not return False, which would read as "the operator is not pressing it".

def button_pressed(which):
    """True/False for "left"/"right"; None when it cannot be read. Never blocks."""
    if which not in ("left", "right", "center"):
        raise ValueError("button_pressed takes left, right or center")
    if API == API_SPIKE3:
        from hub import button                        # UNVERIFIED call site -- never run
        if which == "left":
            return button.pressed(button.LEFT) > 0    # SPIKE 3 returns MILLISECONDS HELD, not a bool
        if which == "right":
            return button.pressed(button.RIGHT) > 0
        return None
    if API == API_SPIKE2:
        if which == "left":
            return hub_api._hub_obj().left_button.is_pressed()   # UNVERIFIED call site -- never run
        if which == "right":
            return hub_api._hub_obj().right_button.is_pressed()
        return None
    return None
