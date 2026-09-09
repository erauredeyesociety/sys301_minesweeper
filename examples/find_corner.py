# find_corner.py -> program.py. Find the blue boundary tape, WALK ALONG IT BY REPEATED TOUCHES, and
# report a CORNER as a measured angle.
# ./hub_programmer/slot_upload.py examples/find_corner.py --apply  -> hub shows "S"; UNPLUG USB, set
# the robot on the carpet a few hundred mm from the tape FACING IT, tap LEFT/RIGHT, stand clear.
# Replug when the box shows, then:
#   python3 hub_programmer/download.py --all && scripts/decode_telemetry.py
# NOTE: run.py/probes send Ctrl-C which KILLS the Hub OS; POWER-CYCLE the hub before a slot upload.
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
# Runbook: docs/runbooks/corner-demo.md   Design: docs/plans/border-trace-and-corners-2026-09-08.md
#
# WHY TOUCH-STITCHING AND NOT LINE FOLLOWING
# docs/plans/minimalism-contract-2026-09-03.md section 4 item 4 rules OUT a line-following control law:
# the ~25 mm colour-sensor mount wobble (docs/findings/colour-sensor-mounting-wobble-2026-09-03.md)
# is the same size as the tape, so an on/off steering signal can be wrong, not merely noisy. This
# program therefore never tries to STAY on the tape. It repeats the ONE primitive that is PROVEN on
# hardware -- drive straight until the tape rule fires twice (examples/drive_to_tape.py, untethered on
# battery 2026-09-08, "#end reason=TAPE_DETECTED rows=53 deg=281 mm=155") -- angling into the boundary,
# backing off, and doing it again. Each touch is a fresh ABSOLUTE fix on the boundary, so nothing
# accumulates across the run and a wandering hand-laid edge is re-aimed at from the last two touches.
#
# THE CORNER DEFINITION (see the plan doc, section 3): a corner is a SUSTAINED, SIGN-CONSISTENT change
# in the BEARING BETWEEN CONSECUTIVE BOUNDARY TOUCH POINTS. It is NOT read off the gyro while turning:
# the only turn data this project owns (the 1 ft square, 2026-09-03) shows two gyro reads milliseconds
# apart disagreeing by 3.8-6.5 deg DURING rotation. Every heading used here is read while STOPPED and
# settled, exactly as examples/motor_poc.py does it.
#
# THE TAPE RULE IS MEASURED (docs/findings/runs/surface-survey-2026-09-08.txt, 2026-09-08, this mount):
#     blue tape   b/(r+g+b) = 0.476 - 0.496,  total 124-135,  builtin color() = BLUE on 149/149
#     carpet      b/(r+g+b) = 0.333 - 0.408,  total  49-107,  builtin color() = BLACK / UNKNOWN
#     notes       b/(r+g+b) = 0.291 - 0.300,  total 263-1715  (a mine can never trip the tape rule)
# BLUE_FRAC_MIN = 0.44 sits inside the measured gap 0.408 -> 0.476, on neither edge.
#
# The CSV HEADER is byte-identical to examples/motor_poc.py so scripts/decode_telemetry.py needs no
# change -- IMU, both encoders, both colour sensors, every tick.
import math
import time
import runloop
import motor
import color_sensor
import color
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

PL = port.A            # left motor
PR = port.B            # right motor
PC = port.C
PD = port.D
# DIRECTION: forward = A:-v, B:+v. The recorded convention, and CONFIRMED TWICE (motor_poc 2026-09-01;
# again 2026-09-08 when a run flipped to -1 drove BACKWARD and the operator confirmed the original
# sign). Do not flip without watching the robot move.
DIRECTION = 1
LEFT_FWD = -1 * DIRECTION
RIGHT_FWD = 1 * DIRECTION

# ---- which way round the box -------------------------------------------------------------------
# SIDE = +1 turns RIGHT off the first touch (tape ends up on the robot's LEFT); -1 turns LEFT.
# THE OPERATOR SETS THIS BEFORE THE RUN. The program must not guess which way round the box to walk.
SIDE = 1               # [OPERATOR SETS]

# ---- speeds and rates --------------------------------------------------------------------------
SPEED_DPS = 100        # ~55 mm/s at the MEASURED 63.5 mm wheel. The only speed ever driven on carpet.
TURN_DPS = 100         # spin turn; ~67 deg/s [COMPUTED from the MEASURED 95 mm track]
TICK_MS = 50           # 20 Hz, MEASURED sustained while driving + logging + reading both sensors
FLUSH_EVERY = 25       # CsvLog default is 10; the flush costs a MEASURED ~40-60 ms, so push it out
MM_PER_DEG = 199.49 / 360.0   # 63.5 mm wheel -> 199.49 mm/rev, MEASURED 2026-09-03

