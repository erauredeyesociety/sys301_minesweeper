"""The ONLY module that touches the LEGO API. Everything else in src/ stays pure and host-testable.

SCAFFOLDING, not finished code. It exists so that the day the hub is identified, the work is filling
in call sites that are already named and already wired -- not designing a layer under time pressure
in class.

TWO API GENERATIONS, AND WE DO NOT YET KNOW WHICH WE HAVE (see docs/runbooks/hub-identification.md):
  SPIKE 3 (current):  import motor, motor_pair, color_sensor, distance_sensor, runloop
                      from hub import port, motion_sensor
  SPIKE 2 (legacy):   from spike import PrimeHub, Motor, MotorPair, ColorSensor, DistanceSensor

This module detects which one is present at import time and adapts. On the HOST neither exists, so it
lands in SIMULATED mode and every reader returns None -- honestly, and loudly enough that nothing
downstream can mistake it for a measurement.

THE RULE THAT MATTERS: a reader returns None when it cannot read. It NEVER returns 0, or a default,
or a last-known value. A caller that gets None knows it has no data; a caller that gets 0 does not.
See docs/directives/honest-instrumentation.md.
"""

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
LEFT_MOTOR_PORT = None
RIGHT_MOTOR_PORT = None
COLOR_PORT = None
DISTANCE_PORT = None


class PortMapIncomplete(Exception):
    """A port was needed before the port map was filled in. Fail loud, on the bench, not in the demo."""


def _require(port_value, name):
    if port_value is None:
        raise PortMapIncomplete(
            "{0} is unassigned -- fill in docs/hardware/port-map.md and set it in sensors.py".format(name))
    return port_value


# --- Colour sensor ----------------------------------------------------------
# Detect on REFLECTED LIGHT, never the built-in colour ID: colour mode spatially averages at target
# edges, which is fatal for edge counting, and its palette is eight saturated LEGO brick colours that
# matte pastel paper is nowhere near. Classification, if the professor's answer to Q5 requires it, is
# a layer ON TOP built from raw RGB -- see docs/research/color-discrimination.md.

def read_reflection():
    """Reflected light, 0-100. None if unreadable. THE primary detection signal."""
    if API == API_SPIKE3:
        return _color.reflection(_require(COLOR_PORT, "COLOR_PORT"))
    if API == API_SPIKE2:
        return _color_obj().reflected_light_intensity()
    return None


def read_rgb():
    """Raw (r, g, b[, intensity]) for classification. None if unreadable or unsupported.

    UNVERIFIED on both generations: whether raw RGB is exposed, and on what scale. Confirm against
    the real hub before building classification on it.
    """
    if API == API_SPIKE3:
        return _color.rgbi(_require(COLOR_PORT, "COLOR_PORT"))
    if API == API_SPIKE2:
        return _color_obj().get_rgb_intensity()
    return None


def read_ambient():
    """Ambient light, 0-100. Useful for detecting that the arena lighting changed mid-run."""
    if API == API_SPIKE3:
        return _color.ambient(_require(COLOR_PORT, "COLOR_PORT"))
    if API == API_SPIKE2:
        return _color_obj().ambient_light_intensity()
    return None


# --- Distance sensor --------------------------------------------------------
# Role: arena boundary and obstacles. Whether we need it at all depends on professor Q3 (what bounds
# the area) -- it is unpurchased, so this is scaffolding against a decision not yet made.

def read_distance_mm():
    """Distance in mm. None when nothing is in range -- which is NOT the same as zero.

    Returning 0 for out-of-range would read as 'a wall is touching us' and drive a stop. None.
    """
    if API == API_SPIKE3:
        return _distance.distance(_require(DISTANCE_PORT, "DISTANCE_PORT"))
    if API == API_SPIKE2:
        return _distance_obj().get_distance_cm(short_range=False)
    return None


# --- Motors and IMU ---------------------------------------------------------
# All three candidate motors (45602 / 45603 / 45607) have built-in absolute encoders, and the hub has
# a 6-axis IMU. Both are available regardless of which motors we own -- which is why odometry.py
# could be written before the hardware question closed.

def read_motor_degrees():
    """(left, right) absolute motor positions in degrees, feeding odometry.Odometry.update()."""
    if API == API_SPIKE3:
        return (_motor.relative_position(_require(LEFT_MOTOR_PORT, "LEFT_MOTOR_PORT")),
                _motor.relative_position(_require(RIGHT_MOTOR_PORT, "RIGHT_MOTOR_PORT")))
    if API == API_SPIKE2:
        return (_motor_obj("left").get_degrees_counted(),
                _motor_obj("right").get_degrees_counted())
    return None


def read_yaw_deg():
    """Hub yaw in degrees. The heading source -- see odometry.py for why not the encoders.

    UNVERIFIED: SPIKE 3 reports yaw in DECIDEGREES via motion_sensor.tilt_angles(); confirm the scale
    on the real hub before trusting any number that comes out of here.
    """
    if API == API_SPIKE3:
        from hub import motion_sensor
        return motion_sensor.tilt_angles()[0] / 10.0
    if API == API_SPIKE2:
        return _hub_obj().motion_sensor.get_yaw_angle()
    return None


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


def selfcheck():
    """Is every device we expect actually connected and responding? Returns a dict of findings.

    An UNKNOWN result is a legitimate answer and is never reported as a pass. This is a DIAGNOSTIC,
    not a test -- it needs the hub, so it can never live in tests/persistent/.
    """
    report = {"api": API, "checks": {}}
    if not available():
        report["verdict"] = "UNKNOWN"
        report["reason"] = "no LEGO API present -- running on the host, nothing to check"
        return report

    probes = (
        ("left_motor", lambda: read_motor_degrees()[0]),
        ("right_motor", lambda: read_motor_degrees()[1]),
        ("yaw", read_yaw_deg),
        ("color_reflection", read_reflection),
        ("distance", read_distance_mm),
    )
    for name, fn in probes:
        try:
            value = fn()
        except PortMapIncomplete as exc:
            report["checks"][name] = {"state": "UNASSIGNED", "detail": str(exc)}
        except Exception as exc:                      # a device that is absent raises; that is data
            report["checks"][name] = {"state": "FAIL", "detail": repr(exc)}
        else:
            state = "UNKNOWN" if value is None else "OK"
            report["checks"][name] = {"state": state, "value": value}

    states = [c["state"] for c in report["checks"].values()]
    report["verdict"] = "OK" if states and all(s == "OK" for s in states) else "NOT_OK"
    return report
