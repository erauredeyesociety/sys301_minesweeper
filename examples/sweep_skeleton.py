# examples/sweep_skeleton.py — the smallest thing that looks like the mission.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/sweep_skeleton.py
#
# ############################################################################
# ## THIS DEMO COMMANDS MOTION. It drives both wheels. READ THIS FIRST.      ##
# ############################################################################
#   What it does: a LAWNMOWER / BOUSTROPHEDON sweep. Drive forward one row
#   while polling BOTH colour sensors; on a colour event STOP and REPORT it
#   (a matrix mark, a beep, a printed line) -- it does NOT act on the mine.
#   At the end of a row it pivots 180 degrees using the gyro and drives the
#   next row. That is the whole mission in miniature.
#
#   HOW TO RUN IT SAFELY ON A DESK: put the robot up on a stand / box / two
#   stacked erasers so BOTH WHEELS SPIN FREE OFF THE SURFACE. Then it cannot
#   drive off the desk, and you watch the pattern in the printout, the matrix
#   and the wheels instead. To run it on the FLOOR instead, clear a lane at
#   least as long as ROW_LENGTH_DEG turns the wheels (that distance is in
#   motor degrees, NOT mm -- see below), keep a hand near the hub, and use the
#   soft-abort below.
#   SOFT ABORT: press the LEFT hub button -- the loop stops the motors and
#   ends. HARD STOP of last resort: the centre POWER button (the firmware's,
#   not ours). The motors are also stopped in a finally: block no matter how
#   the program ends.
#   SPEED is deliberately low (DRIVE_SPEED_DPS, far under the 930 deg/s ceiling
#   the hub reported for these motors on 2026-09-01).
#
# [UNVERIFIED] NEVER RUN ON REAL HARDWARE as of 2026-09-01. Every NAME used
# here was read off our own hub, so nothing is invented -- but no motor.run(),
# motor.stop() or reset_relative_position() CALL has ever been made on this
# project, so no motion below is a measurement yet, and which way "forward" is
# (the LEFT_SIGN / RIGHT_SIGN below) is a guess until the wheels actually turn.
# Delete this block once it has run and file the output in docs/findings/runs/.
#
# THIS IS A DEMO / SKELETON. It is deliberately NOT src/main.py: it does not
# calibrate, does not count with the real detector, and does NOT sense the
# arena boundary (that is a separate concern -- row end is by motor degrees
# only). Where the real pure modules plug in is noted at the bottom.
#
# MicroPython notes: no f-strings, no statistics module, no numpy, no enum.
# % formatting and plain loops only.

import time
import motor
import color_sensor
import color
import hub
from hub import port

# --- PORTS AS BUILT (measured 2026-09-01: A,B motors; C,D colour) -----------
LEFT_PORT = port.A
RIGHT_PORT = port.B
COLOR_PORTS = (("C", port.C), ("D", port.D))

# --- MOTION -- all [ASSUMED] / [UNVERIFIED] until the wheels turn -----------
DRIVE_SPEED_DPS = 200     # [ASSUMED] gentle. Measured ceiling is 930 deg/s.
PIVOT_SPEED_DPS = 150     # [ASSUMED] slower for the turn -- easier to watch and to stop.
# Which sign makes a wheel drive the robot FORWARD is UNVERIFIED: on a diff
# drive one motor is mounted mirrored. If "forward" makes the robot SPIN in
# place instead of go straight, flip ONE of these to -1. examples/
# motor_encoder_verbose.py measures which side; this carries it as a knob.
LEFT_SIGN = 1             # [UNVERIFIED]
RIGHT_SIGN = 1            # [UNVERIFIED]

# ROW LENGTH IS IN MOTOR DEGREES, NOT MM. Wheel diameter and track width are
# UNMEASURED (KU-M3), so no deg/s converts to mm/s yet. Parameterising the row
# in degrees is the whole point: measuring the wheel later changes this number,
# not the code. src/odometry.mm_to_degrees() is where mm would convert once the
# wheel is known.
ROW_LENGTH_DEG = 720      # [ASSUMED] ~2 wheel revolutions. Shorten for a desk stand.
NUM_ROWS = 4              # [ASSUMED] small on purpose.
TURN_DEG = 180.0          # a full end-of-row pivot.