# ---- detection ---------------------------------------------------------------------------------
BLUE_FRAC_MIN = 0.44   # MEASURED gap: carpet max 0.408 -> tape min 0.476
CONSEC_NEEDED = 2      # PROVEN in drive_to_tape.py; one noisy sample must not stop the robot
SAT_MAX = 1000         # any of r,g,b >= 1000 means the sensor is TOUCHING the surface and the ratios
                       # have collapsed to 33/33/33 (MEASURED). NOTE: r,g,b ONLY -- the i channel
                       # legitimately reaches 1022 over a pink note (find_note run 2026-09-08).
MIN_CHAN_SUM = 40      # low-light floor. MEASURED carpet total is 49-107; below 40 the blue fraction
                       # is quantisation garbage (a 1,1,2 read gives exactly 0.500). Nobody had a
                       # floor guard before; the darkest carpet leaves only ~1 LSB of margin.

# ---- geometry of one stitch --------------------------------------------------------------------
STITCH_DEG = 30        # [ASSUMED] angle to the edge on each approach and retreat
RETREAT_DEG = 217      # ~120 mm [COMPUTED]; perpendicular standoff 120*sin30 = 60 mm
APPROACH_CAP_DEG = 500 # ~277 mm [COMPUTED]; >2x the ~120 mm an approach should need. Hitting this
                       # cap means the edge fell away -> LOST, which is a RESULT, not a crash.
SEEK_CAP_DEG = 2000    # ~1100 mm
CLEAR_CAP_DEG = 400    # reverse cap if the robot is armed already sitting on the tape
MAX_TOUCH = 7          # bounded: at ~208 mm of advance per stitch [COMPUTED] this walks ~1.2 m
CORNER_MIN_DEG = 45    # [ASSUMED] 13-16x the MEASURED 2.6 deg yaw wander over a 155 mm run
WIGGLE_MAX_DEG = 25    # [ASSUMED] below this a bearing change is hand-laid wander, not a corner
COUNTDOWN_S = 5
ARM_TIMEOUT_MS = 90000
RUN_CAP_MS = 120000
SETTLE_TICKS = 3       # 3 samples x 100 ms, exactly motor_poc.settle()

S_GLYPH = (0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0)
BOX = (1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1)
FULL = (1,) * 25
XMARK = (1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1)   # CORNER
DASH = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)    # straight EDGE
QMARK = (0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0)   # FAULT
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
        pass                      # [UNVERIFIED] signature on SPIKE 3; silence must not fail the run


def norm_deg(d):
    """Wrap to (-180, 180]. Yaw wraps at +/-180 -- MEASURED, imu-characterisation-2026-08-27."""
    return ((d + 180.0) % 360.0) - 180.0


def is_blue(rgbi_sample, color_code):
    """True when THIS sensor sees the boundary tape. Two independent votes, either suffices.

    Each sensor is tested against its OWN absolute threshold and reduced to a boolean. The two are
    never compared to each other: port D reads systematically bluer than C on the same surface
    (surface-survey-2026-09-08), so a differential rule would bias permanently toward D.

    Returns False (not None) on an unreadable, saturated or too-dark sample: a missing read is not a
    boundary and must never stop the robot on its own.
    """
    if rgbi_sample is None or rgbi_sample[0] is None:
        return color_code == color.BLUE
    r, g, b = rgbi_sample[0], rgbi_sample[1], rgbi_sample[2]
    if r >= SAT_MAX or g >= SAT_MAX or b >= SAT_MAX:
        return False              # touching the surface; ratios collapsed to 33/33/33
    tot = r + g + b
    if tot < MIN_CHAN_SUM:
        return False              # too dark to have a meaningful ratio
    if color_code == color.BLUE:
        return True               # PROVEN vote: BLUE on 149/149 tape samples, never once on carpet
    return (float(b) / tot) >= BLUE_FRAC_MIN


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: robot on carpet, a few hundred mm from the tape, FACING IT. Tap LEFT or RIGHT.")
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


