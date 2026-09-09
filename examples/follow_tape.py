# follow_tape.py -> program.py. Straddle the BLUE TAPE line and follow it; stop when it ends or corners.
# POWER-CYCLE the hub first (REPL tools kill the Hub OS), then:
#   ./hub_programmer/slot_upload.py examples/follow_tape.py --apply
#   -> hub shows "S"; UNPLUG USB, straddle the robot over the tape, tap LEFT/RIGHT, stand clear.
#   Replug when the box shows, then:
#   python3 hub_programmer/download.py --all && scripts/decode_telemetry.py
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
#
# THE GEOMETRY -- why straddling, not centring on the line:
# The two colour sensors are spaced WIDER THAN A 76 mm STICKY NOTE (MEASURED 2026-09-08: a single note
# could never be made to cover both at once), and painters tape is ~24-48 mm. So the tape FITS BETWEEN
# the sensors. The robot therefore rides with the line in the GAP and both sensors on carpet. A sensor
# seeing tape means the robot has DRIFTED THE OTHER WAY:
#     LEFT sensor (port D) sees tape  -> drifted RIGHT -> steer LEFT
#     RIGHT sensor (port C) sees tape -> drifted LEFT  -> steer RIGHT
# ⚠ SIDES MATTER ABSOLUTELY. D = LEFT and C = RIGHT, confirmed 2026-09-08 (docs/hardware/port-map.md):
# covering the left sensor drove port D from 9 to 42 and 47 on two independent runs while C stayed
# flat. Swap them and the robot steers AWAY from the line and loses it instantly. Re-run
# ./scripts/sensor-sides.py after any reassembly.
#
# WHAT v1 MEASURED, 2026-09-08 (tmp/telemetry/20260908T112501-followtape-0000360435.csv):
#     #end reason=TAPE_ENDED rows=44 corrections=0 deg=210 mm=116
#   * corrections=0 -- the tape was NEVER detected. D peaked at 35.9% blue, C at 40.8%, threshold 44.
#   * v1 then ended the run because "2 s with no tape = line ended". That rule was WRONG: while
#     straddling, seeing no tape is the NORMAL state, so it ended EVERY run after 2 s. Fixed below --
#     the run now ends only on a cap or a corner, and "no tape" is just cruising.
#   * The robot drove STRAIGHT: yaw held within 1.3 deg over 116 mm and the encoders matched to 1
#     count in 207. The drift is not motor imbalance -- it is initial misalignment plus a hand-laid
#     tape that is not straight. Hence HEADING HOLD below, which corrects heading, not wheel balance.
#   * Blue fraction RAMPS as the tape edge enters the aperture (C climbed 33 -> 40.8). A partly
#     covered sensor reads a BLEND, so 44 needs substantial coverage. 40.8 is also the carpet's own
#     measured maximum, so the threshold CANNOT safely be lowered into that band.
#
# THE TAPE RULE IS MEASURED, NOT GUESSED (docs/findings/runs/surface-survey-2026-09-08.txt):
#     blue tape  blue fraction b/(r+g+b) 0.476 - 0.496,  reflection 7 - 9
#     carpet     blue fraction up to     0.408,          reflection 3 - 9
# BLUE_FRAC_MIN sits at 0.44, inside that measured gap. This exact rule was PROVEN on hardware by
# examples/drive_to_tape.py, which drove untethered and stopped on the tape correctly.
# NOTE reflection does NOT separate tape from carpet (7-9 vs 3-9, overlapping) -- only the blue
# fraction does. That is the opposite of the MINE rule, which uses brightness and ignores tape entirely.
import time
import runloop
import motor
import color_sensor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

PL = port.A            # left motor
PR = port.B            # right motor
PC = port.C            # RIGHT-hand floor sensor  (confirmed 2026-09-08)
PD = port.D            # LEFT-hand floor sensor   (confirmed 2026-09-08)
DIRECTION = 1          # forward = A:-v, B:+v -- the twice-confirmed convention
LEFT_FWD = -1 * DIRECTION
RIGHT_FWD = 1 * DIRECTION

BASE_DPS = 80          # slower than the 100 used for straight runs: steering needs reaction time
TURN_DPS = 45          # how much the inside wheel is slowed to steer. Bang-bang, not proportional --
                       # a P controller needs a tuned gain we have no measurement for yet.
