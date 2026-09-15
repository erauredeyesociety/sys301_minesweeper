# speed_ladder.py -> program.py. Step through commanded speeds and MEASURE what the robot actually
# does at each one, so MIN and MAX stop being guesses.
# POWER-CYCLE the hub first (REPL tools kill the Hub OS), then:
#   ./hub_programmer/slot_upload.py examples/speed_ladder.py --apply
#   -> hub shows "S"; UNPLUG USB, put the robot on the arena carpet with ~1.5 m clear AHEAD AND
#   BEHIND, tap LEFT/RIGHT, stand clear. Replug when the box shows, then:
#   python3 hub_programmer/download.py --all && scripts/analyse-run.py
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
#
# WHY THIS RUNS FIRST. Every speed in this project is a copy-pasted bench-safety constant. The motors
# were never the limit -- MEASURED, motor.run() delivers what it is told (commanded 150 dps, achieved
# 150.02). What is NOT known is what the ROBOT does at each speed on THIS carpet: where the closed
# loop stops holding, where it stops tracking straight, and where it stalls. Those three numbers set
# mission_config.TRAVERSE_SPEED_MMS and the whole time budget.
#
# THE ROBOT STAYS PUT. Each speed is driven FORWARD then BACKWARD for the same time, so net
# displacement is ~zero and a 900 dps step needs ~700 mm of runway, not 12 m. It will oscillate.
#
# WHAT IS MEASURED AT EACH STEP -- all from the encoders, never from motor.velocity():
#   ⚠ motor.velocity() is NOT deg/s. MEASURED across 12 logs: it reads ~percent of rated speed
#     (150.02 dps -> 12.90). Speed here is ALWAYS delta(relative_position)/delta(t).
#   * ACHIEVED dps per wheel, and achieved/commanded. Where that ratio falls below ~0.95 the closed
#     loop has run out of authority -- that is the real MAX, and it may be well under max_speed=930.
#   * DIVERGENCE, |dL| - |dR| -- the straightness proxy. A speed the robot cannot drive straight at
#     is useless for a sweep lane no matter what the encoders say.
#   * YAW RATE, degrees per second of unwanted turn. Straightness in the frame that matters.
#   * TICK PERIOD actually achieved, because the sampling ceiling scales with it and a slower loop at
#     speed would quietly cancel the gain.
#
# EDIT THIS LIST AND RE-RUN -- that is the whole adaptation.
import time
import runloop
import motor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

# Commanded speeds in deg/s, low to high. 930 is the MEASURED max_speed, so the top of the ladder is
# deliberately at it: the point is to find where reality departs from the command.
SPEEDS = (50, 100, 150, 250, 400, 550, 700, 850, 930)
# And the low end, to find where it stalls or stutters on carpet. A sweep needs a usable MIN too --
# the corner arc drives its inner wheel at 21 dps at R=65 mm, so anything above that would break it.
SLOW_SPEEDS = (40, 30, 20, 15, 10)

HOLD_MS = 1500         # per direction, so 3.0 s per speed. At 930 dps that is ~700 mm each way.
SETTLE_MS = 500        # let it come to rest before reading the end state
TICK_MS = 20           # sample FAST here -- this program is measuring the loop as well as the motors
RUN_CAP_MS = 180000
ARM_TIMEOUT_MS = 120000
COUNTDOWN_S = 5

PL = port.A            # left motor
PR = port.B            # right motor
LEFT_FWD = -1          # forward = A negative, B positive. MEASURED, twice confirmed.
RIGHT_FWD = 1
MM_PER_REV = 199.49    # pi * 63.5 mm wheel, MEASURED 2026-09-03

S_GLYPH = (0,1,1,1,1, 1,0,0,0,0, 0,1,1,1,0, 0,0,0,0,1, 1,1,1,1,0)
BOX = (1,1,1,1,1, 1,0,0,0,1, 1,0,0,0,1, 1,0,0,0,1, 1,1,1,1,1)
FULL = (1,)*25
BARS = (0,1,0,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,0,1,0, 0,1,0,1,0)
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


def stop_motors():
    """Never raises: each motor stopped independently, so one failure cannot strand the other."""
    for p in (PL, PR):
        try:
            motor.stop(p)
        except Exception:
            pass


def norm_ddeg(d):
    return ((d + 1800) % 3600) - 1800