# --- DETECTION -- a stand-in, NOT the mission's detector --------------------
# The mine is a YELLOW sticky note. This skeleton fires an "event" on the
# sensor's BUILT-IN colour ID matching EVENT_COLORS, purely so the demo is
# legible with no calibration. That is explicitly NOT how the mission counts:
# the real path is REFLECTANCE through src/detector.EdgeCounter (hysteresis +
# dwell + width gate), fed by hub_color.read_reflection() -- see the bottom.
# The per-sensor rising-edge latch below is a crude stand-in for that
# hysteresis so one note is not re-reported on every poll while driving over it.
EVENT_COLORS = (color.YELLOW,)

# --- LOOP / REPORT ----------------------------------------------------------
POLL_MS = 20              # inner polling period while driving
EVENT_DWELL_MS = 800      # [ASSUMED] how long the mark/beep is held on an event
BEEP_FREQ = 880           # A5 -- carries across a classroom
BEEP_MS = 200             # [ASSUMED]

# Colour code -> name, for a readable printout (same trick as color_live.py).
NAMES = {}
for _n in dir(color):
    if not _n.startswith("_"):
        NAMES[getattr(color, _n)] = _n

T0 = time.ticks_ms()


def t_now():
    return time.ticks_diff(time.ticks_ms(), T0) / 1000.0


def yaw_deg():
    # tilt_angles()[0] is DECIDEGREES (measured 2026-08-27) and WRAPS at +/-180.
    return hub.motion_sensor.tilt_angles()[0] / 10.0


def normalize_angle(d):
    # Inline copy of src/odometry.normalize_angle(). Kept here because run.py
    # pastes ONE file and src/ is not on the hub; the mission uses the src one.
    a = d % 360.0
    if a > 180.0:
        a -= 360.0
    return a


def mark(image_name):
    # Show one built-in image by attribute name, e.g. "IMAGE_YES". Best-effort:
    # a blank matrix must never crash a moving robot.
    try:
        lm = hub.light_matrix
        lm.show_image(getattr(lm, image_name))
    except Exception:
        pass


def beep():
    # sound.beep returns an Awaitable on SPIKE 3; UNVERIFIED whether it sounds
    # at all when never awaited (see src/hub_ui.py). A silent beep loses the
    # Builder's tally, so this is a Stage-1 thing to confirm by ear.
    try:
        hub.sound.beep(BEEP_FREQ, BEEP_MS)
    except Exception:
        pass


def stop_both():
    motor.stop(LEFT_PORT)      # UNVERIFIED call site -- never run
    motor.stop(RIGHT_PORT)     # UNVERIFIED call site -- never run


def drive_forward():
    motor.run(LEFT_PORT, int(DRIVE_SPEED_DPS * LEFT_SIGN))     # UNVERIFIED call site -- never run
    motor.run(RIGHT_PORT, int(DRIVE_SPEED_DPS * RIGHT_SIGN))   # UNVERIFIED call site -- never run


def motors_ready():
    # PRE-FLIGHT, read-only, BEFORE any motion. The drive ports are hard-coded
    # (A,B measured as motors 2026-09-01) -- but a motion demo must not trust
    # that blindly: if the build moved, motor.run() would spin the wrong port.
    # LEFT vs RIGHT is NOT discoverable (both motors report device_id 48), so
    # this only confirms A and B hold a motor at all; the LEFT/RIGHT assignment
    # and the *_SIGN knobs stay a human call. motor.info() is a proven call
    # (2026-09-01); that it RAISES on an empty port is [UNVERIFIED] but inferred
    # (device.id() raises and motor.status()==5 on the empty ports). Fail SAFE:
    # any doubt -> return False -> do not move.
    ok = True
    for label, p in (("LEFT/A", LEFT_PORT), ("RIGHT/B", RIGHT_PORT)):
        try:
            motor.info(p)          # read-only; raises if the port is empty/wrong
            present = True
        except Exception:
            present = False
        print("  preflight  %-8s motor present: %s" % (label, present))
        if not present:
            ok = False
    return ok


def abort_requested():
    # LEFT hub button = our soft abort. The centre POWER button is the
    # firmware's hard stop and is not ours to poll.
    try:
        return hub.button.pressed(hub.button.LEFT) > 0
    except Exception:
        return False


def report_event(sensor_label, color_code):
    # STOP, then REPORT -- do not act on the mine. This is the line where the
    # real run would instead feed src/detector.EdgeCounter and increment the
    # one accountable count.
    stop_both()
    mark("IMAGE_YES")
    beep()
    print("  %6.1f  EVENT   sensor %s   colour=%d (%s)   -- reported, not acted on"
          % (t_now(), sensor_label, color_code, NAMES.get(color_code, "?")))
    time.sleep_ms(EVENT_DWELL_MS)


