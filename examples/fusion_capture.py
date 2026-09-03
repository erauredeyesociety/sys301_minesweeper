# examples/fusion_capture.py — sensor fusion with the motors MOVING, logged to /flash.
#
# ⚠ MOVES MOTORS (in-place rotation, robot stays put). Hold / on blocks is safer.
#
# The point: capture motors + IMU + BOTH colour sensors TOGETHER while the robot is
# actually doing something, so scripts/decode_telemetry.py can reconstruct what happened.
# Runs over USB via the REPL (proven) -- no Bluetooth needed:
#   ./hub_programmer/run.py examples/fusion_capture.py --seconds 40
#   python3 hub_programmer/download.py --all
#   scripts/decode_telemetry.py
#
# Spins BOTH motors at the same raw sign = in-place rotation on this mirrored chassis,
# so the robot rotates about its centre and stays on the desk. Low speed, bounded,
# motors stopped in a finally. Logs the same 30-column record as telemetry_verbose_log.
#
# MicroPython: no f-strings.

import time
import motor
import color_sensor
from hub import motion_sensor, port
from hub_telemetry_log import CsvLog

SPEED_DPS = 150
LOG_MS = 30000
PERIOD_MS = 100
PL = port.A
PR = port.B
PC = port.C
PD = port.D

COLUMNS = (
    "seq", "t_ms",
    "relA_deg", "velA_dps", "statusA", "relB_deg", "velB_dps", "statusB",
    "yaw_ddeg", "pitch_ddeg", "roll_ddeg", "accx_mg", "accy_mg", "accz_mg",
    "colorC", "reflC_pct", "rC", "gC", "bC", "iC",
    "colorD", "reflD_pct", "rD", "gD", "bD", "iD",
)


def none_ok(fn):
    try:
        return fn()
    except Exception:
        return None


print("fusion_capture: spinning A+B in place at %d dps, logging all sensors" % SPEED_DPS)
log = CsvLog(",".join(COLUMNS), prefix="fusion", now_ms=time.ticks_ms())
motor.run(PL, SPEED_DPS)
motor.run(PR, SPEED_DPS)
t0 = time.ticks_ms()
seq = 0
try:
    while time.ticks_diff(time.ticks_ms(), t0) < LOG_MS:
        seq += 1
        t = time.ticks_diff(time.ticks_ms(), t0)
        tilt = none_ok(lambda: motion_sensor.tilt_angles()) or (None, None, None)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        row = (
            seq, t,
            none_ok(lambda: motor.relative_position(PL)), none_ok(lambda: motor.velocity(PL)),
            none_ok(lambda: motor.status(PL)),
            none_ok(lambda: motor.relative_position(PR)), none_ok(lambda: motor.velocity(PR)),
            none_ok(lambda: motor.status(PR)),
            tilt[0], tilt[1], tilt[2], acc[0], acc[1], acc[2],
            none_ok(lambda: color_sensor.color(PC)), none_ok(lambda: color_sensor.reflection(PC)),
            cc[0], cc[1], cc[2], cc[3],
            none_ok(lambda: color_sensor.color(PD)), none_ok(lambda: color_sensor.reflection(PD)),
            cd[0], cd[1], cd[2], cd[3],
        )
        log.append(",".join("" if v is None else str(v) for v in row))
        if seq % 10 == 0:
            print("FC %d t%d a%s b%s y%s Cr%s Dr%s"
                  % (seq, t, row[2], row[5], tilt[0],
                     none_ok(lambda: color_sensor.reflection(PC)),
                     none_ok(lambda: color_sensor.reflection(PD))))
        time.sleep_ms(PERIOD_MS)
finally:
    motor.stop(PL)
    motor.stop(PR)
    log.close()
    print("FC done: %d rows to %s" % (seq, log.path))