async def find_corner():
    log = CsvLog(HEADER, prefix="findcorner", now_ms=time.ticks_ms(), flush_every=FLUSH_EVERY)
    t0 = time.ticks_ms()
    st = {"seq": 0, "x": 0.0, "y": 0.0, "hdg": 0.0,      # pose, mm and degrees, origin = first touch
          "touches": 0, "turn_sum": 0.0, "prev_brg": None, "corner": 0.0, "edge": 0.0}

    def sample(phase):
        """Log one full row; return True when EITHER sensor sees tape on THIS tick."""
        t = time.ticks_diff(time.ticks_ms(), t0)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        code_c = none_ok(lambda: color_sensor.color(PC))
        code_d = none_ok(lambda: color_sensor.color(PD))
        row = (st["seq"], t, phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
               none_ok(lambda: color_sensor.reflection(PC)), cc[0], cc[1], cc[2], cc[3],
               none_ok(lambda: color_sensor.reflection(PD)), cd[0], cd[1], cd[2], cd[3], "")
        log.append(",".join("" if v is None else str(v) for v in row))
        st["seq"] += 1
        return is_blue(cc, code_c) or is_blue(cd, code_d)

    def guard():
        if tapped():
            raise StopRun("STOP_button")
        if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
            raise StopRun("time_cap")

    def yaw_deg():
        y = none_ok(lambda: motion_sensor.tilt_angles()[0])
        return None if y is None else y / 10.0        # decidegrees, MEASURED 2026-08-27

    async def settle(phase):
        """Stop, then read the heading STILL. Every angle this program reports comes from here."""
        acc = 0.0
        n = 0
        for _ in range(SETTLE_TICKS):
            sample(phase)
            y = yaw_deg()
            if y is not None:
                acc += y
                n += 1
            await runloop.sleep_ms(100)
        if n == 0:
            return st["hdg"]
        st["hdg"] = acc / n
        return st["hdg"]

    async def turn_to(target, phase):
        """Gyro-closed turn to an ABSOLUTE heading. Absolute, not relative +/-90, so each turn
        cancels the previous leg's heading error instead of accumulating it."""
        y0 = yaw_deg()
        if y0 is None:
            raise StopRun("gyro_none")
        delta = norm_deg(target - y0)
        if abs(delta) < 2.0:
            return await settle(phase)
        s = 1 if delta > 0 else -1
        motor.run(PL, LEFT_FWD * TURN_DPS * s)
        motor.run(PR, -RIGHT_FWD * TURN_DPS * s)
        while True:
            guard()
            y = yaw_deg()
            if y is not None and abs(norm_deg(y - y0)) >= abs(delta):
                break
            sample(phase)
            await runloop.sleep_ms(TICK_MS)
        motor.stop(PL)
        motor.stop(PR)
        return await settle(phase)

    async def drive(cap_deg, phase, want_tape, back=False):
        """Drive cap_deg, or stop early on the tape rule. want_tape: True = stop when the tape is
        seen CONSEC_NEEDED times; False = stop when it is NOT seen CONSEC_NEEDED times; None = drive
        the whole cap_deg blind (the retreat leg, which is a fixed geometric standoff).

        Returns (mm_travelled, saw_tape). Pose is integrated ONCE per leg from the settled heading,
        not per tick -- a straight leg here is <300 mm and yaw wander was MEASURED at ~2.6 deg over
        155 mm, so per-tick integration would buy nothing and cost memory.
        """
        d = -1 if back else 1
        motor.run(PL, LEFT_FWD * SPEED_DPS * d)
        motor.run(PR, RIGHT_FWD * SPEED_DPS * d)
        l0 = motor.relative_position(PL)
        hits = 0
        saw = False
        while True:
            guard()
            if abs(motor.relative_position(PL) - l0) >= cap_deg:
                break
            blue = sample(phase)
            if want_tape is None:
                hits = 0
            elif want_tape and blue:
                hits += 1
                if hits >= CONSEC_NEEDED:
                    saw = True
                    break
            elif (not want_tape) and (not blue):
                hits += 1
                if hits >= CONSEC_NEEDED:
                    saw = False
                    break
            else:
                hits = 0
            await runloop.sleep_ms(TICK_MS)
        motor.stop(PL)
        motor.stop(PR)
        travelled = abs((none_ok(lambda: motor.relative_position(PL)) or l0) - l0)
        mm = travelled * MM_PER_DEG * d
        h = math.radians(st["hdg"])
        st["x"] += mm * math.cos(h)
        st["y"] += mm * math.sin(h)
        return (mm, saw)

    def record_touch():
        """Fold this touch point into the edge bearing, and test for a corner.

        The corner signal is the bearing between CONSECUTIVE touch points. On a straight (even a
        hand-laid, wandering) edge that bearing is stable; at a corner it swings, monotonically.
        A sign flip RESETS the accumulator, so a wiggle cancels and only a corner accumulates.
        Returns "CORNER", "WIGGLE" or "" .
        """
        st["touches"] += 1
        if st["touches"] < 2:
            st["px"], st["py"] = st["x"], st["y"]
            return ""
        brg = math.degrees(math.atan2(st["y"] - st["py"], st["x"] - st["px"]))
        st["px"], st["py"] = st["x"], st["y"]
        if st["prev_brg"] is None:
            st["prev_brg"] = brg
            st["edge"] = brg
            return ""
        d = norm_deg(brg - st["prev_brg"])
        st["prev_brg"] = brg
        if st["turn_sum"] == 0.0 or (d >= 0) == (st["turn_sum"] >= 0):
            st["turn_sum"] += d
        else:
            st["turn_sum"] = d              # sign flip: a wiggle, not a corner. Start again.
        if abs(st["turn_sum"]) >= CORNER_MIN_DEG:
            st["corner"] = st["turn_sum"]
            return "CORNER"
        if abs(st["turn_sum"]) > WIGGLE_MAX_DEG:
            return "WIGGLE"
        return ""

    reason = "time_cap"
    try:
        # --- 0. if we are armed sitting ON the tape, back off it first -------------------------
        await settle("start")
        if sample("check"):
            await drive(CLEAR_CAP_DEG, "clear", False, back=True)
            await settle("clear")

        # --- 1. SEEK: drive straight until the boundary --------------------------------------
        mm, saw = await drive(SEEK_CAP_DEG, "seek", True)
        if not saw:
            reason = "NO_TAPE"
            raise StopRun(reason)
        await settle("touch0")
        st["x"], st["y"] = 0.0, 0.0                    # origin = the first boundary touch
        record_touch()
        theta_e = norm_deg(st["hdg"] + SIDE * 90.0)    # travel direction ALONG the edge

        # --- 2. STITCH: walk the edge by repeated touches -------------------------------------
        verdict = ""
        for k in range(1, MAX_TOUCH):
            await turn_to(norm_deg(theta_e + SIDE * STITCH_DEG), "retreat%d" % k)
            await drive(RETREAT_DEG, "retreat%d" % k, None)
            await turn_to(norm_deg(theta_e - SIDE * STITCH_DEG), "approach%d" % k)
            mm, saw = await drive(APPROACH_CAP_DEG, "approach%d" % k, True)
            if not saw:
                reason = "LOST_EDGE"                   # the edge fell away: a result, not a crash
                break
            await settle("touch%d" % k)
            verdict = record_touch()
            if st["touches"] >= 2 and st["prev_brg"] is not None:
                theta_e = st["prev_brg"]               # re-aim from the last two REAL touches
            if verdict == "CORNER":
                reason = "CORNER"
                break
        else:
            reason = "EDGE_STRAIGHT"                   # walked the whole budget, no corner: also a
                                                       # result, and the control case for the demo
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        motor.stop(PL)
        motor.stop(PR)
        for _ in range(4):                             # TRUE stopping point, motors already cut
            sample("stopped")
            await runloop.sleep_ms(100)
        log.append("#end reason=%s touches=%d corner_deg=%d turnsum_deg=%d x_mm=%d y_mm=%d rows=%d"
                   % (reason, st["touches"], int(st["corner"]), int(st["turn_sum"]),
                      int(st["x"]), int(st["y"]), st["seq"]))
        log.close()
        if reason == "CORNER":
            show(XMARK)
            beep(880, 120)
            time.sleep_ms(160)
            beep(1320, 200)
        elif reason == "EDGE_STRAIGHT":
            show(DASH)
            beep(660, 200)
        elif reason in ("LOST_EDGE", "NO_TAPE"):
            show(QMARK)
            beep(440, 300)
        else:
            show(BOX)
        print("FIND_CORNER done: %s touches=%d corner=%d turnsum=%d pose=(%d,%d) rows=%d -> %s"
              % (reason, st["touches"], int(st["corner"]), int(st["turn_sum"]),
                 int(st["x"]), int(st["y"]), st["seq"], log.path))


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    await countdown()
    await find_corner()


runloop.run(main())
