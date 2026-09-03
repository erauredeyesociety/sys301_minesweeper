"""Hub API detection, the port map, and the clock -- the shared foundation.

Part of the hub-facing layer. **Only `hub_*.py` modules may import the LEGO API** -- everything else in
`src/` stays pure and runs on the host ([ADR-0004], enforced by ./scripts/check-docs.py).

Split out of the old monolithic `sensors.py` on 2026-08-26: one file per device, so each stays small
enough to read in one sitting. That is load-bearing here -- this project carries no test suite and no
debugger, and smallness is what replaces both (test_methodology.md).

THE RULE: a reader returns None when it cannot read. NEVER 0, never a default, never a last-known
value. A caller that gets None knows it has no data; a caller that gets 0 does not.
"""
import math as _math
import time as _time

_ticks_ms = getattr(_time, "ticks_ms", None)   # MicroPython has it, CPython does not; see now_ms()

API_SPIKE3 = "spike3"
API_SPIKE2 = "spike2"
API_NONE = "simulated"

API = API_NONE
_hub = None

try:                                    # SPIKE 3
    import motor as _motor              # noqa: F401
    import color_sensor as _color       # noqa: F401
    import distance_sensor as _distance # noqa: F401
    from hub import port as _port       # noqa: F401
    API = API_SPIKE3
except ImportError:
    # KNOWN-DEAD ON OUR HUB, kept deliberately (2026-08-27): our hub is SPIKE 3, measured, so this
    # arm -- and every API_SPIKE2 branch in hub_imu / hub_motors / hub_selfcheck -- can never run
    # here. Deleting it is an ADR-shaped call about whether this code must survive meeting a
    # different hub, not a drive-by cleanup. Raised, not done.
    try:                                # SPIKE 2
        from spike import PrimeHub as _PrimeHub, ColorSensor as _ColorSensor, \
            DistanceSensor as _DistanceSensor, Motor as _Motor
        API = API_SPIKE2
    except ImportError:
        API = API_NONE                  # host: no hardware, and we say so


def api_generation():
    """Which LEGO API this module bound to. Report it at run start -- do not assume it."""
    return API


def available():
    return API != API_NONE


# --- Port map ---------------------------------------------------------------
# Single source of truth is docs/hardware/port-map.md (scope TR-5). These are UNASSIGNED until the
# Builder mounts the parts and the port map is filled in; nothing here is a guess at what is plugged
# in where, because a wrong port map is a silent failure that wastes a whole class session.
#
# THE VALUE IS GENERATION-DEPENDENT and only one generation is ever live at a time: on SPIKE 3 write
# the port OBJECT, COLOR_PORT = _port.E; on SPIKE 2 write the STRING, COLOR_PORT = "E". Fill these in
# only after api_generation() has been read off the actual hub.
#
# MEASURED 2026-09-03 after rebuild, read-only probes over USB:
#   A motor id 48, B motor id 48, C colour id 61, D colour id 61, E/F empty.
# The physical left/right and signs below come from the 2026-09-01 drive test; re-run a short
# wheels-up move if the build changes again.
if API == API_SPIKE3:
    LEFT_MOTOR_PORT = _port.A
    RIGHT_MOTOR_PORT = _port.B
    COLOR_PORT = _port.C
    SECOND_COLOR_PORT = _port.D
    DISTANCE_PORT = None
elif API == API_SPIKE2:
    LEFT_MOTOR_PORT = "A"
    RIGHT_MOTOR_PORT = "B"
    COLOR_PORT = "C"
    SECOND_COLOR_PORT = "D"
    DISTANCE_PORT = None
else:
    LEFT_MOTOR_PORT = None
    RIGHT_MOTOR_PORT = None
    COLOR_PORT = None
    SECOND_COLOR_PORT = None
    DISTANCE_PORT = None

# The mirrored-motor sign convention, MEASURED 2026-09-01 by watching the robot drive
# (examples/drive_moves.py, confirmed by the operator; docs/hardware/port-map.md).
# The two motors are mounted mirrored, so a positive robot-FORWARD command is a NEGATIVE
# velocity on the left motor and a POSITIVE velocity on the right. hub_motors applies these
# to BOTH the drive command AND the encoder reads, so everything downstream (odometry,
# telemetry) sees FORWARD-POSITIVE values on both wheels. Without them, forward motion
# integrated to ~0 distance because the raw encoders are equal-and-opposite (latent bug
# caught by the drive checkpoint data). These are plain ints so they are host-safe.
LEFT_MOTOR_FORWARD_SIGN = -1
RIGHT_MOTOR_FORWARD_SIGN = +1


class PortMapIncomplete(Exception):
    """A port was needed before the port map was filled in. Fail loud, on the bench, not in the demo."""


def _require(port_value, name):
    if port_value is None:
        raise PortMapIncomplete(
            "{0} is unassigned -- fill in docs/hardware/port-map.md and set it in hub_api.py".format(name))
    return port_value

# --- SPIKE 2 lazy object helpers -------------------------------------------
# The legacy API is object-based rather than port-function-based. Built on first use so that merely
# importing this module on the host cannot fail.
_cache = {}


def _hub_obj():
    if "hub" not in _cache:
        _cache["hub"] = _PrimeHub()
    return _cache["hub"]


def _color_obj():
    if "color" not in _cache:
        _cache["color"] = _ColorSensor(_require(COLOR_PORT, "COLOR_PORT"))
    return _cache["color"]


def _distance_obj():
    if "distance" not in _cache:
        _cache["distance"] = _DistanceSensor(_require(DISTANCE_PORT, "DISTANCE_PORT"))
    return _cache["distance"]


def _motor_obj(side):
    key = "motor_" + side
    if key not in _cache:
        p = LEFT_MOTOR_PORT if side == "left" else RIGHT_MOTOR_PORT
        _cache[key] = _Motor(_require(p, side.upper() + "_MOTOR_PORT"))
    return _cache[key]

# --- Time -------------------------------------------------------------------
# The hub runs MicroPython and the host runs CPython, and only one of them has time.ticks_ms(). Bind
# the difference once at import so the tick does not pay a getattr per call, and so main.py never has
# to know which platform it is on.

def now_ms():
    """Monotonic milliseconds, as an int. MUST work on the host -- the state machine is walked there.

    UNVERIFIED on the hub: that Hub OS exposes time.ticks_ms() at all
    (docs/research/spike-prime-linux-toolchain.md flags it). If it does not, the fallback below is
    time.monotonic(), which is a CPython name that MicroPython does NOT have -- so on such a hub this
    raises AttributeError on the first call, loudly, at Stage 1 on a desk. That is deliberate: a
    silent fake clock would corrupt the time box and every rate measurement in the report.

    ticks_ms() wraps at 2**30 ms. What makes subtraction safe is not that our RUN is minutes -- a wrap
    can land mid-run whatever the run length -- it is that the counter starts near zero at power-on and
    2**30 ms is ~12.4 days of uptime. Do not carry a value across a power cycle, and if a wrap is ever
    observed, the fix is time.ticks_diff(), not a bigger number.
    """
    if _ticks_ms is not None:
        return _ticks_ms()
    return int(_time.monotonic() * 1000.0)
