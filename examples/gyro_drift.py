# examples/gyro_drift.py — how fast does heading rot when nothing is moving?
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/gyro_drift.py --seconds 70
#
# One job: measure yaw drift, and REFUSE TO REPORT IT if the hub was disturbed.
#
# Why the refusal matters. An earlier 30 s run reported 98.7 degrees of "drift"
# that went +7.6, then -22.2, then +96.6. Steady drift does not reverse
# direction -- somebody was handling the robot. A number like that, written
# into a design document as a measured gyro characteristic, would send us
# building heading correction we may not need.
#
# So this watches the accelerometer while it measures. A stationary hub holds
# its gravity vector to within a milli-g or two; if that vector moves, the hub
# moved, and the drift figure from that window is worthless. The script says so
# instead of printing a number that looks authoritative.
#
# MicroPython: no f-strings, no statistics, no numpy.

import math
import time
import hub

m = hub.motion_sensor

DURATION_MS = 30000
PERIOD_MS = 50
# A stationary hub was measured holding each axis to a spread of 0-1 milli-g.
# 25 is far outside that and well inside "somebody bumped the table".
DISTURB_MG = 25


def mag(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


print("=" * 62)
print("GYRO DRIFT -- with a disturbance check")
print("=" * 62)
print("\nPut the hub on a flat surface and DO NOT TOUCH IT for 30 seconds.")
print("Starting in 3 seconds...")
time.sleep_ms(3000)

ref = m.acceleration()
start_yaw = m.tilt_angles()[0]
t0 = time.ticks_ms()

worst_dev = 0
disturbed_at = -1
samples = 0
yaw_min = start_yaw
yaw_max = start_yaw

while time.ticks_diff(time.ticks_ms(), t0) < DURATION_MS:
    t = time.ticks_diff(time.ticks_ms(), t0)
    a = m.acceleration()
    y = m.tilt_angles()[0]

    dev = mag((a[0] - ref[0], a[1] - ref[1], a[2] - ref[2]))
    if dev > worst_dev:
        worst_dev = dev
    if dev > DISTURB_MG and disturbed_at < 0:
        disturbed_at = t

    if y < yaw_min:
        yaw_min = y
    if y > yaw_max:
        yaw_max = y

    samples += 1
    if samples % 100 == 0:
        print("  t=%5d ms  yaw=%6d ddeg (%7.2f deg)  drift=%6d  accel_dev=%5.1f mg"
              % (t, y, y / 10.0, y - start_yaw, dev))

    time.sleep_ms(PERIOD_MS)

end_yaw = m.tilt_angles()[0]
elapsed = time.ticks_diff(time.ticks_ms(), t0)
net = end_yaw - start_yaw

print("\n--- RESULT ---")
print("  samples          %d over %d ms" % (samples, elapsed))
print("  yaw start/end    %d / %d ddeg" % (start_yaw, end_yaw))
print("  yaw min/max      %d / %d ddeg  (range %d)" % (yaw_min, yaw_max, yaw_max - yaw_min))
print("  net change       %d ddeg = %.2f degrees" % (net, net / 10.0))
print("  worst accel dev  %.1f milli-g   (threshold %d)" % (worst_dev, DISTURB_MG))

print("")
if disturbed_at >= 0:
    print("  *** CONTAMINATED -- the hub MOVED at t=%d ms ***" % disturbed_at)
    print("  The gravity vector shifted by more than %d milli-g, so the yaw" % DISTURB_MG)
    print("  change above is at least partly REAL ROTATION, not drift.")
    print("  This run measures nothing. Leave the hub alone and run it again.")
else:
    rate_dps = (net / 10.0) * 1000.0 / elapsed
    print("  Hub stayed still (worst deviation %.1f mg). The number is good." % worst_dev)
    print("  DRIFT RATE = %.4f degrees/second" % rate_dps)
    print("")
    print("  What it costs over a run:")
    for mins in (1, 3, 5, 10):
        print("    %2d min of driving => %7.2f degrees of accumulated heading error"
              % (mins, abs(rate_dps) * 60 * mins))
    print("")
    print("  Compare against the cross-track budget before deciding whether")
    print("  heading correction is needed at all. Cheap if it is not.")

print("\nDONE.")
