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

    UNITS CONFIRMED, MEASURED on our hub 2026-08-27: tilt_angles() reports DECIDEGREES, so the /10.0
    below is right. Derived from gravity rather than a datasheet -- the accelerometer put the true
    tilt at 0.705 deg while tilt_angles() reported a magnitude of 6.7, a ratio of 9.53, i.e. 10.
    docs/findings/imu-characterisation-2026-08-27.md

    YAW WRAPS AT +/-180 DEGREES. Observed -1795 and +1771 ddeg across one hand rotation, so this
    function returns -179.5 .. +177.1 and jumps the full range at the seam. It does NOT accumulate.
    Every heading DIFFERENCE computed from this must go through odometry.normalize_angle(); a plain
    subtraction across the seam gives a ~360 deg error and a robot that spins to correct it.
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
        from hub import motion_sensor                 # UNVERIFIED call site -- never run.
                                                      # reset_yaw IS in the measured API surface
                                                      # (2026-08-27) but has never been CALLED.
        motion_sensor.reset_yaw(0)                    # SPIKE 3 takes the new angle explicitly
        return None
    if API == API_SPIKE2:
        hub_api._hub_obj().motion_sensor.reset_yaw_angle()    # UNVERIFIED call site -- never run
        return None
    return None


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
# UNITS MEASURED on our own hub 2026-08-27, derived from gravity, not read off a datasheet:
#   tilt_angles()   DECIDEGREES  (true tilt 0.705 deg vs a reported magnitude of 6.7 -> ratio 9.53)
#   acceleration()  MILLI-G      (a flat, still hub reads ax=-2.0 ay=12.0 az=989.2, |a|=989.3,
#                                 so 1 g reads as about 989 units -- not 1000, and not m/s^2)
# The method names above are confirmed present in the API surface. What is still UNVERIFIED is the
# SPIKE 2 arm of every branch below: this hub is SPIKE 3 and those lines have never run.
# docs/findings/imu-characterisation-2026-08-27.md

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
    """(x, y, z) acceleration in MILLI-G, or None. ~989 units per g at rest, measured 2026-08-27.

    Its job in this project is not absolute magnitude but CHANGE: a spike means the robot hit
    something. That worked whatever the scale, which is why logging it was never blocked on the
    unit -- but the unit is known now, and telemetry names its columns accx_mg / accy_mg / accz_mg.

    A second, free use fell out of knowing the scale: gravity is a CONSTANT the hub can watch. If
    |a| wanders from ~989 while the robot is supposed to be still, something disturbed it, and any
    measurement taken over that window is contaminated. examples/gyro_drift.py uses exactly this to
    refuse to report a drift figure -- docs/lessons_learned/bound-the-inputs-before-trusting-a-conclusion.md.
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
    tilting.

    The UNIT is no longer assumed: decidegrees, measured 2026-08-27, so 100 ddeg really is 10 deg.
    The THRESHOLD is still [ASSUMED] -- nobody has measured what a normal run on a real floor shows.
    Do not read the confirmed unit as a confirmed limit.
    """
    t = read_tilt_ddeg()
    if t is None:
        return None
    return abs(t[1]) <= max_tilt_ddeg and abs(t[2]) <= max_tilt_ddeg
