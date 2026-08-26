# Telemetry and offline analysis — FORWARD-PLAN

**Type:** FORWARD-PLAN · **Status:** parked, to be revisited when the hub is connected · 2026-08-25

## Why this matters more now

[ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md) removed the test suite. Verification is
the robot on the floor. That is defensible, but it leaves a gap: **watching a robot cross a room tells
you it missed a note — not why.** Telemetry closes that gap, and it closes it with data about the
physical world, which a test never could.

It also directly serves the thing the operator asked for: *"very basic data analysis python scripts to do
math so that you don't have to do it live."* A run produces a file; the file gets analysed on the laptop;
the analysis says what to change. No live guessing, no re-running the robot to ask a second question.

## What we would want to capture

Per sample, at whatever rate the hub can actually sustain (**UNVERIFIED** — the 100 Hz figure is a LEGO
spec for the sensor, not a measured Python loop rate):

| Field | Why |
|---|---|
| timestamp / tick | Establishes the real loop rate — currently a guess |
| left, right motor degrees | Odometry, and slip when they disagree with the gyro |
| gyro yaw | Heading truth; drift over a run |
| colour reflection | The detection signal itself |
| raw RGB, if available | Lets classification be re-run offline against different thresholds |
| distance, if fitted | Boundary events |
| detector state + count | Ties a count change to the samples that caused it |

**The rule that makes this worth doing: log the RAW samples, not just the decisions.** A run logged
raw can be re-analysed against a different threshold, a different debounce, a different classifier —
without touching the robot. A run that logged only "count = 7" is one number and cannot answer a second
question. Class time is the scarcest resource; a raw log converts one run into many experiments.

## How it might get off the hub — options, none tried

| Route | How | Trade-off |
|---|---|---|
| **Write to a file on the hub, pull it after** | Hub writes CSV to its own filesystem; retrieve over USB after the run | **Likely first choice.** No live link to keep alive, works during a free-running demo. Needs hub filesystem write — check against the blacklist first (writing our own data file is not a firmware operation, but confirm) and against free space |
| **Print over USB serial** | `print()` per sample; the laptop captures the stream | Simplest by far, and the REPL is already proven to work over `/dev/ttyACM0`. But the robot is tethered, which changes how it drives — unusable for the real demo, fine for a bench run |
| **Bluetooth** | Hub has BT; stream to the laptop | Untethered, so a real run can be logged. **UNVERIFIED** whether stock firmware exposes a usable BT data channel to a user program, and at what rate. This is the operator's suggestion and it is the right ambition — it needs research before it is a plan |
| **Buffer in RAM, dump at end of run** | Accumulate, print/write once when the sweep finishes | Avoids per-sample I/O cost distorting the loop rate. **Bounded by hub RAM** — see [../research/hub-compute-limits.md](../research/hub-compute-limits.md); a 3-minute run at even 20 Hz is thousands of samples |

**Do not choose yet.** The choice depends on the Hub OS generation, the achievable loop rate, and
whether BT is reachable from a user program — all unknown until the hub is connected.

## The analysis side

Small, plain Python on the laptop, in the spirit of `inventory.py` — a script anyone can edit, not a
framework:

- **`analyse-run.py`** — read a run CSV and report: actual loop rate, gyro-vs-encoder heading divergence
  over time, cross-track error per lane, every detection event with its width and peak, and the count
  the logic *would* produce at a different threshold.
- **`plot-run.py`** — optional, only if a picture beats a table. Reflectance against distance with the
  thresholds drawn on it makes a mis-set threshold obvious in a way a column of numbers does not, and it
  is a strong figure for the Intro Report.

Both operate on files. Neither touches the robot. Both are re-runnable against an old log, which is the
whole point.

## What has to be true first

1. The hub is connected and its API generation identified — [../runbooks/hub-identification.md](../runbooks/hub-identification.md).
2. The achievable loop rate is measured — [bench-measurement-plan.md](./bench-measurement-plan.md).
3. We know whether hub filesystem writes are acceptable and whether BT is reachable from a user program.

Until then this is a plan, not a task. **Nothing here has been attempted.**
