# Finding — the colour sensors wobble in a ~1 inch circle (loose mount)

**Date:** 2026-09-03 · **Source:** OPERATOR-REPORTED build fact (no bench measurement yet) ·
**Status:** a hardware constraint that shapes the sweep and the map, not a bug to fix (no budget to fix it).

## The fact

The two colour sensors (ports C/D) are **loosely attached**. Each is held by a single peg near its
**rear/side** and points down at the floor; the team had no budget for a rigid mount. As a result each
sensor can **pivot about that peg**, so its sensing point is not fixed — the operator estimates the
centre of the footprint stays within about a **1 inch (~25 mm) diameter circle**. So the robot's own
position is known far better than *where each colour sample was actually taken*.

**Do not chase the datasheet for a tighter number.** The uncertainty is MECHANICAL (peg slop), not
optical (sensor-body size), so the LEGO Color Sensor 45605 dimensions would not improve the estimate —
the ~1 inch figure is dominated by how freely the peg lets the sensor swing, which only a bench
measurement of *this* build (BM-9 below) can pin down. The operator's ~25 mm is the working figure.

## Why it matters (three consequences, in priority order)

| Consequence | Effect on the design |
|---|---|
| **1. Line-following is unreliable** | Modes M2/M3/M5 in [competition-movement-options](../plans/competition-movement-options-2026-09-03.md) use the two-sensor front bar as a left/right error signal. A wobbling sensor moves that signal by up to ~25 mm on its own, which swamps a fine steering error. **Prefer the odometry lawnmower (M4) + floor-anomaly detection over line-centring.** |
| **2. Sweep lanes must overlap generously** | A mine must not hide in a gap the wobble opens between lanes. Effective coverage width per pass = sensor footprint **minus** the wobble diameter, so **lane spacing must be tighter than footprint − 25 mm**, and lanes should overlap by **≥ 25 mm + one spot diameter**. This is a coverage-time cost (more, closer lanes) — it interacts with the units question in [coverage-time-budget](./coverage-time-budget.md). |
| **3. A detected mine's MAP position carries ±~12.5 mm** | Presence detection is unaffected (a mine still reads as a strong anomaly — see [detection-telemetry-build](./detection-telemetry-build-2026-09-03.md)). But the *logged position* of each mine inherits half the wobble circle as error, so the dead-reckoned mine map's per-point uncertainty is at least ±12.5 mm before odometry drift is added. Record it as the map's floor error, don't pretend the position is exact. |

Calibration is **not** harmed and may even be helped: the run-start floor burst already samples in
`CALIBRATION_PLACEMENTS` spots, and a wobbling sensor naturally samples a little more of the floor's
spread — which the multi-band floor model in [floor_anomaly](../../src/floor_anomaly.py) is built to absorb.

## What this does NOT change

The detection **method** is unaffected: the anomaly metric works in chromaticity, which is invariant to
the small height changes a pivot introduces, and the four-state counter's width gate already rejects
too-narrow/too-wide events. The wobble is a **geometry/coverage** problem (where did I look, and did I
leave a gap), not a **signal** problem (can I tell a mine from the floor).

## Open bench test

- **BM-9 — wobble amplitude.** With the robot still, nudge each sensor to the extremes of its peg play
  and log C/D `rgbi` + reflection over a fixed floor spot; separately, measure the footprint centre
  travel with a ruler. Confirms (or corrects) the ~25 mm and yields the real number for lane spacing.
  Pairs naturally with BM-3 (effective wheel diameter) and the spot-diameter measurement M2 needs.

**Related:** [competition-movement-options](../plans/competition-movement-options-2026-09-03.md) ·
[detection-telemetry-build](./detection-telemetry-build-2026-09-03.md) ·
[coverage-time-budget](./coverage-time-budget.md) · `src/floor_anomaly.py`