MAX_DEG = 40000        # hard distance cap, ~22 m -- enough for several laps of a small
                       # rectangle. The point of the demo is to keep going round, so the
                       # cap is a runaway backstop, not the end of the run.
RUN_CAP_MS = 150000    # hard time cap, 2.5 min. A lap of a small rectangle at ~44 mm/s is
                       # roughly 45-90 s, so this allows a lap or two plus corners.
ARM_TIMEOUT_MS = 90000
COUNTDOWN_S = 5
TICK_MS = 50           # 20 Hz -- MEASURED sustainable while driving and logging

BLUE_FRAC_MIN = 0.44   # MEASURED gap: carpet max 0.408 -> tape min 0.476
# ⚠ MINIMUM CHANNEL SUM -- the highest-value guard in this file, added 2026-09-09.
# on_tape() previously rejected only `tot <= 0`, so a reading of r=0,g=1,b=3 returns a blue fraction
# of 0.75 and votes TRUE. MEASURED in our own corpus: run 0000153852 port D has a SIX-tick sustained
# run and run 0000312454 port C a FIVE-tick run in which EVERY tick had r+g+b < 40 -- both long
# enough to fire CORNER_SUSTAIN and command a 90 degree turn on pure sensor dropout. Worse, run
# 0000043283 (the one the corner-side rule was fitted against) had port D fire exactly ONCE in 188
# rows and that firing was a sub-40 total. Tape totals are 124-135 and carpet 49-107, so a floor of
# 40 excludes neither real class -- it excludes only noise.
MIN_CHANNEL_SUM = 40
BOTH_TICKS = 2         # both sensors blue at once -- still a corner, but MEASURED to be rare
# A CORNER IS A SUSTAINED RUN ON ONE SENSOR, not a simultaneous hit on both. MEASURED 2026-09-08
# (tmp/telemetry/20260908T120015-followtape-0001250307.csv): at the corner port D held tape for TEN
# consecutive ticks (seq 93-102) before port C joined at seq 103. During ordinary line-bounce a
# sensor only GRAZES the tape for a tick or two. Requiring both sensors at once missed corners
# entirely -- the next run logged corners=0 with 49 tape sightings. The sustained side is also the
# side the corner turns toward, because the perpendicular leg extends only one way.
CORNER_SUSTAIN = 4     # consecutive ticks on ONE sensor to call it a corner (~0.2 s at 20 Hz).
                       # MEASURED: a real corner held C for 5 ticks (run 0000043283, seq 89-93) and D
                       # for 10 in an earlier run, while ordinary line-bounce grazes for ONE tick
                       # (that run had 8 tape sightings total, 5 of them the corner). 4 catches a
                       # shorter corner without reaching into single-tick bounce territory.
# ⚠ TURN SIGN -- MEASURED 2026-09-08, not inferred. Run 0000043283 logged:
#     TURN_START_want900_from17   ->   TURN_END_at-955_delta-972_want900
# A commanded +900 produced a yaw delta of MINUS 972, and the operator saw the robot turn away from
# the corner "into the void". So the motor pairing for a positive command is the opposite of what
# motor_poc.py turn direction implied. One constant carries the correction so the geometry above
# stays readable.
# Which way a corner turns, given which sensor held the tape. MEASURED 2026-09-08 by OBSERVATION,
# twice: with +1 (sustained-LEFT -> turn LEFT, the "obvious" reading) the robot turned AWAY from the
# corner every time, even after the spin directions themselves were proven correct by
# examples/calibrate_directions.py. So the physical relationship is the opposite of the intuitive one
# for this straddling geometry, and the honest thing is to record what was SEEN rather than to keep
# arguing from a diagram. -1 means: sustained on the LEFT sensor -> turn RIGHT.
# CORRECTED 2026-09-09 back to +1: TURN TOWARD THE SENSOR THAT SAW THE LEG.
# The geometry admits no alternative -- at a corner the outgoing leg occupies only ONE side of the
# incoming centreline, so only the sensor on that side can lie in it. Sustained on port D (LEFT)
# means the leg goes LEFT. The -1 was fitted on 2026-09-08 against run 0000043283, in which port D
# fired exactly once in 188 rows on a sub-40 channel total -- i.e. against NOISE, not a corner (see
# MIN_CHANNEL_SUM above, now added). With the noise guard in place that evidence evaporates, so the
# empirical fit is withdrawn and the geometry stands.
CORNER_SIDE_SIGN = 1
TURN_SIGN = 1          # MEASURED 2026-09-08 by examples/calibrate_directions.py: the operator
                       # WATCHED -1 turn the wrong way on both spins. Same motor pairing as
                       # src/hub_drive.py, so the same value. Forward/backward were confirmed correct.
