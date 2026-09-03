# examples/g4_spin_and_print.py — the G4 test: motor runs WHILE BLE streams telemetry?
#
# ⚠ MOVES MOTORS. Robot held / on blocks, or this spins both wheels.
#
# SPIKE 3 SLOT PROGRAM STRUCTURE. Measured 2026-09-03: a bare top-level motor.run()
# + while/time.sleep_ms() launches as a slot (ProgramFlow ACK) but the motor does
# NOT turn. A slot program needs the runloop async structure -- runloop.run(main())
# with await runloop.sleep_ms() -- which is how the LEGO app itself generates code.
# (Bare motor.run() works fine from the REPL via hub_programmer/run.py; only the
# SLOT execution context needs runloop.)
#
#   SLOT (the real test): ./hub_programmer/slot_upload.py examples/g4_spin_and_print.py --apply --listen 0
#       then stream over BLE with hub_programmer/capture_ble.py -- the motor should
#       turn AND its encoder should move in the DeviceNotification stream at once.
#
# Spins BOTH motors at the same raw sign = in-place ROTATION on this mirrored
# chassis, so the robot stays put on the desk. Low speed, bounded, motors stopped
# in a finally.
#
# MicroPython: no f-strings.

import runloop
import motor
import hub
from hub import port

SPEED_DPS = 150        # gentle; measured ceiling is 930
TICKS = 100            # ~50 s at 500 ms -- long, so a BLE listener can overlap
PERIOD_MS = 500
PL = port.A            # left motor
PR = port.B            # right motor


async def main():
    print("G4 start: spinning A+B in place at %d dps" % SPEED_DPS)
    motor.run(PL, SPEED_DPS)
    motor.run(PR, SPEED_DPS)
    n = 0
    try:
        while n < TICKS:
            n += 1
            try:
                yaw = hub.motion_sensor.tilt_angles()[0]
            except Exception:
                yaw = -9999
            print("G4 %d y%d a%d b%d"
                  % (n, yaw, motor.relative_position(PL), motor.relative_position(PR)))
            await runloop.sleep_ms(PERIOD_MS)
    finally:
        motor.stop(PL)
        motor.stop(PR)
        print("G4 done: motors stopped after %d ticks" % n)


runloop.run(main())