async def run_step(log, box, dps, direction, label):
    """Drive one speed in one direction for HOLD_MS. Returns the measured row for this step."""
    sign = 1 if direction > 0 else -1
    a0 = none_ok(lambda: motor.relative_position(PL)) or 0
    b0 = none_ok(lambda: motor.relative_position(PR)) or 0
    y0 = none_ok(lambda: motion_sensor.tilt_angles()[0])
    t0 = time.ticks_ms()
    ticks = 0

    box["note"] = "STEP_%s_cmd%d_dir%d" % (label, dps, sign)
    motor.run(PL, LEFT_FWD * dps * sign)
    motor.run(PR, RIGHT_FWD * dps * sign)
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < HOLD_MS:
            if tapped():
                raise StopRun("STOP_button")
            acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
            row = (box["seq"], time.ticks_diff(time.ticks_ms(), box["t_run"]), label,
                   none_ok(lambda: motor.relative_position(PL)),
                   none_ok(lambda: motor.relative_position(PR)),
                   none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
                   none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
                   none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
                   "", "", "", "", "", "", "", "", "", "", box["note"])
            log.append(",".join("" if v is None else str(v) for v in row))
            box["seq"] += 1
            box["note"] = ""
            ticks += 1
            await runloop.sleep_ms(TICK_MS)
    finally:
        stop_motors()

    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    await runloop.sleep_ms(SETTLE_MS)
    a1 = none_ok(lambda: motor.relative_position(PL)) or a0
    b1 = none_ok(lambda: motor.relative_position(PR)) or b0
    y1 = none_ok(lambda: motion_sensor.tilt_angles()[0])

    da, db = abs(a1 - a0), abs(b1 - b0)
    secs = elapsed / 1000.0
    ach_l = da / secs if secs > 0 else 0.0
    ach_r = db / secs if secs > 0 else 0.0
    ach = (ach_l + ach_r) / 2.0
    ratio = ach / float(dps) if dps else 0.0
    yaw_rate = 0.0
    if y0 is not None and y1 is not None and secs > 0:
        yaw_rate = norm_ddeg(y1 - y0) / 10.0 / secs      # decidegrees -> degrees per second
    tick_ms = elapsed / float(ticks) if ticks else 0.0
    mms = ach * MM_PER_REV / 360.0

    box["note"] = ("RESULT_%s_cmd%d_achL%d_achR%d_ratio%d_div%d_yawrate%d_tick%d"
                   % (label, dps, int(ach_l), int(ach_r), int(ratio * 100),
                      int(da - db), int(yaw_rate * 10), int(tick_ms)))
    row = (box["seq"], time.ticks_diff(time.ticks_ms(), box["t_run"]), label,
           a1, b1, None, None, None, None, y1, None, None, None,
           "", "", "", "", "", "", "", "", "", "", box["note"])
    log.append(",".join("" if v is None else str(v) for v in row))
    box["seq"] += 1
    box["note"] = ""

    print("  %-10s cmd %4d dps | achieved %4d (%3d%%) | %5.0f mm/s | div %+5d | yaw %+5.1f d/s | tick %2.0f ms"
          % (label, dps, int(ach), int(ratio * 100), mms, da - db, yaw_rate, tick_ms))
    return (dps, ach, ratio, da - db, yaw_rate, tick_ms, mms)


async def main():
    log = CsvLog(HEADER, prefix="speedladder", now_ms=time.ticks_ms())
    box = {"seq": 0, "note": "", "t_run": time.ticks_ms()}
    results = []

    show(S_GLYPH)
    print("=" * 96)
    print("SPEED LADDER -- measuring what the robot ACTUALLY does at each commanded speed")
    print("Put it on the ARENA CARPET with ~1.5 m clear AHEAD AND BEHIND. It will oscillate.")
    print("=" * 96)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ARM_TIMEOUT_MS and not tapped():
        await runloop.sleep_ms(50)
    if not tapped():
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    for s in range(COUNTDOWN_S, 0, -1):
        show(FULL if (s % 2) else BOX)
        beep(1000, 60)
        await runloop.sleep_ms(1000)

    box["t_run"] = time.ticks_ms()
    try:
        show(BARS)
        print("")
        print("--- UP THE LADDER (forward, then back at the same speed) ---")
        for dps in SPEEDS:
            if time.ticks_diff(time.ticks_ms(), box["t_run"]) > RUN_CAP_MS:
                raise StopRun("time_cap")
            results.append(await run_step(log, box, dps, +1, "up%d" % dps))
            await run_step(log, box, dps, -1, "back%d" % dps)
        print("")
        print("--- DOWN TO THE STALL (where does it stop moving at all?) ---")
        for dps in SLOW_SPEEDS:
            if time.ticks_diff(time.ticks_ms(), box["t_run"]) > RUN_CAP_MS:
                raise StopRun("time_cap")
            results.append(await run_step(log, box, dps, +1, "slow%d" % dps))
            await run_step(log, box, dps, -1, "slowback%d" % dps)
        reason = "complete"
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        stop_motors()

        # THE POINT OF THE RUN, computed on the hub so the operator sees it before unplugging.
        # MAX = the highest command the loop still HOLDS (ratio >= 0.95) and still tracks straight.
        # MIN = the lowest command that still MOVES the robot at all.
        best_max, best_min = None, None
        for (dps, ach, ratio, div, yaw, tick, mms) in results:
            if ratio >= 0.95 and abs(yaw) < 5.0:
                if best_max is None or dps > best_max[0]:
                    best_max = (dps, mms, ratio, yaw)
            if ach > 5.0:
                if best_min is None or dps < best_min[0]:
                    best_min = (dps, mms, ratio, yaw)
        log.append("#end reason=%s steps=%d max=%s min=%s"
                   % (reason, len(results), best_max, best_min))
        log.close()
        show(BOX)
        beep(1320, 250)
        print("")
        print("=" * 96)
        if best_max:
            print("  MAX usable: %d dps = %.0f mm/s  (loop held %d%%, yaw drift %+.1f deg/s)"
                  % (best_max[0], best_max[1], int(best_max[2] * 100), best_max[3]))
            print("      -> compare against mission_config.max_safe_speed_mms(measured_tick_hz):")
            print("         the SAMPLING ceiling may be lower than this, and the LOWER one wins.")
        else:
            print("  MAX usable: NONE of the tested speeds held the loop AND tracked straight.")
        if best_min:
            print("  MIN usable: %d dps = %.0f mm/s  (below this the robot did not move)"
                  % (best_min[0], best_min[1]))
            print("      -> the corner arc at R=65 mm drives its INNER wheel at ~21 dps. If MIN is")
            print("         above that, the arc turn cannot work and R must be raised.")
        else:
            print("  MIN usable: not established -- every slow step failed to move.")
        print("  %s -> %s" % (reason, log.path))
        print("=" * 96)


runloop.run(main())
