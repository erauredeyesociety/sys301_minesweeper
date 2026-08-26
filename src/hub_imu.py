"""The hub's 6-axis IMU -- yaw, the heading source.

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

def read_yaw_deg():
    """Hub yaw in degrees. The heading source -- see odometry.py for why not the encoders.

    UNVERIFIED: SPIKE 3 reports yaw in DECIDEGREES via motion_sensor.tilt_angles(); confirm the scale
    on the real hub before trusting any number that comes out of here.
    """
    if API == API_SPIKE3:
        from hub import motion_sensor
        return motion_sensor.tilt_angles()[0] / 10.0
    if API == API_SPIKE2:
        return hub_api._hub_obj().motion_sensor.get_yaw_angle()
    return None

def reset_yaw():
    """Zero the heading. Once, STATIONARY, before SWEEP -- resetting while moving bakes in the error."""
    if API == API_SPIKE3:
        from hub import motion_sensor                 # UNVERIFIED call site -- never run
        motion_sensor.reset_yaw(0)                    # SPIKE 3 takes the new angle explicitly
        return None
    if API == API_SPIKE2:
        hub_api._hub_obj().motion_sensor.reset_yaw_angle()    # UNVERIFIED call site -- never run
        return None
    return None


# Which probes must pass for the run to proceed. The distance sensor is NOT here: we do not own one,
# and whether we ever will depends on the professor's answer about the arena boundary. Including it
# unconditionally made selfcheck() return NOT_OK on every run forever -- a check that always fails is


# --- The other four axes -----------------------------------------------------
# The hub carries a SIX-axis IMU: three-axis gyroscope AND three-axis accelerometer
# (docs/course/lego-reference/LegoTechnicalSpecifications.txt lines 35-41). Yaw alone uses one of
# the six. The rest are worth streaming because they diagnose things yaw cannot:
#
#   pitch/roll   the robot tilting -- a wheel on a cable, a ramp, a wobbling chassis. Also the only
#                way to confirm the robot was FLAT, which every odometry assumption depends on.
#   accel x/y/z  impacts and stalls. A collision with the arena wall is a spike here and nothing at
#                all in the encoders, which keep turning against a stopped robot.
#
# UNVERIFIED on both API generations: the method names and the units below. SPIKE 3's
# motion_sensor.tilt_angles() returns DECIDEGREES; whether acceleration() is in mG, m/s^2 or raw
# counts is not documented anywhere we have found. Confirm at the REPL before trusting a number.

def read_tilt_ddeg():
    """(yaw, pitch, roll) in DECIDEGREES, or None. Raw units on purpose -- see telemetry.py.

    Decidegrees because that is what the hub reports; converting here would throw away a digit and
    hide the unit from the log. The analysis side divides by 10 once, in one place.
    """
    if API == API_SPIKE3:
        from hub import motion_sensor
        return motion_sensor.tilt_angles()
    if API == API_SPIKE2:
        m = hub_api._hub_obj().motion_sensor
        return (m.get_yaw_angle() * 10, m.get_pitch_angle() * 10, m.get_roll_angle() * 10)
    return None


def read_accel():
    """(x, y, z) acceleration, or None. UNITS UNVERIFIED -- record them once measured.

    Its job in this project is not absolute magnitude but CHANGE: a spike means the robot hit
    something. That works whatever the scale, which is why an unknown unit does not block logging it.
    """
    if API == API_SPIKE3:
        from hub import motion_sensor
        return motion_sensor.acceleration()
    if API == API_SPIKE2:
        return hub_api._hub_obj().motion_sensor.get_acceleration()
    return None


def is_flat(max_tilt_ddeg=100):
    """Is the robot level? None when unreadable -- never a cheerful True.

    Odometry assumes a flat robot. If pitch or roll drifts past the limit mid-run, the pose is
    wrong in a way no gyro-vs-encoder check would reveal, because both agree about a robot that is
    tilting. Default 100 ddeg = 10 deg, [ASSUMED] -- measure what a normal run actually shows.
    """
    t = read_tilt_ddeg()
    if t is None:
        return None
    return abs(t[1]) <= max_tilt_ddeg and abs(t[2]) <= max_tilt_ddeg