def drive_row(row_index):
    # Drive ~ROW_LENGTH_DEG of LEFT-motor rotation forward, polling BOTH colour
    # sensors. Row end is by MOTOR DEGREES only -- no boundary sensing here.
    # Returns True if the row finished, False if the operator aborted.
    print("  %6.1f  ROW %d   drive forward ~%d deg, polling C and D"
          % (t_now(), row_index, ROW_LENGTH_DEG))
    mark("IMAGE_ARROW_N")
    motor.reset_relative_position(LEFT_PORT, 0)   # UNVERIFIED call site -- (port, 0) arg form assumed
    latched = {"C": False, "D": False}
    drive_forward()
    while abs(motor.relative_position(LEFT_PORT)) < ROW_LENGTH_DEG:
        if abort_requested():
            stop_both()
            return False
        for label, p in COLOR_PORTS:
            try:
                c = color_sensor.color(p)
            except Exception:
                c = None                          # unreadable -> no event, never a fake one
            if c is not None and c in EVENT_COLORS:
                if not latched[label]:
                    latched[label] = True         # rising edge -- report once
                    report_event(label, c)
                    mark("IMAGE_ARROW_N")
                    drive_forward()               # resume the SAME row (no position reset)
            else:
                latched[label] = False            # left the note -- re-arm
        time.sleep_ms(POLL_MS)
    stop_both()
    return True


def pivot(turn_sign):
    # Spin in place ~TURN_DEG using the GYRO. Accumulate small yaw deltas
    # through normalize_angle so the +/-180 wrap is handled (exactly what
    # src/odometry does) -- a plain end-minus-start would blow up across the seam.
    print("  %6.1f  TURN    pivot %d deg (sign %d) by gyro"
          % (t_now(), int(TURN_DEG), turn_sign))
    motor.run(LEFT_PORT, int(PIVOT_SPEED_DPS * LEFT_SIGN * turn_sign))    # UNVERIFIED call site
    motor.run(RIGHT_PORT, int(-PIVOT_SPEED_DPS * RIGHT_SIGN * turn_sign)) # UNVERIFIED call site
    turned = 0.0
    prev = yaw_deg()
    while turned < TURN_DEG:
        if abort_requested():
            break
        time.sleep_ms(POLL_MS)
        now = yaw_deg()
        turned += abs(normalize_angle(now - prev))
        prev = now
    stop_both()


print("=" * 70)
print("SWEEP SKELETON -- lawnmower demo. THIS MOVES THE ROBOT.")
print("=" * 70)
print("  Prop the wheels off the desk, or give it clear floor. LEFT button aborts.")
print("  Row length is %d MOTOR DEGREES (mm not convertible yet). %d rows."
      % (ROW_LENGTH_DEG, NUM_ROWS))
print("  Colour event = built-in colour ID in %s (a stand-in for the real"
      % (tuple(NAMES.get(c, c) for c in EVENT_COLORS),))
print("  reflectance detector). On an event: stop, mark, beep, print -- no action.")
print("")
print("   t(s)   phase")
print("  " + "-" * 64)

finished = False
try:
    if not motors_ready():
        print("  %6.1f  ABORT   a drive port is not a motor -- NOT commanding motion." % t_now())
    else:
        for row in range(NUM_ROWS):
            if not drive_row(row):
                print("  %6.1f  ABORT   LEFT button -- stopping." % t_now())
                break
            if row < NUM_ROWS - 1:
                pivot(1 if row % 2 == 0 else -1)   # alternate turn direction each row end
        else:
            finished = True
finally:
    # One basic failure path: whatever happened, the wheels stop. (AB2.)
    stop_both()
    mark("IMAGE_NO") if not finished else mark("IMAGE_YES")

if finished:
    print("  %6.1f  DONE    %d rows swept." % (t_now(), NUM_ROWS))
print("")
print("WHERE THE REAL src/ CODE PLUGS IN (deliberately NOT wired up here):")
print("  * src/detector.EdgeCounter.update(reflection) replaces the colour-ID")
print("    latch above -- hysteresis, min-dwell and width-gate on reflectance,")
print("    fed by hub_color.read_reflection(), and it owns the one true count.")
print("  * src/odometry: normalize_angle() (inlined above), mm_to_degrees() to")
print("    turn ROW_LENGTH_DEG into a measured distance once the wheel is known,")
print("    and Odometry.update() to hold a pose for lane pitch / coverage.")
print("  * src/config: DRIVE_SPEED / lane_pitch_mm() / lane_count() -- and a")
print("    boundary concern (config.BOUNDARY_MODE) this skeleton refuses to do.")
print("DONE.")