# Turns OVERSHOOT: commanded 900, achieved 972 -- 72 ddeg (7.2 deg) past target, because the loop
# breaks on the threshold and the robot then coasts. Stop that much early. MEASURED on the same run;
# it is ONE sample, so re-check it against TURN_END_ lines before trusting it further.
# MEASURED n=6 (run 0000456461): commanded 900 with TURN_LEAD 70 (target 830) achieved +866, -853,
# -881, +840, -860, -846 -- mean magnitude 857.7, i.e. 27.7 ddeg PAST the 830 target. So the coast is
# ~28 ddeg, not 72, and the old 70 made every turn UNDERSHOOT the commanded angle by ~42 ddeg. One
# loop tick of latency at ~50 ms and ~48 deg/s is ~24 ddeg, which matches: it is latency, not momentum.
TURN_LEAD_DDEG = 28
# ⚠ THE CORNER TURN IS AN ARC, NOT A PIVOT. This is the fix for the failure the operator watched:
# the robot detected the corner, turned the right way, and still lost the tape, because a PIVOT is
# the arc formula with the sensor-ahead distance silently set to zero -- it assumes the sensors sit
# on the wheel axis, and they do not.
#   MASTER EQUATION (derived and numerically verified to <1e-9 mm over A in {40,60,90},
#   S in {80,140}, theta in {45..135}):
#       miss e = X_v*sin(theta) - R*(1 - cos(theta))        ->        R* = X_v * cot(theta/2)
#   where X_v is the distance from the WHEEL-AXIS MIDPOINT to the corner vertex when the turn is
#   commanded. At theta = 90 this is simply R* = X_v. A pivot is R = 0, so e = X_v*sin(theta): the
#   robot misses the new leg by one whole sensor-ahead distance, worst at exactly 90 degrees.
#   Sensor SPACING and sensor AHEAD both cancel out of e exactly -- only X_v and R matter.
#
# WHY 65 mm IS SAFE WITHOUT THE RULER: a fixed R survives every X_v within +/-(S-W)/2 of it, where
# S is the sensor spacing and W the tape width. At S = 80 mm (the tightest value consistent with the
# MEASURED "wider than a 76 mm note") and W = 25.4 mm, R = 65 survives X_v in [37.7, 92.3] -- which
# covers the whole plausible sensor-ahead range. Measuring S turns a survivable guess into a centred
# one, but Thursday does not have to wait for it.
CORNER_TURN_RADIUS_MM = 65.0
TRACK_WIDTH_MM = 95.0  # MEASURED 2026-09-03, effective (folds in caster drag). Mirrors config.py.
# ⚠ AT 180 DEGREES A PIVOT IS EXACTLY RIGHT, and that is a theorem not a heuristic: sin(180) = 0, so
# X_v drops out and e = -2R. R = 0 is the unique correct answer for ANY geometry. So the dead-end
# U-turn keeps using a spin, while the corner turn uses the arc above.
CORNER_TURN_DDEG = 900 # [ASSUMED] 90 deg. Demo day may not be square -- v3 should MEASURE the angle
                       # from the heading change instead of assuming it. Gyro-closed, as motor_poc proved.
CORNER_LOCKOUT_MS = 1500  # after counting a corner, ignore blue for this long so one corner cannot be
                       # counted several times while the robot is still turning off it.
MAX_CORNERS = 9        # the matrix shows ONE digit, so 9 is the honest ceiling. A rectangle
                       # lap is 4 corners, so 9 proves two full laps and part of a third.
                       # DIRECTION-AGNOSTIC BY CONSTRUCTION: the robot turns toward whichever
                       # sensor holds tape, so starting it the other way round traverses the
                       # rectangle the other way with NO code change. That is the real proof.

