"""The four motion primitives, and the ONE place that owns what left, right, forward and back mean.

Upload it once and import it from any on-hub program:

    ./hub_programmer/upload.py src/hub_drive.py --apply     # -> /flash/lib/hub_drive.py
    from hub_drive import forward, backward, spin_left, spin_right, stop, turn_by

WHY THIS EXISTS
    Direction was got wrong three separate times on 2026-09-08, each time by INFERRING it from
    another program's convention instead of measuring it:

      * `find_note.py` was flipped to drive backward, then flipped back, because the recorded
        "forward = A:-v, B:+v" was doubted after one bad run.
      * `follow_tape.py`'s gyro heading hold had an inverted sign and drove the robot in circles for
        a whole 40 s run (docs/lessons_learned/guard-every-feedback-loop.md).
      * `follow_tape.py`'s corner turn commanded +900 and MEASURED a yaw delta of -972, i.e. it
        turned away from the corner.

    The root cause is that ENCODER SIGNS AND YAW SIGNS ARE CONVENTIONS, NOT DIRECTIONS. Nothing in
    the telemetry says which way the robot physically moves; only a human watching it can say that.
    So the mapping lives HERE, in one file, with the evidence beside it, and every program imports it
    rather than re-deriving it. Getting it wrong once now costs one edit instead of three.

    Run examples/calibrate_directions.py to re-establish the two constants below after any rebuild.

MEASURED CONSTANTS -- change these ONLY from a calibration run, never from reasoning.
    FORWARD_SIGN  MEASURED 2026-09-03 (examples/motor_poc.py drove a 1 ft square) and CONFIRMED
                  2026-09-08 (find_note.py found notes driving this way, twice). The motors are
                  mounted mirrored, so forward is left NEGATIVE and right POSITIVE.
    TURN_SIGN     MEASURED 2026-09-08 from telemetry, run 0000043283:
                      TURN_START_want900_from17  ->  TURN_END_at-955_delta-972_want900
                  A positive command produced a NEGATIVE yaw delta and the robot turned away from the
                  corner. So the pairing below is inverted relative to what motor_poc.py implied.
    TURN_LEAD_DDEG  MEASURED on the same run: commanded 900, achieved 972 -- the loop breaks on the
                  threshold and the robot then coasts ~72 ddeg (7.2 deg) further. ONE sample only.

MicroPython subset: no f-strings. The LEGO API is imported INSIDE the calls, so this module still
imports on the host (./scripts/check-docs.py checks that) and only its call sites are hub-only.
"""

# GEOMETRY. src/config.py is the single source of truth for these MEASURED numbers, but this module
# cannot simply import it.
#
# ⚠ MEASURED 2026-09-08: THE MODULE NAME `config` IS SHADOWED ON THE HUB. Uploading src/config.py to
# /flash/lib and doing `import config` in an on-hub program resolves to something else in the LEGO
# firmware, not our file, and the program dies at import:
#     File "/flash/lib/hub_drive.py", line 49, in <module>
#     AttributeError: 'module' object has no attribute 'WHEEL_DIAMETER_MM'
# The upload itself was fine -- hash-verified by the hub. The NAME is the problem.
#
# So the values are declared here, and kept honest by an ASSERTION against config.py that runs on the
# HOST. ./scripts/check-docs.py imports every src/ module on the host, so if the two ever disagree
# the check fails loudly and immediately. Single source is enforced by a CHECK rather than by a hub
# import that can be hijacked -- which is the stronger guarantee anyway, since it cannot fail silently.
WHEEL_DIAMETER_MM = 63.5      # mm, MEASURED 2026-09-03. Mirror of config.WHEEL_DIAMETER_MM.
TRACK_WIDTH_MM = 95.0         # mm effective, MEASURED 2026-09-03. Mirror of config.TRACK_WIDTH_MM.
COUNTS_PER_REV = 360.0        # LEGO spec. Mirror of config.ENCODER_COUNTS_PER_REV.

