# examples/drive_moves.py — the checkpoint: forward, back, turn right, turn left.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/drive_moves.py --seconds 40
#
# ⚠ THIS MOVES THE ROBOT ACROSS THE FLOOR. Put it on the floor with ~1 m clear
#   all around, OR prop the wheels off the desk. It drives at a low speed for
#   short bursts with pauses, and a try/finally stops both motors on any exit
#   (including the run.py deadline Ctrl-C).
#
# ONE JOB: demonstrate the four basic moves and confirm the sign convention.
#   Differential drive, direct drive (1 wheel rev = 360 encoder deg), motors on
#   A and B (device.id 48), rear roller caster. The two motors are mounted
#   MIRRORED, so "forward" is a different sign on each -- that is what the sign
#   constants below encode, and confirming them on the floor is half the point.
#
# [ASSUMED], to confirm by watching the robot:
#   * LEFT_PORT / RIGHT_PORT -- which physical wheel is on A vs B is not yet
#     known. If "forward" spins in place or veers, the ports are swapped.
#   * *_FWD signs -- from the hand-turn encoder read (left forward drove the
#     encoder NEGATIVE, right forward POSITIVE). If "forward" goes backward,
#     flip both signs.
# Each move prints the exact velocities it commands, so a wrong direction tells
# you which constant to change -- fix the constant, not main.py.
#
# MicroPython: no f-strings, no dataclasses. % formatting only.

import time
import motor
from hub import port

LEFT_PORT = port.A          # [ASSUMED] left wheel
RIGHT_PORT = port.B         # [ASSUMED] right wheel
LEFT_FWD = -1               # sign that drives the LEFT wheel forward  (encoder went negative)
RIGHT_FWD = +1              # sign that drives the RIGHT wheel forward (encoder went positive)

SPEED_DPS = 250             # gentle: ~0.7 rev/s. Measured motor ceiling is 930.
MOVE_MS = 1500              # how long each straight move runs
TURN_MS = 900               # how long each pivot turn runs
PAUSE_MS = 1200             # settle between moves, so each is clearly separable
ARM_S = 3                   # countdown before anything moves


def drive(left_v, right_v):
    motor.run(LEFT_PORT, int(left_v))
    motor.run(RIGHT_PORT, int(right_v))


def stop():
    motor.stop(LEFT_PORT)
    motor.stop(RIGHT_PORT)


def move(label, left_v, right_v, dur_ms):
    print("  %-11s left(A)=%+5d  right(B)=%+5d dps  for %d ms"
          % (label, left_v, right_v, dur_ms))
    la0 = motor.relative_position(LEFT_PORT)
    ra0 = motor.relative_position(RIGHT_PORT)
    drive(left_v, right_v)
    time.sleep_ms(dur_ms)
    stop()
    la1 = motor.relative_position(LEFT_PORT)
    ra1 = motor.relative_position(RIGHT_PORT)
    print("             encoder delta: left %+d  right %+d deg" % (la1 - la0, ra1 - ra0))
    time.sleep_ms(PAUSE_MS)


print("=" * 62)
print("DRIVE MOVES -- forward / back / turn right / turn left")
print("=" * 62)

# Refuse to run if the two motors are not where we think they are.
ok = True
for name, p in (("A", LEFT_PORT), ("B", RIGHT_PORT)):
    try:
        st = motor.status(p)
        print("  motor %s status %d (0=READY)" % (name, st))
    except Exception as e:
        print("  motor %s NOT present: %s" % (name, type(e).__name__))
        ok = False
if not ok:
    print("  a motor is missing -- not moving. Check the port map.")
else:
    v = SPEED_DPS
    print("\n  MOVING in %d s -- clear the floor or prop the wheels up." % ARM_S)
    time.sleep_ms(ARM_S * 1000)
    try:
        move("FORWARD",    LEFT_FWD * v,  RIGHT_FWD * v,  MOVE_MS)
        move("BACKWARD",  -LEFT_FWD * v, -RIGHT_FWD * v,  MOVE_MS)
        move("TURN RIGHT", LEFT_FWD * v, -RIGHT_FWD * v,  TURN_MS)   # left fwd, right back
        move("TURN LEFT", -LEFT_FWD * v,  RIGHT_FWD * v,  TURN_MS)   # left back, right fwd
    finally:
        stop()
    print("\n  Done. Did each labelled move match the robot's actual motion?")
    print("  FORWARD went backward  -> flip LEFT_FWD and RIGHT_FWD.")
    print("  FORWARD spun in place  -> LEFT_PORT/RIGHT_PORT are swapped.")
    print("  TURN RIGHT turned left -> same swap, or the two signs disagree.")

print("\nDONE.")
