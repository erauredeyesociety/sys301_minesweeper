# examples/standalone_log.py — record telemetry to /flash while UNPLUGGED, for later USB retrieval.
#
# The competition fallback milestone: a slot program logs sensors to /flash and keeps running on
# battery after the USB cable is pulled; plug back in afterward and download.py retrieves the log.
# NO MOTORS -- the robot stays put when you unplug, so it is safe to set down and shake by hand.
#
# Deploy + run (slot mechanism, program.py -- proven 2026-09-03):
#   ./hub_programmer/slot_upload.py examples/standalone_log.py --apply --listen 0
#   >>> then UNPLUG the USB, shake the robot ~20 s, plug back in
#   python3 hub_programmer/download.py --all
#
# A moving pixel on the 5x5 matrix shows it is running (visible while unplugged). Logs IMU + both
# colour sensors + battery at 10 Hz for 45 s. MicroPython: no f-strings.

import runloop
import time
import hub
import color_sensor
from hub import motion_sensor, port
from hub_telemetry_log import CsvLog

LOG_MS = 45000
PERIOD_MS = 100
PC = port.C
PD = port.D

COLUMNS = (
    "seq", "t_ms", "yaw_ddeg", "pitch_ddeg", "roll_ddeg", "accx_mg", "accy_mg", "accz_mg",
    "colorC", "reflC_pct", "rC", "gC", "bC", "iC",
    "colorD", "reflD_pct", "rD", "gD", "bD", "iD", "batt_mv",
)


def none_ok(fn):
    try:
        return fn()
    except Exception:
        return None


async def main():
    log = CsvLog(",".join(COLUMNS), prefix="standalone", now_ms=time.ticks_ms())
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
                seq, t, tilt[0], tilt[1], tilt[2], acc[0], acc[1], acc[2],
                none_ok(lambda: color_sensor.color(PC)), none_ok(lambda: color_sensor.reflection(PC)),
                cc[0], cc[1], cc[2], cc[3],
                none_ok(lambda: color_sensor.color(PD)), none_ok(lambda: color_sensor.reflection(PD)),
                cd[0], cd[1], cd[2], cd[3],
                none_ok(lambda: hub.battery_voltage()),
            )
            log.append(",".join("" if v is None else str(v) for v in row))
            # a walking pixel = "running", visible with the cable out
            try:
                hub.light_matrix.clear()
                hub.light_matrix.set_pixel(seq % 5, (seq // 5) % 5, 100)
            except Exception:
                pass
            time.sleep_ms(0)
            await runloop.sleep_ms(PERIOD_MS)
    finally:
        log.close()
        print("SL done: %d rows to %s" % (seq, log.path))


runloop.run(main())
