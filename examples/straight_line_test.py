# straight_line_test.py -> program.py. Drive a LONG straight line, repeatedly, and log the drift.
# POWER-CYCLE the hub first (REPL tools kill the Hub OS), then:
#   ./hub_programmer/slot_upload.py examples/straight_line_test.py --apply
#   -> hub shows "S"; UNPLUG USB, aim the robot down a clear runway, tap LEFT/RIGHT.
#   It drives ONE leg, stops, and returns to ARMED. Reposition, tap again for the next leg.
#   All legs append to ONE log. Replug when done, then:
#   python3 hub_programmer/download.py --all && scripts/analyse-run.py
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
#
# THIS ANSWERS THE LOAD-BEARING UNKNOWN, and it is the foundation of the lawnmower sweep.
# A lane IS a long straight line, so nothing about coverage is trustworthy until this is measured.
#
# THE QUESTION: is the observed heading wander a SYSTEMATIC BIAS or ZERO-MEAN NOISE?
#   * BIAS accumulates. [COMPUTED] 1.6 deg over a 3048 mm lane is 85 mm of cross-track drift -- WIDER
#     THAN A 76 mm NOTE, so a mine the lane should have covered is missed entirely. Fatal.
#   * NOISE partly cancels and may already meet the budget (<1.43 deg over 10 ft).
# They demand opposite fixes, and today we cannot tell them apart: MEASURED over four ~300 mm
# segments the nets were -3, -1, -4, +6 ddeg, mean -0.50, SD 4.509. With n=4 the 95% CI on the
# per-300 mm bias spans -7.67 to +6.67 ddeg, which scales to -207 mm to +180 mm of drift over
# 3048 mm. A bias 2.7x FATAL to the budget is fully consistent with that data.
#
# HOW THIS SETTLES IT: drive the SAME long leg several times and look at the NET heading change of
# each. Legs clustering around a NON-ZERO mean = BIAS. Legs scattered around zero = NOISE. Long legs
# and repeats are both essential -- four short segments could never have decided it.
#
# ⚠ HEADING HOLD IS OFF BY DEFAULT, DELIBERATELY. A controller would MASK the very quantity being
# measured. Measure the plant first, then tune the controller against the measurement -- the reverse
# is how a heading hold with an inferred sign drove this robot in circles for 40 s on 2026-09-08
# (docs/lessons_learned/guard-every-feedback-loop.md).
#
# SECOND MEASUREMENT, free with the first: CROSS_TRACK_ERROR_MM is [UNMEASURED] and it sets the lane
# pitch -- mission_config.lane_pitch_mm() is TARGET_SIZE_MM - 2*CROSS_TRACK - LANE_OVERLAP = 41 mm
# with the ASSUMED 15 mm. Put a mark on the floor at the start and at the intended end; the lateral
# miss at the end IS the cross-track error over that distance. Write it on paper -- the robot cannot
# see its own lateral error.
import time
import runloop
import motor
import color_sensor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

PL = port.A            # left motor
PR = port.B            # right motor
PC = port.C            # RIGHT-hand floor sensor (confirmed 2026-09-08)
PD = port.D            # LEFT-hand floor sensor  (confirmed 2026-09-08)
LEFT_FWD = -1          # forward = A negative, B positive. MEASURED and twice confirmed.
RIGHT_FWD = 1

LEG_MM = 2500.0        # long enough that a real bias separates from tick noise. Needs ~3 m clear.
SPEED_DPS = 270        # ~150 mm/s, the configured traverse speed -- measure the drift AT THE SPEED
                       # the sweep will actually use, not at a gentler one.
MM_PER_REV = 199.49    # pi * 63.5 mm wheel, MEASURED 2026-09-03
LEG_DEG = LEG_MM * 360.0 / MM_PER_REV
RUN_CAP_MS = 40000     # per-leg time cap
ARM_TIMEOUT_MS = 120000
COUNTDOWN_S = 3
TICK_MS = 50
SETTLE_MS = 600        # let the coast finish before reading the TRUE end heading

