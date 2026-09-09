# Lesson — A feedback loop ships with a divergence guard, or it does not ship

**WHEN** you add any closed-loop correction on real hardware — a heading hold, a line follower, a
speed regulator — and the **sign** of the feedback depends on a convention you have not measured
end to end.

**DON'T** ship it with the sign as a comment saying "flip this if it goes the wrong way", and
**DON'T** ship it without a guard that detects the loop running away.

**BECAUSE** an unverified sign is a coin flip, and the wrong half is not a small error — it is
*positive feedback*. It does not drift slightly; it saturates the correction and stays there.

## What happened, 2026-09-08

`examples/follow_tape.py` gained a gyro heading hold whose sign was reasoned out from
`examples/motor_poc.py`'s turn direction and marked `[UNVERIFIED]`, with a comment saying to flip
`HOLD_SIGN` if the robot diverged. The reasoning was wrong.

The robot **drove in circles for the entire 40-second run**
(`tmp/telemetry/20260908T114003-followtape-0000102164.csv`):

```
#end reason=time_cap corners=3 rows=670 corrections=89 tape_seen=89 hold=477 deg=3842 mm=2129
```

The left encoder moved **3842°** against the right's **1490°** — a fixed **2.55:1** ratio for the
whole run. A correction pinned at its clamp predicts `(80+30)/(80-30) = 2.2`. So the loop saturated
in one direction on the first few ticks and never left. Yaw wrapped through ±180° repeatedly.

The operator had to pick the robot up and move it, and the run produced no usable following data.

## The two rules

1. **Derive the sign from a measurement, not from another program's convention.** The sign here was
   inferred from which way `motor_poc.py` turns while waiting for yaw to increase. That inference was
   one step too long, and it was wrong. One logged straight run with a deliberate nudge would have
   settled it in 20 seconds.
2. **Guard the loop.** A correction stuck at its clamp in the *same direction* for N ticks is not
   correcting — it is running away. Detect that, disable the loop, drive open-loop, and **record it**
   in the run trailer so a silent fallback can never be mistaken for a healthy run. A robot driving
   straight is recoverable; one circling for 40 s is a wasted session.

Both are now in `examples/follow_tape.py`: `HOLD_SIGN = -1` with the measurement that settled it, plus
`HOLD_DIVERGE_TICKS` and a `diverged=` field in the `#end` line. The guard also beeps, so the
operator hears the loop give up rather than discovering it afterwards in the log.

## The wider point

This project has no test suite by decision ([ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md)),
so the robot on the floor *is* the test. That makes a self-protecting failure mode worth more than a
correct-looking constant: the guard turns "the run was wasted" into "the run degraded and told us so".
See also [say-which-kind-of-verified.md](./say-which-kind-of-verified.md) — `[UNVERIFIED]` on a
load-bearing sign is a warning that something must be *measured*, not a licence to ship it.
