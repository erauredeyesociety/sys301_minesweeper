# motor_poc.py -> program.py. Drive a 1ft square, logged; button start/stop, runs unplugged.
# ./hub_programmer/slot_upload.py examples/motor_poc.py --apply  -> hub shows "S"; unplug, tap
# LEFT/RIGHT, watch the square, replug when the box shows. Then download.py --all + decode.
# Only dep: hub_telemetry_log (in /flash/lib). Turns are gyro-closed 90 deg. MicroPython: no f-strings.
import time
import runloop
import motor
import color_sensor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

PL = port.A            # left motor
PR = port.B            # right motor
PC = port.C
PD = port.D
LEFT_FWD = -1          # measured mirror: forward = left neg, right pos. If a "side" rotates, flip.
RIGHT_FWD = 1
SPEED_DPS = 120
SIDE_DEG = 550         # ~1 ft at 63.5 mm wheel
TURN_DDEG = 900        # 90 deg, gyro-closed
SIDES = 4
COUNTDOWN_S = 5
RUN_CAP_MS = 45000
ARM_TIMEOUT_MS = 90000
TICK_MS = 100

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


def norm_ddeg(d):
    return ((d + 1800) % 3600) - 1800


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: tap LEFT or RIGHT to start")
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


async def drive_square():
    log = CsvLog(HEADER, prefix="motorpoc", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    box = {"seq": 0}

    def sample(phase):
        t = time.ticks_diff(time.ticks_ms(), t0)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
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

    def guard():
        if tapped():
            raise StopRun("STOP_button")
        if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
            raise StopRun("time_cap")

    async def straight(side):
        motor.run(PL, LEFT_FWD * SPEED_DPS)
        motor.run(PR, RIGHT_FWD * SPEED_DPS)
        l0 = motor.relative_position(PL)
        r0 = motor.relative_position(PR)
        while (abs(motor.relative_position(PL) - l0) < SIDE_DEG
               or abs(motor.relative_position(PR) - r0) < SIDE_DEG):
            guard()
            sample("side%d" % side)
            await runloop.sleep_ms(TICK_MS)
        motor.stop(PL)
        motor.stop(PR)

    async def turn(side):
        motor.run(PL, LEFT_FWD * SPEED_DPS)
        motor.run(PR, -RIGHT_FWD * SPEED_DPS)
        y0 = none_ok(lambda: motion_sensor.tilt_angles()[0]) or 0
        while True:
            y = none_ok(lambda: motion_sensor.tilt_angles()[0]) or y0
            if abs(norm_ddeg(y - y0)) >= TURN_DDEG:
                break
            guard()
            sample("turn%d" % side)
            await runloop.sleep_ms(TICK_MS)
        motor.stop(PL)
        motor.stop(PR)

    async def settle(side):
        for _ in range(3):
            sample("stop%d" % side)
            await runloop.sleep_ms(100)

    reason = "complete"
    try:
        for side in range(SIDES):
            await straight(side)
            await settle(side)
            await turn(side)
            await settle(side)
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        motor.stop(PL)
        motor.stop(PR)
        log.append("#end reason=%s rows=%d" % (reason, box["seq"]))
        log.close()
        show(BOX)
        print("SQUARE done: %d rows, reason=%s -> %s" % (box["seq"], reason, log.path))


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    await countdown()
    await drive_square()


runloop.run(main())
