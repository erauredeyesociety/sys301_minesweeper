# Finding — Drive checkpoint: forward / back / turn confirmed on the robot

**Date:** 2026-09-01 · **Hub:** USB, operator holding the robot (wheels free) ·
**Commanded motion:** yes — `examples/drive_moves.py`, low speed, operator watching ·
**Verified how:** encoder deltas (measured) **and** the operator watched each move (observed).

Raw run: [runs/drive-moves-2026-09-01.txt](./runs/drive-moves-2026-09-01.txt).

## The checkpoint

**The drive stack works end to end: command → motion → encoder feedback, all four basic moves.**
The operator confirmed by eye that each labelled move matched the robot's real motion — forward went
forward, turn-right rotated clockwise. So the sign convention is not just self-consistent, it is
**correct against physical reality.**

| Move | commanded (A/B dps) | left Δ (A) | right Δ (B) |
|---|---|---|---|
| FORWARD | −250 / +250 | **−366** | **+366** |
| BACKWARD | +250 / −250 | **+367** | **−367** |
| TURN RIGHT | −250 / −250 | −217 | −217 |
| TURN LEFT | +250 / +250 | +217 | +216 |

Forward/backward are clean mirrors (366 vs 367), turns symmetric (217 vs 216) — both motors respond
and agree.

## What this locks in (was assumed, now MEASURED)

- **Port A = LEFT wheel, port B = RIGHT wheel** — confirmed by watching.
- **The mirror sign flip:** robot-forward is `A: -v, B: +v` (`LEFT_FWD = -1`, `RIGHT_FWD = +1`).
  Recorded in [../hardware/port-map.md](../hardware/port-map.md) and
  [`src/hub_motors.py`](../../src/hub_motors.py) — the one UNVERIFIED note that guarded the drive
  layer is now CONFIRMED.
- **Direct drive:** motor axle straight to the wheel, so **1 wheel revolution = 360 encoder degrees**,
  no gearing to divide out. Distance per rev = π × wheel diameter — pending one ruler measurement of
  the diameter (`WHEEL_DIAMETER_MM`).

## Speed control — already have it

No separate demo needed. `motor.run(port, velocity)` takes velocity in **deg/s**; this run used
**250** against a measured ceiling of **930** (`motor.info` max_speed). So speed is simply the velocity
argument, anywhere in ±930 dps. `motor.set_duty_cycle(port, percent)` is the raw-power alternative.

## A free odometry datum

250 dps × 1.5 s should command 375°; the encoders logged **366°** — the missing ~9° is the
accel/decel ramp at the ends of a short move. Worth carrying: short moves lose a fixed ramp slice, so
distance estimates from commanded time will run slightly short unless the ramp is accounted for.

## Still open

- **Wheel diameter (mm)** — the last piece to turn every encoder degree into real distance. One ruler
  read. Until then, distances stay in encoder degrees / wheel revolutions.
- **Track width** and **turn-degrees per robot-degree** — the turn deltas (±217 for a `TURN_MS` burst)
  are raw; converting to "the robot rotated N degrees" needs the gyro cross-check while driving
  (KU-M9) and the track width. The IMU is the confirmation source, the encoders the primary — as the
  operator directed.
- **BLE telemetry during a drive** — needs the slot-upload path (`hub_programmer/slot_upload.py`,
  built, untested) so a program runs under the live Hub OS and streams over BLE.

**Related:** [../hardware/port-map.md](../hardware/port-map.md) ·
[../plans/competition-program-design.md](../plans/competition-program-design.md) ·
[hub-api-surface-2026-09-01.md](./hub-api-surface-2026-09-01.md)

## Latent bug the checkpoint data exposed (fixed 2026-09-01)

The measured directions — forward drives **A(left) −366, B(right) +366** — revealed a bug in our own
pure code that no host import check could catch. `odometry.Odometry.update()` computed
`d_center = (d_left + d_right) / 2` on the **raw** encoder degrees, and the raw readings are
equal-and-opposite on this mirrored chassis: `(−366 + 366)/2 = 0`. **A forward move integrated to zero
distance**, and the encoder-heading cross-check had the same fault (a forward move read as a large fake
turn).

Two sibling bugs, one root: `hub_motors.drive()` also applied **no** sign, so `drive(50, 50)` would
have *spun* the robot (left backward, right forward), not driven it forward.

**Fix:** the mirror convention now lives as `hub_api.LEFT_MOTOR_FORWARD_SIGN = -1` /
`RIGHT_MOTOR_FORWARD_SIGN = +1` (MEASURED), applied in `hub_motors.read_motor_degrees()` and
`drive()`, so everything downstream sees **forward-positive** values on both wheels. `odometry.py`
stays pure and mirror-agnostic. Verified on the host: the checkpoint's forward move now integrates to
**+178.9 mm** at a 56 mm `[ASSUMED]` wheel (`366/360 · π · 56`), `x = 0`.

**The lesson matches [ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md):** the import
boundary passed this happily; only real directions off the floor exposed it. Hardware is the check.

