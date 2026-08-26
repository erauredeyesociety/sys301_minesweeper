"""Colour sensor 45605 -- the target detector.

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

# --- Colour sensor ----------------------------------------------------------
# Detect on REFLECTED LIGHT, never the built-in colour ID: colour mode spatially averages at target
# edges, which is fatal for edge counting, and its palette is eight saturated LEGO brick colours that
# matte pastel paper is nowhere near. Classification, if the professor's answer to Q5 requires it, is
# a layer ON TOP built from raw RGB -- see docs/research/color-discrimination.md.

def read_reflection():
    """Reflected light, 0-100. None if unreadable. THE primary detection signal."""
    if API == API_SPIKE3:
        return _color.reflection(hub_api._require(hub_api.COLOR_PORT, "hub_api.COLOR_PORT"))
    if API == API_SPIKE2:
        return hub_api._color_obj().get_reflected_light()
    return None


def read_rgb():
    """Raw (r, g, b[, intensity]) for classification. None if unreadable or unsupported.

    Both generations expose it (docs/research/color-discrimination.md section 1.2). SPIKE 2's
    get_rgb_intensity() is documented 0-1024; SPIKE 3's rgbi() is documented 0-1024 by one mirror and
    left undocumented by the other. UNVERIFIED on OUR hub, and classify.py works in chromaticity
    partly so that the scale cancels -- measure it before any absolute threshold is written.
    """
    if API == API_SPIKE3:
        return _color.rgbi(hub_api._require(hub_api.COLOR_PORT, "hub_api.COLOR_PORT"))
    if API == API_SPIKE2:
        return hub_api._color_obj().get_rgb_intensity()
    return None


def read_ambient():
    """Ambient light, 0-100, on SPIKE 2 only. None on SPIKE 3, which cannot read it at all.

    SPIKE 3's color_sensor exposes color(), reflection() and rgbi() and NOTHING ELSE -- there is no
    ambient function to call (docs/research/color-discrimination.md section 1.2,
    docs/research/detection-and-sweep-techniques.md). The hardware has the mode; the API does not
    reach it. So this returns None there: cannot read, not zero, and no ambient-compensation scheme
    may be designed on top of it until a Hub OS is identified that exposes one.
    """
    if API == API_SPIKE2:
        return hub_api._color_obj().get_ambient_light()
    return None