# Set to a positive gain ONLY after the bias question is settled. Left at 0 the run is open-loop,
# which is the whole point of this test.
HOLD_KP = 0.0
HOLD_MAX_DPS = 30

S_GLYPH = (0,1,1,1,1, 1,0,0,0,0, 0,1,1,1,0, 0,0,0,0,1, 1,1,1,1,0)
BOX = (1,1,1,1,1, 1,0,0,0,1, 1,0,0,0,1, 1,0,0,0,1, 1,1,1,1,1)
FULL = (1,)*25
HEADER = ("seq,t_ms,phase,relA_deg,relB_deg,velL,velR,statusL,statusR,"
          "yaw_ddeg,accx_mg,accy_mg,accz_mg,reflC_pct,rC,gC,bC,iC,reflD_pct,rD,gD,bD,iD,reason")


class StopRun(Exception):
    pass


def show(p):
    try:
        light_matrix.show([100 if v else 0 for v in p])
    except Exception:
        pass


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
        pass                       # [UNVERIFIED] signature -- a silent hub must not fail the run


def norm_ddeg(d):
    """Yaw WRAPS at +/-180 deg. Every delta goes through here or 1 deg reads as 359."""
    return ((d + 1800) % 3600) - 1800


def stop_motors():
    """Never raises: each motor is stopped independently, so one failure cannot strand the other."""
    for p in (PL, PR):
        try:
            motor.stop(p)
        except Exception:
            pass


def digit(n):
    """Leg number on the matrix, so the operator knows which leg is which without the laptop."""
    rows = {0: (0,1,1,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,1,1,0),
            1: (0,0,1,0,0, 0,1,1,0,0, 0,0,1,0,0, 0,0,1,0,0, 0,1,1,1,0),
            2: (0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0),
            3: (0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0),
            4: (0,1,0,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,0,0,1,0),
            5: (0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0),
            6: (0,1,1,1,0, 0,1,0,0,0, 0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0),
            7: (0,1,1,1,0, 0,0,0,1,0, 0,0,0,1,0, 0,0,0,1,0, 0,0,0,1,0),
            8: (0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0),
            9: (0,1,1,1,0, 0,1,0,1,0, 0,1,1,1,0, 0,0,0,1,0, 0,1,1,1,0)}
    return rows.get(min(max(n, 0), 9), FULL)


async def wait_tap(timeout_ms, leg):
    show(digit(leg))
    print("ARMED for leg %d: aim down a clear runway (~3 m), then tap LEFT or RIGHT" % leg)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if tapped():
            return True
        await runloop.sleep_ms(50)
    return False


