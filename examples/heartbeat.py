# examples/heartbeat.py — the smallest program that answers KU-M16.
#
# DEPLOYED AS /flash/main.py:
#   ./hub_programmer/upload.py examples/heartbeat.py --to /flash/main.py --apply --force
#   then POWER-CYCLE the hub and watch. Restore with:
#   ./hub_programmer/upload.py hub_programmer/restore/main.py --to /flash/main.py --apply --force
#
# THE QUESTION: does /flash/main.py autorun at boot, and does the LEGO Hub OS
# keep running alongside it? That gates Demo Day -- it is the difference between
# a robot that runs standalone and a robot tethered to a laptop. It is also the
# gate on BLE telemetry: print() only reaches the host as a ConsoleNotification
# if the Hub OS is alive to carry it.
#
# IT REPORTS ITSELF THREE WAYS ON PURPOSE, so the answer is readable no matter
# which channels turn out to work:
#   1. the 5x5 light matrix -- visible with NO laptop at all
#   2. print() -- reaches USB serial, and BLE if the Hub OS is up
#   3. a beep at startup -- audible confirmation it began
#
# It never commands motion. It cannot drive the robot anywhere.
#
# MicroPython: no f-strings.

import time
import hub

# Beep once so the start is unmistakable even if nothing else works.
try:
    hub.sound.beep(600, 200, 60)
except Exception:
    pass

n = 0
while True:
    n += 1

    # 1. Light matrix: a moving pixel. Visible across a room, needs no laptop.
    try:
        hub.light_matrix.clear()
        hub.light_matrix.set_pixel(n % 5, (n // 5) % 5, 100)
    except Exception:
        pass

    # 2. print(): USB serial always; BLE ConsoleNotification only if the Hub OS lives.
    #    Keep the line short -- the negotiated BLE MTU is 23 bytes.
    try:
        yaw = hub.motion_sensor.tilt_angles()[0]
    except Exception:
        yaw = -9999
    print("HB %d yaw %d mV %d" % (n, yaw, hub.battery_voltage()))

    time.sleep_ms(500)
