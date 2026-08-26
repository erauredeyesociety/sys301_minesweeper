"""Motor encoders and the ONLY motor writes in the project.

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

# --- Motors and IMU ---------------------------------------------------------
# All three candidate motors (45602 / 45603 / 45607) have built-in absolute encoders, and the hub has
# a 6-axis IMU. Both are hub_api.available regardless of which motors we own -- which is why odometry.py
# could be written before the hardware question closed.

def read_motor_degrees():
    """(left, right) absolute motor positions in degrees, feeding odometry.Odometry.update()."""
    if API == API_SPIKE3:
        return (_motor.relative_position(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT")),
                _motor.relative_position(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT")))
    if API == API_SPIKE2:
        return (hub_api._motor_obj("left").get_degrees_counted(),
                hub_api._motor_obj("right").get_degrees_counted())
    return None

# --- Motor writes -----------------------------------------------------------
# The ONLY motor writes in the project. A velocity PAIR, not a steering value, so the heading-hold
# arithmetic stays pure in main.py (docs/plans/mission-algorithm.md, Main loop step 9).
#
# UNITS: both arguments are PERCENT, -100 (full reverse) to +100 (full forward), and they are CLAMPED.
# The two generations disagree, and this is the number one porting trap:
#   SPIKE 2   Motor.start(speed)       speed is PERCENT      -> passed straight through
#   SPIKE 3   motor.run(port, vel)     vel is DEGREES/SECOND -> percent * DRIVE_MAX_DPS / 100
#
# DRIVE_MAX_DPS is the SLOWEST candidate motor's ceiling: Small 45607 +-660 deg/s, Large 45602 +-1050,
# Medium 45603 +-1110. We own two motors of UNKNOWN type, so 660 is the only figure that cannot ask a
# motor for more than it has. Raise it only once the Builder identifies what is actually bolted on.
DRIVE_MAX_DPS = 660.0

# UNVERIFIED: on a differential drive one motor is mounted mirrored, so one side needs a sign flip for
# a positive percent to mean "forward". Which side is a Stage 2 finding; the flip belongs here, beside
# the port map, and NOT in main.py, or the heading-hold arithmetic stops being readable.


def _clamp_pct(value):
    if value > 100.0:
        return 100.0
    if value < -100.0:
        return -100.0
    return value


def drive(left_pct, right_pct):
    """Continuous velocity pair, percent. Returns None; on the host a no-op, never a fake move."""
    left_pct = _clamp_pct(left_pct)
    right_pct = _clamp_pct(right_pct)
    if API == API_SPIKE3:                             # UNVERIFIED call site -- never run
        _motor.run(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT"),
                   int(left_pct * DRIVE_MAX_DPS / 100.0))
        _motor.run(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT"),
                   int(right_pct * DRIVE_MAX_DPS / 100.0))
        return None
    if API == API_SPIKE2:                             # UNVERIFIED call site -- never run
        hub_api._motor_obj("left").start(int(left_pct))
        hub_api._motor_obj("right").start(int(right_pct))
        return None
    return None


def stop_motors():
    """Stop both motors. Called from the try/finally that guards the whole run (degraded mode AB2)."""
    if API == API_SPIKE3:                             # UNVERIFIED call site -- never run
        _motor.stop(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT"))    # SPIKE 3 stops BRAKE by default
        _motor.stop(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT"))
        return None
    if API == API_SPIKE2:                             # UNVERIFIED call site -- never run
        hub_api._motor_obj("left").stop()
        hub_api._motor_obj("right").stop()
        return None
    return None