async def one_leg(log, box, leg):
    """Drive LEG_MM straight, open-loop unless HOLD_KP is set. Returns the net heading change."""
    t0 = time.ticks_ms()

    def sample(phase):
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        row = (box["seq"], time.ticks_diff(time.ticks_ms(), t0), phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
               none_ok(lambda: color_sensor.reflection(PC)), cc[0], cc[1], cc[2], cc[3],
               none_ok(lambda: color_sensor.reflection(PD)), cd[0], cd[1], cd[2], cd[3],
               box["note"])
        log.append(",".join("" if v is None else str(v) for v in row))
        box["seq"] += 1
        box["note"] = ""

    a0 = none_ok(lambda: motor.relative_position(PL)) or 0
    b0 = none_ok(lambda: motor.relative_position(PR)) or 0
    y0 = none_ok(lambda: motion_sensor.tilt_angles()[0])
    box["note"] = "LEG%d_START_yaw%s" % (leg, y0)

    reason = "complete"
    try:
        motor.run(PL, LEFT_FWD * SPEED_DPS)
        motor.run(PR, RIGHT_FWD * SPEED_DPS)
        while True:
            if tapped():
                raise StopRun("STOP_button")
            if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
                raise StopRun("time_cap")
            a = none_ok(lambda: motor.relative_position(PL))
            if a is not None and abs(a - a0) >= LEG_DEG:
                break
            sample("leg%d" % leg)
            # Open-loop unless a gain is set. See the header: a controller would mask the very
            # quantity this test exists to measure.
            if HOLD_KP > 0.0 and y0 is not None:
                y = none_ok(lambda: motion_sensor.tilt_angles()[0])
                if y is not None:
                    corr = HOLD_KP * norm_ddeg(y - y0)
                    if corr > HOLD_MAX_DPS:
                        corr = HOLD_MAX_DPS
                    elif corr < -HOLD_MAX_DPS:
                        corr = -HOLD_MAX_DPS
                    motor.run(PL, int(LEFT_FWD * (SPEED_DPS - corr)))
                    motor.run(PR, int(RIGHT_FWD * (SPEED_DPS + corr)))
            await runloop.sleep_ms(TICK_MS)
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        stop_motors()

    await runloop.sleep_ms(SETTLE_MS)          # the TRUE end heading is after the coast, not before
    a1 = none_ok(lambda: motor.relative_position(PL)) or a0
    b1 = none_ok(lambda: motor.relative_position(PR)) or b0
    y1 = none_ok(lambda: motion_sensor.tilt_angles()[0])
    net = norm_ddeg(y1 - y0) if (y0 is not None and y1 is not None) else None
    da, db = a1 - a0, b1 - b0
    mm = (abs(da) + abs(db)) / 2.0 * MM_PER_REV / 360.0
    box["note"] = ("LEG%d_END_%s_net%s_dA%d_dB%d_mm%d" % (leg, reason, net, da, db, int(mm)))
    sample("leg%d" % leg)
    print("  LEG %d: %s  net yaw %s ddeg   dA %+d  dB %+d   ~%d mm   divergence %+d"
          % (leg, reason, net, da, db, int(mm), abs(da) - abs(db)))
    beep(880, 120)
    return net


async def main():
    log = CsvLog(HEADER, prefix="straight", now_ms=time.ticks_ms())
    box = {"seq": 0, "note": ""}
    nets = []
    print("=" * 70)
    print("STRAIGHT-LINE DRIFT TEST -- %d mm per leg at %d dps, heading hold %s"
          % (int(LEG_MM), SPEED_DPS, "ON" if HOLD_KP > 0 else "OFF (open loop)"))
    print("Run at least 5 legs. Reposition between legs; tap to start each one.")
    print("=" * 70)
    try:
        for leg in range(1, 10):
            if not await wait_tap(ARM_TIMEOUT_MS, leg):
                print("no tap -- finishing")
                break
            for s in range(COUNTDOWN_S, 0, -1):
                show(FULL if (s % 2) else BOX)
                beep(1000, 60)
                await runloop.sleep_ms(1000)
            net = await one_leg(log, box, leg)
            if net is not None:
                nets.append(net)
    finally:
        stop_motors()
        # The whole point, computed on the hub so the operator sees it before unplugging: legs
        # clustering around a NON-ZERO mean means BIAS; scattered around zero means NOISE.
        if nets:
            mean = sum(nets) / float(len(nets))
            spread = max(nets) - min(nets)
            log.append("#end legs=%d nets=%s mean_ddeg=%.1f spread_ddeg=%d"
                       % (len(nets), "|".join([str(n) for n in nets]), mean, spread))
            print("")
            print("=" * 70)
            print("  legs=%d  nets=%s" % (len(nets), nets))
            print("  MEAN %.1f ddeg   SPREAD %d ddeg" % (mean, spread))
            print("  Mean far from zero relative to the spread => BIAS (accumulates, needs a fix).")
            print("  Mean near zero with a wide spread        => NOISE (partly cancels).")
            print("=" * 70)
        else:
            log.append("#end legs=0 -- no usable heading readings")
        log.close()
        show(BOX)
        print("STRAIGHT done -> %s" % log.path)


runloop.run(main())
