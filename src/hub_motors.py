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
    """(left, right) motor positions in degrees, FORWARD-POSITIVE, feeding odometry.Odometry.update().

    The mirror sign (hub_api.LEFT/RIGHT_MOTOR_FORWARD_SIGN) is applied here, so both values are
    positive when the robot drives forward. This is the fix for the latent odometry bug: the raw
    encoders are equal-and-opposite on this mirrored chassis, so summing them integrated a forward
    move to ~0 mm. odometry.py stays pure and mirror-agnostic; the convention lives in this layer.
    """
    if API == API_SPIKE3:
        return (hub_api.LEFT_MOTOR_FORWARD_SIGN * hub_api._motor.relative_position(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT")),
                hub_api.RIGHT_MOTOR_FORWARD_SIGN * hub_api._motor.relative_position(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT")))
    if API == API_SPIKE2:
        return (hub_api.LEFT_MOTOR_FORWARD_SIGN * hub_api._motor_obj("left").get_degrees_counted(),
                hub_api.RIGHT_MOTOR_FORWARD_SIGN * hub_api._motor_obj("right").get_degrees_counted())
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
# DRIVE_MAX_DPS -- MEASURED 2026-08-27, no longer a guess.
# The hub reports its own ceiling: motor.info(port.A) -> (device_id=48, max_speed=930).
# Both motors on ports A and B report device_id 48.
#
# This REPLACES the old 660.0, which was the deliberately conservative "slowest motor we
# might own" figure chosen while the motor type was unknown. It under-drove us by 29%.
#
# Do NOT substitute LEGO's datasheet figure (often quoted as 1110 deg/s for a Medium
# Angular 45603). The hub is the authority on what this motor will actually accept, and
# the hub says 930. Where they disagree, believe the hardware.
DRIVE_MAX_DPS = 930.0

# CONFIRMED 2026-09-01 (examples/drive_moves.py, watched on the robot): the motors ARE mounted
# mirrored. LEFT wheel is port A, forward = NEGATIVE; RIGHT wheel is port B, forward = POSITIVE.
# So robot-forward is (A: -v, B: +v). Encoder deltas were symmetric to +/-1 deg. The flip lives here
# beside the port map, NOT in main.py, or the heading-hold arithmetic stops being readable.
#   LEFT_MOTOR_FORWARD_SIGN = -1 ; RIGHT_MOTOR_FORWARD_SIGN = +1  (see docs/hardware/port-map.md)


def _clamp_pct(value):
    if value > 100.0:
        return 100.0
    if value < -100.0:
        return -100.0
    return value


def drive(left_pct, right_pct):
    """Continuous velocity pair, percent, where POSITIVE means the robot drives FORWARD.

    The mirror sign is applied here too, so a caller writes forward-positive percents and does not
    need to know the motors are mounted mirrored. Without it, drive(50, 50) would SPIN the robot
    (left backward, right forward) instead of going forward. Returns None; on the host a no-op.
    """
    left_pct = _clamp_pct(left_pct) * hub_api.LEFT_MOTOR_FORWARD_SIGN
    right_pct = _clamp_pct(right_pct) * hub_api.RIGHT_MOTOR_FORWARD_SIGN
    if API == API_SPIKE3:                             # UNVERIFIED call site -- never run
        hub_api._motor.run(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT"),
                   int(left_pct * DRIVE_MAX_DPS / 100.0))
        hub_api._motor.run(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT"),
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
        hub_api._motor.stop(hub_api._require(hub_api.LEFT_MOTOR_PORT, "hub_api.LEFT_MOTOR_PORT"))    # SPIKE 3 stops BRAKE by default
        hub_api._motor.stop(hub_api._require(hub_api.RIGHT_MOTOR_PORT, "hub_api.RIGHT_MOTOR_PORT"))
        return None
    if API == API_SPIKE2:                             # UNVERIFIED call site -- never run
        hub_api._motor_obj("left").stop()
        hub_api._motor_obj("right").stop()
        return None
    return None