try:                          # host only: on the hub this import gets the WRONG module, see above
    import config as _cfg
    _mirrored = (("WHEEL_DIAMETER_MM", WHEEL_DIAMETER_MM),
                 ("TRACK_WIDTH_MM", TRACK_WIDTH_MM),
                 ("ENCODER_COUNTS_PER_REV", COUNTS_PER_REV))
    for _name, _here in _mirrored:
        _there = getattr(_cfg, _name, None)
        if _there is not None and abs(float(_there) - float(_here)) > 1e-6:
            raise ValueError(
                "hub_drive geometry has drifted from config.py: " + _name + " is " + str(_here) +
                " here but " + str(_there) + " in config.py. config.py is the source of truth -- "
                "update the mirror above, and re-upload hub_drive.py to the hub.")
except ImportError:
    pass                      # running on the hub, where config is unavailable under that name

FORWARD_SIGN = 1        # 1 = forward is (A negative, B positive). Flip only from a calibration run.
TURN_SIGN = 1           # MEASURED 2026-09-08 by examples/calibrate_directions.py: with -1 the
                        # operator WATCHED spin_right turn left and spin_left turn right. +1 is
                        # correct. This is an EYES measurement, which is the only kind that can
                        # settle a direction -- yaw sign alone is a convention, not a direction.
TURN_LEAD_DDEG = 70     # stop this far short of the target; the robot coasts the rest. MEASURED.

LEFT_FWD = -1 * FORWARD_SIGN
RIGHT_FWD = 1 * FORWARD_SIGN


# --- geometry: millimetres <-> motor degrees, and mm/s <-> deg/s -----------------------------------
# One wheel revolution advances pi * diameter of ground, and one revolution is COUNTS_PER_REV degrees.
# Everything below is arithmetic on the two MEASURED constants above -- no new assumptions.
MM_PER_REV = 3.141592653589793 * WHEEL_DIAMETER_MM      # 199.49 mm at 63.5 mm


def mm_to_deg(mm):
    """Ground distance -> motor degrees."""
    return mm * COUNTS_PER_REV / MM_PER_REV


def deg_to_mm(deg):
    """Motor degrees -> ground distance."""
    return deg * MM_PER_REV / COUNTS_PER_REV


def mms_to_dps(mms):
    """Ground speed in mm/s -> motor deg/s. Use this instead of guessing a percent."""
    return mm_to_deg(mms)


def dps_to_mms(dps):
    """Motor deg/s -> ground speed in mm/s."""
    return deg_to_mm(dps)


def wheel_speeds_for_arc(speed_mms, radius_mm):
    """(left_mms, right_mms) to drive an arc of the given radius at the given centre speed.

    radius_mm > 0 curves RIGHT, < 0 curves LEFT, and a radius of 0 is a spin in place.
    The outer wheel travels (R + track/2) while the inner travels (R - track/2) over the same angle,
    so their speeds are in that ratio. This is the only place the track width does any work, and it
    is why TRACK_WIDTH_MM is the EFFECTIVE value measured from a real turn rather than a ruler
    reading -- it folds in the rear caster's drag.
    """
    if radius_mm == 0:
        return (speed_mms, -speed_mms)
    half = TRACK_WIDTH_MM / 2.0
    r = float(abs(radius_mm))
    inner = speed_mms * (r - half) / r
    outer = speed_mms * (r + half) / r
    return (outer, inner) if radius_mm > 0 else (inner, outer)


def arc(speed_mms, radius_mm):
    """Drive a constant-radius arc at a ground speed in mm/s. radius > 0 curves RIGHT."""
    left_mms, right_mms = wheel_speeds_for_arc(speed_mms, radius_mm)
    _run(LEFT_FWD * mms_to_dps(left_mms), RIGHT_FWD * mms_to_dps(right_mms))


def _ports():
    from hub import port
    return (port.A, port.B)          # A = LEFT motor, B = RIGHT motor (docs/hardware/port-map.md)


def _run(left_dps, right_dps):
    import motor
    pl, pr = _ports()
    motor.run(pl, int(left_dps))
    motor.run(pr, int(right_dps))


