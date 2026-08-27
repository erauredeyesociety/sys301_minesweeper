# examples/imu_verbose.py — everything the hub's IMU will tell us, verbosely.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/imu_verbose.py
#
# Purpose: DISCOVERY, not the mission. This prints raw values with no
# interpretation baked in, so we can find out what the units and ranges
# actually are instead of trusting a datasheet. Whatever we learn gets
# distilled into src/ later -- that is the whole point of keeping this
# out of src/.
#
# It also measures two numbers that odometry depends on and that nothing
# else can give us:
#   * the NOISE FLOOR of each axis while the hub sits perfectly still
#   * the YAW DRIFT RATE -- how fast heading rots when nothing is moving
# Both are the difference between "the gyro says we turned 90 degrees" and
# "we turned 90 degrees".
#
# MicroPython notes: no f-strings, no statistics module, no numpy.
# Keep it to % formatting and plain loops.

import time
import hub

SAMPLES = 100          # how many readings in the streaming phase
PERIOD_MS = 50         # target interval between readings

m = hub.motion_sensor


def show(label, value):
    print("  %-22s %r" % (label, value))


print("=" * 62)
print("IMU DISCOVERY -- hub.motion_sensor")
print("=" * 62)

print("\n--- 1. WHAT EXISTS ---")
print("  " + ", ".join([a for a in dir(m) if not a.startswith("_")]))

print("\n--- 2. ONE SAMPLE OF EACH, RAW ---")
print("  (units are what we are trying to LEARN -- nothing here is assumed)")
show("tilt_angles()", m.tilt_angles())
show("acceleration()", m.acceleration())
show("angular_velocity()", m.angular_velocity())
show("quaternion()", m.quaternion())
show("up_face()", m.up_face())
show("stable()", m.stable())
show("gesture()", m.gesture())
show("tap_count()", m.tap_count())

print("\n--- 3. ORIENTATION CONSTANTS ---")
print("  face constants on motion_sensor:")
for name in ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT", "UNKNOWN"]:
    if hasattr(m, name):
        print("    %-8s = %r" % (name, getattr(m, name)))
print("  gesture constants:")
for name in ["TAPPED", "DOUBLE_TAPPED", "SHAKEN", "FALLING", "UNKNOWN"]:
    if hasattr(m, name):
        print("    %-14s = %r" % (name, getattr(m, name)))

print("\n--- 4. HOLD STILL: %d samples at ~%d ms ---" % (SAMPLES, PERIOD_MS))
print("  Do not touch the hub. This measures the noise floor and yaw drift.")
print("")
print("   n     yaw   pitch    roll |    ax     ay     az |    gx     gy     gz")

yaws = []
acc = [[], [], []]
gyr = [[], [], []]
t0 = time.ticks_ms()

for i in range(SAMPLES):
    tilt = m.tilt_angles()
    a = m.acceleration()
    g = m.angular_velocity()

    yaws.append(tilt[0])
    for k in range(3):
        acc[k].append(a[k])
        gyr[k].append(g[k])

    if i % 10 == 0:
        print("  %3d  %6d  %6d  %6d | %5d  %5d  %5d | %5d  %5d  %5d"
              % (i, tilt[0], tilt[1], tilt[2], a[0], a[1], a[2], g[0], g[1], g[2]))

    time.sleep_ms(PERIOD_MS)

elapsed_ms = time.ticks_diff(time.ticks_ms(), t0)


def stats(vals):
    lo = min(vals)
    hi = max(vals)
    total = 0
    for v in vals:
        total += v
    return lo, hi, total / len(vals), hi - lo


print("\n--- 5. WHAT THAT MEASURED ---")
print("  elapsed %d ms for %d samples => %.1f ms/sample, %.1f Hz actual"
      % (elapsed_ms, SAMPLES, float(elapsed_ms) / SAMPLES,
         1000.0 * SAMPLES / elapsed_ms))
print("  (the REQUESTED period was %d ms -- the difference is the cost of"
      % PERIOD_MS)
print("   reading the sensors, and it bounds our real control-loop rate)")

names = ["accel x", "accel y", "accel z"]
print("\n  STATIONARY NOISE -- min / max / mean / spread")
for k in range(3):
    lo, hi, mean, spread = stats(acc[k])
    print("    %-9s %6d %6d %9.2f %6d" % (names[k], lo, hi, mean, spread))
names = ["gyro x", "gyro y", "gyro z"]
for k in range(3):
    lo, hi, mean, spread = stats(gyr[k])
    print("    %-9s %6d %6d %9.2f %6d" % (names[k], lo, hi, mean, spread))

print("\n  YAW DRIFT -- the number odometry lives or dies on")
drift = yaws[-1] - yaws[0]
print("    start %d  end %d  drift %d over %d ms" % (yaws[0], yaws[-1], drift, elapsed_ms))
if elapsed_ms > 0:
    print("    => %.3f units/second while sitting perfectly still"
          % (1000.0 * drift / elapsed_ms))
print("    A non-zero number here is NORMAL. What matters is how big it is")
print("    against the heading budget for a full sweep.")

print("\n  Note: a stationary accelerometer should read ~1g on ONE axis and")
print("  ~0 on the other two. Whichever axis carries gravity tells us how the")
print("  hub is mounted, and the magnitude tells us the units.")
print("\nDONE.")
