# examples/telemetry_verbose_log.py -- verbose internal telemetry capture.
#
# DOES NOT COMMAND MOTION. It logs motor encoder state, IMU, and both colour sensors for a bounded
# window while the operator can shake the robot or turn wheels by hand. For motor-under-power tests,
# run a separate bounded slot program later and use the same logging shape.
#
# Expected path:
#   1. Upload src/hub_telemetry_log.py to /flash/lib.
#   2. Power-cycle the hub for clean Hub OS / BLE state.
#   3. Run as a slot program:
#        ./hub_programmer/slot_upload.py examples/telemetry_verbose_log.py --slot 1 --apply --listen 40
#   4. Pull the internal log:
#        python3 hub_programmer/download.py --all
#
# MicroPython: no f-strings.

import time
import motor
import color_sensor
from hub import motion_sensor, port
from hub_telemetry_log import CsvLog

LOG_MS = 30000
PERIOD_MS = 100
PRINT_EVERY = 5
FLUSH_EVERY = 10

PORT_A = port.A
PORT_B = port.B
PORT_C = port.C
PORT_D = port.D

COLUMNS = (
    "seq", "t_ms",
    "absA_deg", "relA_deg", "velA_dps", "dutyA_pct", "statusA",
    "absB_deg", "relB_deg", "velB_dps", "dutyB_pct", "statusB",
    "yaw_ddeg", "pitch_ddeg", "roll_ddeg", "accx_mg", "accy_mg", "accz_mg",
    "colorC", "reflC_pct", "rC", "gC", "bC", "iC",
    "colorD", "reflD_pct", "rD", "gD", "bD", "iD",
)


def read_or_none(fn):
    try:
        return fn()
    except Exception:
        return None


def flatten(value, n):
    if value is None:
        return [None] * n
    out = list(value[:n])
    while len(out) < n:
        out.append(None)
    return out


def csv_line(values):
    return ",".join("" if v is None else str(v) for v in values)


def read_motor(p):
    return [
        read_or_none(lambda: motor.absolute_position(p)),
        read_or_none(lambda: motor.relative_position(p)),
        read_or_none(lambda: motor.velocity(p)),
        read_or_none(lambda: motor.get_duty_cycle(p)),
        read_or_none(lambda: motor.status(p)),
    ]


def read_colour(p):
    color = read_or_none(lambda: color_sensor.color(p))
    refl = read_or_none(lambda: color_sensor.reflection(p))
    rgbi = flatten(read_or_none(lambda: color_sensor.rgbi(p)), 4)
    return [color, refl] + rgbi


def main():
    start = time.ticks_ms()
    header = [
        "#verbose-telemetry v1",
        "#period_ms=%d" % PERIOD_MS,
        "#duration_ms=%d" % LOG_MS,
        "#ports=A/B motors, C/D colour sensors, measured 2026-09-03",
        ",".join(COLUMNS),
    ]
    log = CsvLog(header, prefix="verbose", now_ms=start, flush_every=FLUSH_EVERY)
    print("TV start path %s" % log.path)
    seq = 0
    next_t = start
    try:
        while time.ticks_diff(time.ticks_ms(), start) < LOG_MS:
            now = time.ticks_ms()
            t_ms = time.ticks_diff(now, start)
            tilt = flatten(read_or_none(lambda: motion_sensor.tilt_angles()), 3)
            accel = flatten(read_or_none(lambda: motion_sensor.acceleration()), 3)
            row = ([seq, t_ms]
                   + read_motor(PORT_A)
                   + read_motor(PORT_B)
                   + tilt
                   + accel
                   + read_colour(PORT_C)
                   + read_colour(PORT_D))
            log.append(csv_line(row))
            if seq % PRINT_EVERY == 0:
                print("TV %d ms%s Arel%s Brel%s y%s Cref%s Dref%s" %
                      (seq, t_ms, row[3], row[8], row[12], row[19], row[25]))
            seq += 1
            next_t = time.ticks_add(next_t, PERIOD_MS)
            remain = time.ticks_diff(next_t, time.ticks_ms())
            if remain > 0:
                time.sleep_ms(remain)
    finally:
        log.close()
        print("TV done path %s rows %d" % (log.path, seq))


main()