def stop():
    """Cut both motors. Safe to call when they are already stopped, and safe in a finally:."""
    import motor
    pl, pr = _ports()
    try:
        motor.stop(pl)
    except Exception:
        pass
    try:
        motor.stop(pr)
    except Exception:
        pass


def forward_mms(mms, steer_mms=0):
    """Drive forward at a ground speed in MILLIMETRES PER SECOND -- the unit the mission thinks in."""
    forward(mms_to_dps(mms), mms_to_dps(steer_mms))


def backward_mms(mms, steer_mms=0):
    """Drive backward at a ground speed in millimetres per second."""
    backward(mms_to_dps(mms), mms_to_dps(steer_mms))


def forward(dps, steer=0):
    """Drive forward at `dps`. `steer` > 0 curves RIGHT, < 0 curves LEFT, by slowing that wheel.

    steer is in the same units as dps, and is SUBTRACTED from the inside wheel, so the outside wheel
    keeps the commanded speed. That matters for odometry: a curve slows the robot rather than
    speeding one side up past the motor's ceiling.
    """
    left = dps - steer if steer > 0 else dps
    right = dps + steer if steer < 0 else dps
    _run(LEFT_FWD * left, RIGHT_FWD * right)


def backward(dps, steer=0):
    """Drive backward at `dps`. Steering keeps the same physical meaning as forward()."""
    left = dps - steer if steer > 0 else dps
    right = dps + steer if steer < 0 else dps
    _run(-LEFT_FWD * left, -RIGHT_FWD * right)


def spin_right(dps):
    """Spin in place, clockwise seen from above. Wheels oppose, so the robot turns about its centre."""
    _run(LEFT_FWD * dps * TURN_SIGN, -RIGHT_FWD * dps * TURN_SIGN)


def spin_left(dps):
    """Spin in place, anticlockwise seen from above."""
    _run(-LEFT_FWD * dps * TURN_SIGN, RIGHT_FWD * dps * TURN_SIGN)


def normalize_ddeg(d):
    """Yaw WRAPS at +/-180 deg (MEASURED, imu-characterisation-2026-08-27). Every delta goes through
    here, or a 1 deg error reads as 359."""
    return ((d + 1800) % 3600) - 1800


def read_yaw():
    """Yaw in DECIDEGREES, or None when it cannot be read. None, never 0 -- a caller that gets 0
    thinks it has a heading."""
    try:
        from hub import motion_sensor
        return motion_sensor.tilt_angles()[0]
    except Exception:
        return None


def turn_by(ddeg, dps, tick_ms=50, cap_ms=6000, on_tick=None):
    """Spin until the GYRO says the heading changed by |ddeg|. ddeg > 0 turns RIGHT, < 0 turns LEFT.

    Gyro-closed, so it does NOT depend on the track width -- the trick examples/motor_poc.py proved.
    Generator-free and synchronous: call it from a runloop coroutine with time.sleep_ms, or pass
    on_tick to sample telemetry each tick.

    Returns (start_yaw, end_yaw, achieved_ddeg) or (None, None, None) if the gyro never read.
    Stops the motors before returning, on every path.
    """
    import time
    y0 = read_yaw()
    if y0 is None:
        return (None, None, None)

    # Stop short by the MEASURED coast. Guarded: a small turn must not get a negative target, which
    # would satisfy the condition immediately and turn not at all.
    target = abs(ddeg) - TURN_LEAD_DDEG
    if target < 100:
        target = abs(ddeg)

    if ddeg > 0:
        spin_right(dps)
    else:
        spin_left(dps)
    t0 = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < cap_ms:
            y = read_yaw()
            if y is not None and abs(normalize_ddeg(y - y0)) >= target:
                break
            if on_tick is not None:
                on_tick()
            time.sleep_ms(tick_ms)
    finally:
        stop()
    time.sleep_ms(200)                       # let the coast finish before reading the TRUE heading
    y1 = read_yaw()
    if y1 is None:
        return (y0, None, None)
    return (y0, y1, normalize_ddeg(y1 - y0))
