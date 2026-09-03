# examples/autorun_test.py — does /flash/main.py autorun at boot? (runloop version)
#
# The 2026-08-27 test used a BARE program and main.py stayed dark. This retests with the
# SPIKE 3 runloop structure -- the same thing that a slot program needs. If THIS autoruns,
# the standalone competition path (upload -> unplug -> power on -> it runs) is open.
#
# Deploy + test:
#   ./hub_programmer/upload.py examples/autorun_test.py --to /flash/main.py --apply --force
#   power-cycle the hub, watch the 5x5 matrix.
# Restore:
#   ./hub_programmer/upload.py hub_programmer/restore/main.py --to /flash/main.py --apply --force
#
# It blinks the WHOLE matrix on/off every 0.5 s and prints a heartbeat. If the matrix blinks
# after a power cycle with no cable command, main.py autoruns. NO MOTORS -- safe on any surface.
#
# MicroPython: no f-strings.

import runloop
import hub


async def main():
    n = 0
    while n < 120:
        n += 1
        on = 100 if (n % 2) else 0
        for x in range(5):
            for y in range(5):
                hub.light_matrix.set_pixel(x, y, on)
        print("AUTORUN tick %d" % n)
        await runloop.sleep_ms(500)


runloop.run(main())