# --- heading hold -------------------------------------------------------------------------------
# v1 MEASURED that the wheels are balanced (207 vs 206 encoder counts) and yaw held within 1.3 deg,
# so the robot does not need wheel trim -- it needs to hold a HEADING against an unstraight line and
# an imperfect start. This is a proportional correction on the gyro, the smallest thing that helps.
HOLD_KP = 0.4          # [ASSUMED] dps of wheel correction per decidegree of heading error. A 5 deg
                       # (50 ddeg) error gives 20 dps of correction. TUNE against a logged run.
HOLD_MAX_DPS = 30      # clamp, so a gyro glitch cannot command a spin
# SIGN -- MEASURED 2026-09-08, the hard way. v2 ran with HOLD_SIGN = +1 and the robot DROVE IN
# CIRCLES for the whole 40 s run (tmp/telemetry/20260908T114003-followtape-0000102164.csv):
#   #end reason=time_cap corners=3 rows=670 corrections=89 tape_seen=89 hold=477 deg=3842 mm=2129
#   left encoder moved 3807 deg against the right's 1490 -- a FIXED 2.55:1 ratio for the entire
#   run, and a saturated correction predicts (80+30)/(80-30) = 2.2. So the correction pinned at its
#   clamp in ONE direction and stayed there: POSITIVE feedback. Yaw wrapped +/-180 repeatedly.
# Therefore the yaw sign is the opposite of what motor_poc.py's turn direction implied. -1 is correct.
HOLD_SIGN = -1
# Divergence guard: if the correction sits at its clamp in the same direction for this many ticks,
# the loop is running away, not correcting. Disable the hold and drive straight rather than spiral --
# a robot that drives straight is recoverable, one that circles for 40 s is a wasted run. The event
# is recorded in the #end trailer so a silent fallback cannot be mistaken for a healthy run.
HOLD_DIVERGE_TICKS = 20
# ⚠ THE SATURATION COUNTER ALONE CANNOT CATCH A RUNAWAY, found by inspection 2026-09-09. `hold_ref`
# is re-taken from the current yaw on EVERY tape sighting (89 sightings in the 670-row circling run),
# which re-zeroes the error and resets the saturation count -- so the guard above could NEVER have
# fired on the very run it was written for. A runaway is better detected by its SIGNATURE: the robot
# turning a long way while seeing no tape. On a line you are following, that cannot happen.
# (For the record, the runaway radius is R = (track/2)*base/clamp = 47.5*80/30 = 127 mm, which is the
# ~0.8 m circle the operator watched.)
HOLD_DIVERGE_DDEG = 900   # net heading change since the last tape sighting that means "circling"

