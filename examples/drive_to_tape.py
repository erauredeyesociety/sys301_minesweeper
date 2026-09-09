# drive_to_tape.py -> program.py. Drive forward until the BLUE BOUNDARY TAPE is seen, then stop.
# ./hub_programmer/slot_upload.py examples/drive_to_tape.py --apply  -> hub shows "S"; UNPLUG USB,
# set the robot on the carpet facing the tape, tap LEFT/RIGHT, stand clear. Replug when the box
# shows, then: python3 hub_programmer/download.py --all && scripts/decode_telemetry.py
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
#
# WHY THIS TEST: first time detection and motion run TOGETHER on hardware, untethered, on battery.
# It is also the exact behaviour the closed blue-tape box needs on demo day -- drive a lane, stop at
# the boundary -- and it answers what a hand-held capture cannot: is the tape still detectable while
# MOVING, at the real tick rate, with the sensors bouncing on carpet pile.
#
# THE TRIGGER IS MEASURED, NOT GUESSED (docs/findings/runs/surface-survey-2026-09-08.txt, 2026-09-08):
#     blue tape   b/(r+g+b) = 0.476 - 0.496,  total 124-135,  builtin color() = BLUE on 149/149
#     carpet      b/(r+g+b) = 0.333 - 0.408,  total  49-107,  builtin color() = BLACK / UNKNOWN
#     notes       b/(r+g+b) = 0.293 - 0.299,  total 263-1715
# The carpet's blue fraction reaches 0.408 on its darkest samples, so BLUE_FRAC_MIN sits at 0.44 --
# inside the measured gap (0.408 -> 0.476), on neither edge. The built-in color() call is a SECOND,
# independent vote: it was perfect on tape and never once said BLUE on carpet.
#
# The CSV HEADER is byte-identical to examples/motor_poc.py so scripts/decode_telemetry.py needs no
# change -- IMU, both encoders, both colour sensors, every tick.
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
LEFT_FWD = -1          # measured mirror: forward = left neg, right pos (proven, motor_poc 2026-09-03)
RIGHT_FWD = 1
SPEED_DPS = 100        # ~55 mm/s at the MEASURED 63.5 mm wheel -- deliberately slow
MAX_DEG = 1200         # hard distance cap, ~660 mm
RUN_CAP_MS = 20000     # hard time cap
ARM_TIMEOUT_MS = 90000
COUNTDOWN_S = 5
TICK_MS = 50           # 20 Hz -- faster than the sweep's 10 Hz so the edge crossing is resolved

BLUE_FRAC_MIN = 0.44   # measured gap: carpet max 0.408 -> tape min 0.476
CONSEC_NEEDED = 2      # two in a row, so one noisy sample cannot stop the run

S_GLYPH = (0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0)
BOX = (1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1)
FULL = (1,) * 25
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


def is_blue(rgbi_sample, color_code):
    """True when this reading looks like the boundary tape. Two independent votes, either suffices.

    Returns False (not None) on an unreadable sample: a missing read must never STOP the robot on
    its own -- a dropped read is not a boundary. The row still records the raw values as empty.
    """
    if color_code == color.BLUE:
        return True
    if rgbi_sample is None or rgbi_sample[0] is None:
        return False
    tot = rgbi_sample[0] + rgbi_sample[1] + rgbi_sample[2]
    if tot <= 0:
        return False
    return (float(rgbi_sample[2]) / tot) >= BLUE_FRAC_MIN


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: set the robot on the carpet facing the tape, then tap LEFT or RIGHT")
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


async def drive_to_tape():
    log = CsvLog(HEADER, prefix="drivetape", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    box = {"seq": 0, "hits": 0}

    def sample(phase):
        t = time.ticks_diff(time.ticks_ms(), t0)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        code_c = none_ok(lambda: color_sensor.color(PC))
        code_d = none_ok(lambda: color_sensor.color(PD))
        row = (box["seq"], t, phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
               none_ok(lambda: color_sensor.reflection(PC)), cc[0], cc[1], cc[2], cc[3],
               none_ok(lambda: color_sensor.reflection(PD)), cd[0], cd[1], cd[2], cd[3], "")
        log.append(",".join("" if v is None else str(v) for v in row))
        box["seq"] += 1
        return (is_blue(cc, code_c) or is_blue(cd, code_d))

    def guard():
        if tapped():
            raise StopRun("STOP_button")
        if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
            raise StopRun("time_cap")

    reason = "time_cap"
    try:
        motor.run(PL, LEFT_FWD * SPEED_DPS)
        motor.run(PR, RIGHT_FWD * SPEED_DPS)
        l0 = motor.relative_position(PL)
        while True:
            guard()
            if abs(motor.relative_position(PL) - l0) >= MAX_DEG:
                reason = "distance_cap"
                break
            if sample("drive"):
                box["hits"] += 1
                if box["hits"] >= CONSEC_NEEDED:
                    reason = "TAPE_DETECTED"
                    break
            else:
                box["hits"] = 0
            await runloop.sleep_ms(TICK_MS)
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        motor.stop(PL)
        motor.stop(PR)
        # Capture the TRUE stopping point AFTER the motors are cut -- the pose that matters is where
        # it actually ended, not the last sample before the break.
        for _ in range(4):
            sample("stopped")
            await runloop.sleep_ms(100)
        travelled = abs((none_ok(lambda: motor.relative_position(PL)) or l0) - l0)
        mm = travelled / 360.0 * 199.49          # 63.5 mm wheel, MEASURED 2026-09-03
        log.append("#end reason=%s rows=%d deg=%d mm=%d" % (reason, box["seq"], travelled, int(mm)))
        log.close()
        show(BOX)
        print("DRIVE_TO_TAPE done: %s after %d rows, %d deg (~%d mm) -> %s"
              % (reason, box["seq"], travelled, int(mm), log.path))


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    await countdown()
    await drive_to_tape()


runloop.run(main())