S_GLYPH = (0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0)
BOX = (1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1)
FULL = (1,) * 25
LEFTA = (0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0)
RIGHTA = (0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
CORNER = (1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0)
# 3x5 digits padded into the 5x5, same font as src/hub_ui.py. A DIGIT, not a pixel tally: a misread
# digit is obviously a misread, whereas a miscounted tally looks like an answer.
DIGITS = (
    (0,1,1,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,1,1,0),
    (0,0,1,0,0, 0,1,1,0,0, 0,0,1,0,0, 0,0,1,0,0, 0,1,1,1,0),
    (0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0),
    (0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0),
    (0,1,0,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,0,0,1,0),
    (0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0),
    (0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0),
    (0,1,1,1,0, 0,0,0,1,0, 0,0,0,1,0, 0,0,0,1,0, 0,0,0,1,0),
    (0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0),
    (0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0),
)
HEADER = ("seq,t_ms,phase,relA_deg,relB_deg,velL,velR,statusL,statusR,"
          "yaw_ddeg,accx_mg,accy_mg,accz_mg,reflC_pct,rC,gC,bC,iC,reflD_pct,rD,gD,bD,iD,reason")


class StopRun(Exception):
    pass


def show(pattern):
    light_matrix.show([100 if v else 0 for v in pattern])


def tapped():
    try:
        return button.pressed(button.LEFT) > 0 or button.pressed(button.RIGHT) > 0
    except Exception:
        return False


def none_ok(fn):
    try:
        return fn()
    except Exception:
        return None


def beep(hz, ms):
    try:
        import hub
        hub.sound.beep(hz, ms, 20)
    except Exception:
        pass                      # [UNVERIFIED] signature; a silent hub must not fail the run


def on_tape(rgbi_sample):
    """True when this reading is the blue tape. False (not None) when unreadable.

    A failed read must never be treated as tape -- that would steer the robot on no evidence.
    """
    if rgbi_sample is None or rgbi_sample[0] is None:
        return False
    tot = rgbi_sample[0] + rgbi_sample[1] + rgbi_sample[2]
    if tot < MIN_CHANNEL_SUM:
        return False            # too little light for a ratio to mean anything -- NOT a tape vote
    return (float(rgbi_sample[2]) / tot) >= BLUE_FRAC_MIN


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: straddle the robot over the tape, then tap LEFT or RIGHT")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if tapped():
            return True
        await runloop.sleep_ms(50)
    return False


async def countdown():
    for s in range(COUNTDOWN_S, 0, -1):
        show(FULL if (s % 2) else BOX)
        print("COUNTDOWN %d" % s)
        await runloop.sleep_ms(1000)


async def follow():
    log = CsvLog(HEADER, prefix="followtape", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    box = {"seq": 0, "both": 0, "corners": 0, "corrections": 0, "seen": 0,
           "hold": 0, "lockout_until": 0, "sat": 0, "hold_off": False, "diverged": 0,
           "first_side": 0, "first_at": 0, "run_d": 0, "run_c": 0, "note": "",
           "yaw_at_sighting": None}

    def sample(phase):
        """Log one row; return (left_on_tape, right_on_tape, yaw_ddeg)."""
        t = time.ticks_diff(time.ticks_ms(), t0)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        yaw = none_ok(lambda: motion_sensor.tilt_angles()[0])
        row = (box["seq"], t, phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               yaw, acc[0], acc[1], acc[2],
               none_ok(lambda: color_sensor.reflection(PC)), cc[0], cc[1], cc[2], cc[3],
               none_ok(lambda: color_sensor.reflection(PD)), cd[0], cd[1], cd[2], cd[3],
               box["note"])
        box["note"] = ""                       # one-shot: an event marks exactly the tick it happened
        log.append(",".join("" if v is None else str(v) for v in row))
        box["seq"] += 1
        return (on_tape(cd), on_tape(cc), yaw)      # LEFT = port D, RIGHT = port C

    def guard():
        if tapped():
            raise StopRun("STOP_button")
        if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
            raise StopRun("time_cap")

    def drive(left_dps, right_dps):
        motor.run(PL, LEFT_FWD * int(left_dps))
        motor.run(PR, RIGHT_FWD * int(right_dps))

    def norm_ddeg(d):
        """Yaw WRAPS at +/-180 deg (MEASURED, imu-characterisation-2026-08-27). Every delta goes
        through here or a heading error of 1 deg reads as 359."""
        return ((d + 1800) % 3600) - 1800

    async def gyro_turn(ddeg, radius_mm=0.0):
        """Spin in place until the GYRO heading has changed by |ddeg|. Gyro-closed, so it does NOT
        depend on TRACK_WIDTH_MM -- the trick examples/motor_poc.py proved on this hardware."""
        y0 = none_ok(lambda: motion_sensor.tilt_angles()[0])
        if y0 is None:
            box["note"] = "TURN_ABORT_NO_YAW"
            return
        box["note"] = "TURN_START_want%d_from%d" % (ddeg, y0)
        # SIGN HONOURED, and corrected by the MEASURED TURN_SIGN (see its comment above).
        way = TURN_SIGN if ddeg > 0 else -TURN_SIGN
        if radius_mm <= 0.0:
            # Spin in place. Correct at 180 degrees (dead-end U-turn), wrong at a corner.
            motor.run(PL, LEFT_FWD * BASE_DPS * way)
            motor.run(PR, -RIGHT_FWD * BASE_DPS * way)
        else:
            # ARC. The outer wheel covers (R + track/2) while the inner covers (R - track/2) over the
            # same angle, so their speeds are in that ratio. Both wheels drive FORWARD, which is what
            # translates the sensor pair onto the new leg instead of spinning under it.
            half = TRACK_WIDTH_MM / 2.0
            inner = BASE_DPS * (radius_mm - half) / radius_mm
            outer = BASE_DPS * (radius_mm + half) / radius_mm
            if inner < 0.0:
                inner = 0.0          # R < track/2 would need the inner wheel to reverse; clamp
            # ddeg > 0 is a RIGHT turn once TURN_SIGN is applied, so the LEFT wheel is the outer one.
            left, right = (outer, inner) if way > 0 else (inner, outer)
            motor.run(PL, LEFT_FWD * left)
            motor.run(PR, RIGHT_FWD * right)
        t_turn = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t_turn) < 6000:      # bounded: never spin forever
            y = none_ok(lambda: motion_sensor.tilt_angles()[0])
            # Stop TURN_LEAD_DDEG early: the robot coasts past the break condition by a measured
            # ~72 ddeg. Guard the subtraction so a small commanded turn cannot become a negative
            # target, which would break instantly and turn not at all.
            target = abs(ddeg) - TURN_LEAD_DDEG
            if target < 100:
                target = abs(ddeg)
            if y is not None and abs(norm_ddeg(y - y0)) >= target:
                break
            sample("turn")
            await runloop.sleep_ms(TICK_MS)
        motor.stop(PL)
        motor.stop(PR)
        # The TRUE end heading after the motors are cut -- turn precision is (achieved - wanted), and
        # it cannot be read from the last in-loop sample because the robot coasts past it.
        await runloop.sleep_ms(200)
        y1 = none_ok(lambda: motion_sensor.tilt_angles()[0])
        if y1 is not None:
            box["note"] = "TURN_END_at%d_delta%d_want%d" % (y1, norm_ddeg(y1 - y0), ddeg)
        sample("turn")

    reason = "time_cap"
    l0 = 0
    try:
        l0 = motor.relative_position(PL)
        hold_ref = none_ok(lambda: motion_sensor.tilt_angles()[0]) or 0
        drive(BASE_DPS, BASE_DPS)
        show(DIGITS[0])
        while True:
            guard()
            if abs(motor.relative_position(PL) - l0) >= MAX_DEG:
                reason = "distance_cap"
                break

            left_tape, right_tape, yaw = sample("follow")
            locked = time.ticks_diff(time.ticks_ms(), box["lockout_until"]) < 0

            # Consecutive-tick runs per sensor. A GRAZE during normal bouncing is 1-2 ticks; a
            # CORNER is a sustained run because the robot is riding along the perpendicular leg.
            box["run_d"] = box["run_d"] + 1 if left_tape else 0
            box["run_c"] = box["run_c"] + 1 if right_tape else 0
            sustained = (box["run_d"] >= CORNER_SUSTAIN) or (box["run_c"] >= CORNER_SUSTAIN)
            # Turn toward the sensor with the LONGER run -- that is the side the leg extends to.
            box["first_side"] = CORNER_SIDE_SIGN * (-1 if box["run_d"] >= box["run_c"] else 1)

            if ((left_tape and right_tape) or sustained) and not locked:
                # Both sensors blue at once. The tape is ~25 mm and the sensors are >76 mm apart, so
                # this cannot happen on a straight line -- it is tape MEETING tape: a corner or a cross.
                box["both"] += 1
                if sustained or box["both"] >= BOTH_TICKS:
                    box["corners"] += 1
                    box["both"] = 0
                    box["dirs"] = box.get("dirs", "") + ("L" if box["first_side"] < 0 else "R")
                    box["note"] = ("CORNER%d_%s_runD%d_runC%d"
                                   % (box["corners"], "L" if box["first_side"] < 0 else "R",
                                      box["run_d"], box["run_c"]))
                    # LOG IT IMMEDIATELY. The note is one-shot and gyro_turn() overwrites it with
                    # TURN_START before any sample() runs, which is why NO csv in the whole corpus
                    # contains a CORNER row and why the side question could never be settled from
                    # telemetry. Found by inspection 2026-09-09.
                    sample("follow")
                    show(DIGITS[min(box["corners"], 9)])
                    beep(880, 100)
                    if box["corners"] >= MAX_CORNERS:
                        reason = "MAX_CORNERS"
                        break
                    # Turn onto the new leg, TOWARD whichever sensor saw blue first. Falls back to
                    # +90 (right) only if nothing was latched, which should not happen.
                    motor.stop(PL)
                    motor.stop(PR)
                    way = box["first_side"] if box["first_side"] != 0 else 1
                    await gyro_turn(CORNER_TURN_DDEG * way, CORNER_TURN_RADIUS_MM)
                    box["first_side"] = 0
                    box["run_d"] = 0
                    box["run_c"] = 0
                    hold_ref = none_ok(lambda: motion_sensor.tilt_angles()[0]) or hold_ref
                    box["sat"] = 0
                    box["hold_off"] = False      # fresh datum on the new leg: give the hold another go
                    box["lockout_until"] = time.ticks_add(time.ticks_ms(), CORNER_LOCKOUT_MS)
                    drive(BASE_DPS, BASE_DPS)
                    continue
                drive(BASE_DPS, BASE_DPS)

            elif left_tape and not locked:
                # LEFT sensor (D) on tape -> drifted RIGHT -> steer LEFT by slowing the left wheel.
                # This is the "line bounce": the robot rides between the two edges rather than
                # tracking a centre it cannot see, because the tape fits BETWEEN the sensors.
                box["both"] = 0
                box["seen"] += 1
                box["corrections"] += 1
                box["yaw_at_sighting"] = yaw
                show(LEFTA)
                drive(TURN_DPS, BASE_DPS)
                hold_ref = yaw if yaw is not None else hold_ref     # the line, not the old heading,
                                                                    # is the authority once seen
            elif right_tape and not locked:
                box["both"] = 0
                box["seen"] += 1
                box["corrections"] += 1
                box["yaw_at_sighting"] = yaw
                show(RIGHTA)
                drive(BASE_DPS, TURN_DPS)
                hold_ref = yaw if yaw is not None else hold_ref
            else:
                # Neither sensor sees tape. While straddling this is the NORMAL cruising state -- v1
                # wrongly treated it as "line lost" and ended every run after 2 s. Hold the heading
                # instead, so the robot tracks straight between bounces rather than wandering off.
                box["both"] = 0
                if yaw is not None and not box["hold_off"]:
                    err = norm_ddeg(yaw - hold_ref)
                    corr = HOLD_SIGN * HOLD_KP * err
                    if corr >= HOLD_MAX_DPS:
                        corr = HOLD_MAX_DPS
                        box["sat"] = box["sat"] + 1 if box["sat"] >= 0 else 1
                    elif corr <= -HOLD_MAX_DPS:
                        corr = -HOLD_MAX_DPS
                        box["sat"] = box["sat"] - 1 if box["sat"] <= 0 else -1
                    else:
                        box["sat"] = 0
                    # Turned a long way without seeing the line = circling. This is the check that
                    # actually works; the saturation count below is kept as a second, weaker signal.
                    if (box["yaw_at_sighting"] is not None and yaw is not None
                            and abs(norm_ddeg(yaw - box["yaw_at_sighting"])) >= HOLD_DIVERGE_DDEG):
                        box["hold_off"] = True
                        box["diverged"] += 1
                        box["note"] = "HOLD_OFF_circling"
                        beep(220, 300)
                    # Stuck at the clamp in ONE direction = running away, not correcting.
                    if abs(box["sat"]) >= HOLD_DIVERGE_TICKS:
                        box["hold_off"] = True
                        box["diverged"] += 1
                        beep(220, 300)          # audible: the operator should know it gave up
                    box["hold"] += 1
                    drive(BASE_DPS - corr, BASE_DPS + corr)
                else:
                    drive(BASE_DPS, BASE_DPS)
                show(DIGITS[min(box["corners"], 9)])

            await runloop.sleep_ms(TICK_MS)
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        motor.stop(PL)
        motor.stop(PR)
        for _ in range(4):                        # capture the true stopping point, motors cut
            sample("stopped")
            await runloop.sleep_ms(100)
        travelled = abs((none_ok(lambda: motor.relative_position(PL)) or l0) - l0)
        mm = travelled / 360.0 * 199.49           # 63.5 mm wheel, MEASURED 2026-09-03
        log.append("#end reason=%s corners=%d dirs=%s rows=%d corrections=%d tape_seen=%d hold=%d diverged=%d deg=%d mm=%d"
                   % (reason, box["corners"], box.get("dirs", ""), box["seq"], box["corrections"],
                      box["seen"], box["hold"], box["diverged"], travelled, int(mm)))
        log.close()
        show(DIGITS[min(box["corners"], 9)])      # leave the COUNT on the matrix, not a done-glyph
        beep(1320, 250)
        print("FOLLOW_TAPE done: %s corners=%d rows=%d corrections=%d tape_seen=%d %d deg (~%d mm) -> %s"
              % (reason, box["corners"], box["seq"], box["corrections"], box["seen"],
                 travelled, int(mm), log.path))


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    await countdown()
    await follow()


runloop.run(main())
