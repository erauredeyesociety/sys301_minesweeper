# Runbook — Measure the Drivetrain

> **Purpose.** Replace the `[ASSUMED]` drivetrain constants in [../../src/config.py](../../src/config.py)
> with measurements taken on the real robot, on the real floor, in one class period.
> **Operator:** the **Builder** — the only person permitted to operate the robot.
> **At the laptop:** the **Programmer**, who types, reads the echo-back aloud, and writes numbers down.
> **Plan, ordering and drop list:** [../plans/bench-measurement-plan.md](../plans/bench-measurement-plan.md)
> **Status:** written 2026-08-25 with **no hub attached and no robot built**. Every statement about what
> the hub will do is **UNVERIFIED**. Nothing in this file may be reported as a result until it was run.
>
> Governing rules: [../directives/hardware-safety.md](../directives/hardware-safety.md) ·
> [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md) ·
> [../directives/automation-first.md](../directives/automation-first.md)

**Read § 0 before the cable goes in. Read the § 10 RESULT block before the first move, so you know what
you are filling in.**

---

## 0. Before anything moves

**The abort action, rehearsed before the first command.** The Builder presses the hub's centre button to
stop the program. Do this once, deliberately, on the very first low-velocity move — *before* you need it.
If you have never pressed it, you do not have an abort.

| Rule | Why |
|---|---|
| **First move of the session is short, slow, and cancellable** — one wheel revolution at low velocity. Never a full mission run as a first test | [../directives/hardware-safety.md](../directives/hardware-safety.md). A runaway with a wrong sign in the port map is the normal first-day failure |
| **Clear floor: the measured lane plus at least 1 m of run-off past the far end** | Every move is bounded by the script, but a wrong `--revs` is one keystroke away |
| **The Builder is the only person who touches the robot.** The Programmer plugs and unplugs the cable, and nothing else | Role separation is enforced at **−2 SB per violation** |
| **If any tool shows "Hub update required" — STOP.** Photograph it, change nothing, ask the operator | Blacklist. A Hub OS change is an ADR, never a side effect |
| **Never command a velocity above the motor's published ceiling** until M2b has run | What the hub does with an over-ceiling command is an open question, not a known behaviour — [../research/speed-envelope.md](../research/speed-envelope.md) |
| **Nothing here writes to the hub filesystem.** The CSV streams over the cable to the laptop | [../directives/hardware-safety.md](../directives/hardware-safety.md) |
| **Never open a blocking serial read.** Everything goes through the script, which has a timeout and exits | A hung read takes the rest of the class period with it |

**A step that cannot be run is recorded as `DROPPED` or `UNKNOWN`. It is never recorded as a pass.**

---

## 1. Kit — check this the class before, not on the day

| Item | Why | Have it? |
|---|---|---|
| Tape measure or metre rule, mm graduations | Every distance in this runbook | ☐ |
| Masking tape + a marker | Start line, lane centreline, fiducials | ☐ |
| A printed 360° protractor card, **or** the chord method in § 6.4 | Turn angle. The chord method needs only the tape measure | ☐ |
| A pointer on the robot — a Technic beam or a taped card with a point | Turn angle and lateral offset both need one repeatable point | ☐ |
| A straight run of clear floor: **measured lane + 1 m run-off** | M3, M7, M8 | ☐ |
| The **real** sticky-note pack | M10, and BM-0 if it has not run | ☐ |
| Charged hub battery, and the pack state written down at the start | Motor speed sags with battery state; it shifts every mm/s here | ☐ |
| Printed copy of the § 10 RESULT block, and a pen | The numbers get written on paper as they happen, not typed from memory later | ☐ |
| Phone camera | M1 motor photos, M10 before/after | ☐ |

**The surface matters and it is part of the answer.** Record which floor you are on. Carpet and tile give
different effective diameters with the same code, and a number without its surface is not a measurement
([../directives/honest-instrumentation.md](../directives/honest-instrumentation.md)).

---

## 2. Step M0 — bring-up and the echo-back assertion (5 min)

The Builder does **M1 in parallel with this** — it needs no hub. Do not idle waiting for the laptop.

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M0.1 | Programmer: `mkdir -p runs` first (it is not in the repo), then start the long idle log and **leave it running on the bench** — `./scripts/measure-drivetrain.py --move idle --seconds 2400 > runs/idle.csv` | Rows appear and keep appearing. **2400 s covers the whole 35-minute attended block plus pack-out** — 900 s would stop the log at T+15 and BM-9 would be measured over a quarter of the session | Start time |
| M0.2 | Read the script's echo-back **out loud** | API generation named (`spike3` / `spike2`), port map printed, assumed wheel diameter and track printed, manoeuvre and velocity printed | API generation; the port map as printed |
| M0.3 | If it exits with **port map incomplete** | It refuses to drive an unassigned port. Fill [../hardware/port-map.md](../hardware/port-map.md) and set the ports in [../../src/sensors.py](../../src/sensors.py) first | — |
| M0.4 | **M2a** — read the motor device type ID while you are here | **48** = Medium 45603 · **49** = Large 45602 · **65** = Small 45607. If the call does not exist on this Hub OS, **that is a result** — write "device ID call unavailable" and fall back to M2b | Both motors' IDs |
| M0.5 | **The first move.** `--move straight --revs 1 --velocity 100`. Builder presses the hub button mid-move to abort | The robot moves a short distance slowly, and **stops when the button is pressed**. Both wheels turn the same way | "abort verified" ☐ |
| M0.6 | Repeat M0.5 without aborting | The robot drives **forward**, not backward, and does not veer hard. A backward or spinning result is a sign error in the port map — fix it now, not at T+30 | — |

> **M0.5 is not ceremony.** It is the only step that proves the port map, the motor directions and the
> abort all work, and it costs 30 seconds. Every later step assumes it passed.

---

## 3. Step M1 — parts identity (5 min, no hub, runs during M0)

| # | Action | Expected observation | Record |
|---|---|---|---|
| M1.1 | Read the size moulded into **each** tyre sidewall | Something like `56 x 14`. Expect 56, 88 or 24 mm | Both sidewall markings |
| M1.2 | Lay the rule across the tread of **each wheel separately** | Two numbers. 24 / 56 / 88 mm are not confusable | **Two** diameters, to the nearest 0.5 mm |
| M1.3 | Compare the two numbers from M1.2 | If they differ, **stop and say so out loud.** A tenth of a millimetre of mismatch costs ~74 mm of lateral error over a **3.05 m** lane on the 112 mm Prime Lessons base the research doc tabulates — not our robot, but the right order of magnitude, and it dwarfs everything else in this session ([../research/motion-control-and-odometry.md](../research/motion-control-and-odometry.md) § Odometry arithmetic) | The difference, even if it is zero |
| M1.4 | Look at both output faces of each motor | Rotating disc on both faces with no axle crosshole ⇒ **Small 45607**, done. A crosshole on one face ⇒ Large **or** Medium — the fact sheets do not distinguish them here | Which case |
| M1.5 | Photograph both motors side by side, and both wheels | LEGO calls the Medium *"low-profile"*; bulk is the only visual separator and it is qualitative | Photo filenames |

Everything from M1 goes into [../hardware/build-record.md](../hardware/build-record.md) § 2 and § 3.

---

## 4. Step M2b — no-load velocity ceiling (8 min — **only if M0.4 failed**)

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M2b.1 | Builder chocks the robot so **both wheels are off the ground and spin freely** | Wheels clear of everything by at least their own diameter | ☐ |
| M2b.2 | `--move ramp --steps 100,200,300,400,500,600 --dwell 2`. **Stop at 600** — 700 is already above the Small's published 660 ceiling and § 0 forbids that until M2b.4. Only if `motor.velocity()` is still tracking the command at 600 (so it is **not** a Small) continue `--steps 700,800,900,1000` | Reported `motor.velocity()` rises with each step, then **plateaus** | The plateau value, per motor |
| M2b.3 | Read the plateau | ~**660 deg/s** ⇒ Small 45607, **definitive**. ~**1050–1110** ⇒ Large or Medium, and this test **cannot** separate them — 5.7 % apart, inside LEGO's own ±15 % tolerance | Which |
| M2b.4 | *Only with the operator's agreement*, command 1200 deg/s once — above every candidate's ceiling | Records whether the hub **clamps, raises, or misbehaves**. This is a documented open question and nobody has the answer | Verbatim behaviour |

---

## 5. Step M3 — effective rolling diameter under load (12 min) — **the keystone**

**Why the moulded number is suspect.** `WHEEL_DIAMETER_MM = 56.0` in
[../../src/config.py](../../src/config.py) gives a geometric circumference of 175.9 mm. **Prime Lessons
(a community deck, not LEGO)** uses **17.5 cm** in its worked code where the same deck's own geometry
says 17.6 ([../research/speed-envelope.md](../research/speed-envelope.md) § Wheel options). **That deck
gives no reason for the 0.6 % difference** — loaded-tyre deflection is this project's inference and is
**UNVERIFIED**; lesson rounding fits the evidence equally well. Either way the moulded number is not
established as the rolling number, and only a measurement settles it. **If the rolling diameter really is
load- and surface-dependent, M3.8 is what shows it** — two surfaces, two answers. If both surfaces give
π·56 to within the tape's resolution, that is also a result: record it and stop worrying about deflection.

**Run this open-loop — heading correction OFF.** That makes the lateral offset in M3.6 a clean signature
of wheel-diameter mismatch, which you get for free.

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M3.1 | Tape a **start line** across the lane. Tape a **fiducial** on the robot — a single point, at the side, over the drive axle | You can put the fiducial back on the start line the same way five times running | ☐ |
| M3.2 | Choose **N**, the number of wheel revolutions, so the run is **800–1200 mm** — N = 5 on a Ø56, N = 3 on a Ø88, N = 12 on a Ø24 | — | **N** |
| M3.3 | Align the fiducial to the start line. `--move straight --revs N --velocity 200 > runs/diam_1.csv` | The robot drives straight-ish and stops. It does **not** coast visibly past its stop | ☐ |
| M3.4 | Measure from the start line to the fiducial **along the direction of travel** | A number near `N × π × 56` if the wheels are Ø56 | `d₁` in mm |
| M3.5 | Repeat M3.3–M3.4 **five times total** | Five numbers that agree closely | `d₁…d₅` |
| M3.6 | On each trial, also measure the **lateral** offset of the fiducial from the lane centreline | A consistent same-side drift is the wheel-diameter-mismatch signature. This is **open-loop** drift and is **not** the M8 number — M8 runs with heading hold ON and measures what the controller fails to remove. Record them as two different quantities | Five lateral offsets |
| M3.7 | Run **once in reverse**, same N | Should match the forward median. A forward/reverse asymmetry is backlash or a dragging third contact point — a **mechanical** finding for the Designer | `d_rev` |
| M3.8 | Repeat M3.3–M3.5 on the **second surface**, if a second surface is reachable in the room | The answers **will** differ. That difference is the point | Second set + surface name |

### 5.1 Why 800–1200 mm and not one revolution

Tape-measure error is roughly fixed at ±2 mm however far you drive. Over one revolution of a Ø56 wheel
that is ±1.1 % of the answer; over five it is ±0.23 %. **The long run is how you get a 0.3 % measurement
out of a hardware-store tape** — which is the accuracy Borenstein says this measurement can reach
([../research/motion-control-and-odometry.md](../research/motion-control-and-odometry.md)). Going much
further trades that back for curvature: the tape measures a straight line and a curving robot travels an
arc, so a very long run under-reports the distance rolled.

### 5.2 Combining the trials

```
D_eff = d / (N * pi)          per trial

report:  median of the five D_eff values      <- this is the number that goes into config.py
         spread = max - min                   <- this is the number that goes into the finding
```

- **Median, not mean.** One trial where a wheel slipped must not move the answer.
- **If the spread exceeds 2 % of the median, do not average it away.** That is slip, a loose wheel, a
  dragging caster, or an inconsistent start alignment. Find the cause and re-run the set. A tight spread
  is what makes the number trustworthy; a wide spread that got averaged is a number that will betray you
  on Demo Day.
- Report `D_eff` to **0.1 mm** and no further. The tape does not support another digit.

---

## 6. Step M4 — track width from a turn that closes (10 min)

### 6.1 Why the ruler value is wrong

`TRACK_WIDTH_MM` is not "the distance between the wheels" as a ruler sees it. Borenstein defines it as
**the distance between the contact points of the two drive wheels**, and:

1. A compressed rubber tyre's contact patch is a **patch**, not a point, and its effective centre moves
   with load, camber and surface.
2. A ruler laid across the top of the chassis measures rims or tyre centrelines. It cannot see what the
   tyres are doing under the robot's weight.
3. During a spin turn both tyres **scrub sideways**. Where a scrubbing tyre actually pivots is not a
   geometric quantity at all — it is a friction outcome.

So calibrate against the use. **`b` is whatever number makes a commanded turn actually close.** The cost
of getting it wrong is not subtle: on the 112 mm Prime Lessons base the research doc tabulates, a 2 mm
error is 1.61° on a 90° turn and **86 mm** of cross-track over the following **3.05 m** lane — nearly two
lane pitches ([../research/motion-control-and-odometry.md](../research/motion-control-and-odometry.md)
§ Odometry arithmetic). That table is **not our robot**: `config.TRACK_WIDTH_MM` is currently the
`[ASSUMED]` placeholder **176.0 mm**, and the fractional error `db/b` is what carries, so read the table
for the order of magnitude and get the number from M4.

### 6.2 Turn the gyro-closed turn OFF for this test

If the turn is closed against the gyro, you are calibrating the gyro, not the track. This step measures
the **encoder** turn model. Turn heading closure back on afterwards for M8.

### 6.3 Procedure

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M4.1 | Place the robot with its pointer over a marked spot. Mark the floor where the **pointer tip** lands, and the pivot point directly under the robot's turn centre | Two marks: pivot `P`, and start `A` | ☐ |
| M4.2 | `--move spin --degrees 1080 --velocity 150 --gyro-close off > runs/track_cw_1.csv` | The robot spins in place three times and stops. It should not translate more than a few mm | ☐ |
| M4.3 | Mark where the pointer tip now lands: `B`. Measure the residual angle `A–P–B` | Small — a few degrees at most if the assumed track is close | `θ_actual = 1080 + residual` (sign it!) |
| M4.4 | Repeat for **3 trials clockwise, then 3 counter-clockwise** | Six values | `θ_cw₁…₃`, `θ_ccw₁…₃` |
| M4.5 | Read the gyro's own reported yaw for each run out of the CSV | An **independent** second opinion on the same turn | Six gyro values |
| M4.6 | Compute `b_actual` per § 6.5 and re-command 1080° with it | **The verification turn closes** — the pointer lands within the resolution of your angle measurement | ☐ closed / ☐ did not close |

### 6.4 Measuring the angle with only a tape measure

If there is no protractor: measure the straight-line chord `c` from `A` to `B`, and the radius `r` from
the pivot `P` to the pointer tip.

```
residual_deg = 2 * asin( c / (2 * r) ) * 180 / pi
```

Make `r` as large as the pointer allows — a longer pointer turns a 2° error into a bigger, more
measurable `c`. Record `r` and `c`, not just the angle, so the arithmetic can be re-checked later.

**The chord gives the magnitude only — you must sign it by eye.** Before the spin, mark the start point
`A` **and an arrow on the floor showing the direction of rotation.** If `B` lies *past* `A` in that
direction the robot **over-rotated** (`θ_actual > θ_commanded`); if `B` falls *short* of `A` it
**under-rotated**. Write the word "over" or "short" on the paper next to `c`, not just the number — an
unsigned residual inverts the § 6.5 conclusion.

### 6.5 Solving for the track

The encoder model converted your commanded turn angle into wheel travel using `b_assumed`. The encoders
delivered that wheel travel accurately (±3° at the motor), so any discrepancy in the angle the robot
*actually* swept is `b` being wrong:

```
b_actual = b_assumed * ( theta_commanded / theta_actual )

over-rotated  (theta_actual > commanded)  ->  the real track is SMALLER than assumed
under-rotated (theta_actual < commanded)  ->  the real track is LARGER  than assumed
```

Take the **median of the three CW trials** and the **median of the three CCW trials** separately.

> **⚠ The CW/CCW comparison is a diagnostic, not a formality.** If the two medians disagree by more than
> the spread *within* each direction, the residual is **not** a track-width error. A wheelbase error
> reverses sign between directions while a wheel-diameter mismatch keeps the same sign — that is
> Borenstein's own separation of the two error types
> ([../research/motion-control-and-odometry.md](../research/motion-control-and-odometry.md) § UMBmark).
> Do not split the difference into a `b` that fits neither. Write down that the two directions disagree,
> re-check M1.3 for a wheel mismatch and the third contact point for drag, and if it persists, book the
> full UMBmark run rather than papering over it here.

---

## 7. Step M7 — top ground speed: saturation or control loss? (10 min)

**Two different ceilings live in this measurement and they are not the same problem.** Motor saturation
means the drivetrain cannot go faster. Control loss means it *can*, and shouldn't. Only one of them is
fixed by buying a different motor.

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M7.1 | Use **the same lane you will use for M8** — the longest straight the room allows — and record its length `L`. Run-off clear, wheels on the ground, full robot weight | The taped line is unbroken end to end and there is ≥ 1 m of clear floor past the far end. **Do not use a different length from M8:** cross-track grows with `L²`, so an offset measured over 2 m cannot be compared against an allowance defined over a 3 m lane | `L` in mm |
| M7.2 | Pick the step ladder: 25 / 50 / 75 / 100 % of the identified motor ceiling. **If the motor is still unidentified, use 200 / 400 / 600 deg/s and stop there** | — | The ladder used |
| M7.3 | At each step: `--move straight --distance <L> --velocity <ω> > runs/speed_<ω>.csv`, **three trials** | Robot completes the lane and stops inside the marked run-off | Time per trial, from the CSV |
| M7.4 | Also stopwatch each run, independently of the CSV | The two agree within ~5 % | Stopwatch times |
| M7.5 | Measure the **lateral offset at the end of `L`** on every trial | It should stay small and roughly constant across the ladder — until it doesn't | Offsets, each labelled with `L` |
| M7.6 | Compute both speeds per § 7.1 | — | `v_ground`, `v_expected` |

### 7.1 Telling the two ceilings apart

```
v_ground   = L / t                                      <- what the robot actually did, L in mm
v_expected = pi * D_eff * omega / 360                   <- what the commanded wheel speed should give
                                                           (D_eff from M3 -- this is why M3 comes first)
```

| Signature | Reading |
|---|---|
| Reported `motor.velocity()` **plateaus below** the commanded value; `v_ground` plateaus with it; the yaw trace in the CSV stays smooth; lateral offset flat | **Motor saturation.** The drivetrain is at its ceiling. Note the plateau value — it is also a motor identification: ~660 ⇒ Small 45607 |
| `motor.velocity()` still **tracks** the command, but `v_ground` falls below `v_expected` by more than 5 % | **Wheel slip.** Not saturation. It is speed- and surface-dependent and it corrupts odometry distance, so record the surface |
| `motor.velocity()` tracks the command, `v_ground` tracks `v_expected`, but the **lateral offset grows** step over step and the yaw trace oscillates or ramps | **Control loss.** The heading loop, not the motor, is the limit — and it binds *lower* than the motor does |

**The stopping rule.** Stop at the first step where the lateral offset **over `L`** exceeds
`CROSS_TRACK_ERROR_MM` in [../../src/config.py](../../src/config.py) (`[ASSUMED]` 15 mm). That constant is
the allowance for **one full lane**, so this comparison is only valid because M7.1 makes `L` the same lane
M8 uses — if you were forced to use a shorter run, say so on the paper and treat the verdict as
provisional rather than rescaling it. **The previous step is the practical top speed**, and going faster than it is self-defeating: it
buys seconds on the lane and spends them on a narrower lane pitch and more lanes
([../findings/coverage-time-budget.md](../findings/coverage-time-budget.md)).

---

## 8. Step M8 — cross-track error over a real lane (20 min, or 7 for M8-lite)

This is the number the sweep design is built on. `CROSS_TRACK_ERROR_MM` feeds `lane_pitch_mm()` →
`lane_count()` → `sweep_path_mm()` in [../../src/config.py](../../src/config.py), and therefore the entire
run-time budget.

**Heading hold ON for this step** — this is the configuration the mission actually runs.

| # | Action / command | Expected observation | Record |
|---|---|---|---|
| M8.1 | Chalk or tape a **straight line as long as the room allows**, ideally 3 m. **Record the length `L`** | Cross-track scales with `L²`, so a number without its `L` is meaningless | `L` |
| M8.2 | Align the robot's centreline fiducial on the line at one end | Sighting along the line, the fiducial and the far end of the tape are collinear. Repeat the alignment twice more and satisfy yourself it lands the same way each time — a sloppy start is indistinguishable from cross-track error | ☐ |
| M8.3 | `--move straight --distance <L> --velocity <ω> --heading-hold on > runs/xtrack_<ω>_<n>.csv` | Robot tracks the line and stops at the far end | ☐ |
| M8.4 | Measure the perpendicular distance from the fiducial to the line at the far end. **That distance is `e`** | — | `e` |
| M8.5 | **Three trials each direction** at the mission speed | Six values | Six `e` values |
| M8.6 | **M8-lite stops here.** With time: repeat the whole set at two more speeds from the M7 ladder | Gives the *shape* of `e(v)` and therefore the speed at which heading hold degrades | Full table |
| M8.7 | Report the **median and the maximum**, per direction, per speed | The lane pitch must be set from the **maximum**, not the median — one bad lane is a missed note | — |

### 8.1 Reading the direction split

Drive the same physical lane both ways and compare where the error lands **in the room**:

- **Error mirrors** — the robot leans toward the *same physical wheel* both times ⇒ geometric: a
  wheel-diameter mismatch or a steady heading bias. Check M1.3.
- **Error stays on the same side of the room** both times ⇒ external: floor slope, or carpet grain
  ([../research/motion-control-and-odometry.md](../research/motion-control-and-odometry.md) open Q8 — no
  published magnitude exists for LEGO tyres, so ours would be the first number anyone has).

*This split is our own reasoning from Borenstein's error separation, not a transcription of it.* Treat it
as a hypothesis to check, not as an established result.

---

## 9. Step M10 — does the robot displace the notes? (3 min)

| # | Action | Expected observation | Record |
|---|---|---|---|
| M10.1 | Builder lays three notes across the lane, one square-on, one at 45°, one at the lane edge | ☐ | Photo **before** |
| M10.2 | Drive one full lane over them at the M8 speed | The robot passes over | ☐ |
| M10.3 | Photograph the same three notes from the same spot | **Nothing moved.** A note that shifts, folds, or sticks to a tyre is a *mechanical* result for the Designer, and a second pass over that lane would count a note that has moved | Photo **after**; mm moved |

Three minutes, and it is the only check on an assumption that is currently doing real work with nothing
behind it (KU-M10).

---

## 10. RESULT block — fill this in on paper, as it happens

```
=== DRIVETRAIN BENCH — RESULT BLOCK ===
Date ______________  Session ______  Start __:__  End __:__
Builder ____________________  Programmer ____________________
Surface ______________________  Lighting ______________________
Battery at start ______  at end ______      Robot build revision ______

M0  API generation ................ [ spike3 / spike2 ]   echo-back read aloud [ ]
    Port map as printed ........... ______________________________
    Abort tested .................. [ ]   Forward direction correct [ ]
M2a Motor device type IDs ......... L ______  R ______   ( 48=Med 49=Lrg 65=Sml )
    or: device ID call unavailable  [ ]
M1  Tyre sidewall markings ........ L ______________  R ______________
    Measured diameters ............ L ______ mm  R ______ mm   DIFFERENCE ______ mm
    Output faces .................. [ small / large-or-medium ]   photos ______
M2b No-load plateau ............... L ______ deg/s  R ______ deg/s   [ DROPPED ]
    Over-ceiling command did ...... ______________________________  [ NOT TRIED ]
M3  N revolutions commanded ....... ______
    d1 __________ d2 __________ d3 __________ d4 __________ d5 __________ mm
    D_eff median .................. __________ mm    spread __________ mm  ( <=2% ? [ ] )
    Reverse trial d_rev ........... __________ mm    asymmetry __________ mm
    Lateral offsets (5) ........... ____ ____ ____ ____ ____ mm
    Second surface ( __________ ) . D_eff __________ mm
M4  theta_cw  ..... ______ ______ ______   median ______  ( gyro said ______ )
    theta_ccw ..... ______ ______ ______   median ______  ( gyro said ______ )
    Directions agree within spread? [ yes / NO -> see 6.5, do not average ]
    b_assumed ______ mm  ->  b_actual ______ mm
    Verification turn closed ...... [ yes / no ]
M5  Loop rate, idle ............... ______ Hz    ( from t_ms in runs/idle.csv )
    Loop rate, driving ............ ______ Hz    ( from t_ms in a driving CSV )
    Sensor polled during that run?  [ no -> the figure above is driving-only / yes ]
    Streaming or buffered? ........ [ streamed / buffered ]
M9  Gyro drift .................... ______ deg over ______ s  = ______ deg/min
    Stuck at zero? ................ [ no / YES -> reboot and retest ]
    ( > 1.8 deg/min means long lanes are not viable on gyro alone )
M6  Spot diameter at h= ______ mm . ______ mm    [ DROPPED ]  ( no procedure in this runbook -- see 13 )
M7  Ladder used ................... ______________________  lane ______ mm
    v_ground per step ............. ____ ____ ____ ____ mm/s
    v_expected per step ........... ____ ____ ____ ____ mm/s
    Ceiling type .................. [ saturation / slip / control loss ]  at ______ mm/s
    PRACTICAL TOP SPEED ........... ______ mm/s
M8  Lane length L ................. ______ mm   heading hold [ on ]
    e, direction A ................ ____ ____ ____ mm
    e, direction B ................ ____ ____ ____ mm
    median ______ mm    MAXIMUM ______ mm   <- this is the one config.py gets
    Error mirrors / same room side  [ mirrors / same side / unclear ]
    Other speeds tested ........... ______________________  [ DROPPED ]
M10 Notes displaced? .............. [ no / yes, ______ mm ]  photos ______  [ DROPPED ]

DROPPED THIS SESSION: ____________________________________________
SURPRISES / anything that did not match this runbook: ____________
__________________________________________________________________
```

---

## 11. Filing the results — part of the procedure, not an afterthought

**Do this the same day.** A row closed in the register but not propagated is worse than an open row,
because the code still holds the guess while the register says we know
([../plans/known-unknowns.md](../plans/known-unknowns.md) § How to use this file).

| # | Do | Where |
|---|---|---|
| 11.1 | Write the finding: every number **with its units, surface, lighting, trial count, spread and date** | **`docs/findings/drivetrain-calibration.md`** (new), plus a row in [../findings/INDEX.md](../findings/INDEX.md) |
| 11.2 | Keep the raw CSVs alongside it | They are the evidence, and they let the arithmetic be redone without the robot |
| 11.3 | Update the constants and **strike the `[ASSUMED]` marker**, leaving the surface and date in the comment | [../../src/config.py](../../src/config.py): `WHEEL_DIAMETER_MM` (M3) · `TRACK_WIDTH_MM` (M4) · `SAMPLE_RATE_HZ` (M5) · `CROSS_TRACK_ERROR_MM` (M8 **maximum**) · `TRAVERSE_SPEED_MMS` (M7/M8) |
| 11.4 | Re-check the pure logic after 11.3. **`tests/persistent/` does not exist yet**, so today this is one command, not a suite: `python3 -c "import sys; sys.path.insert(0,'src'); import config; print(config.lane_pitch_mm(), config.lane_count(), config.sweep_path_mm())"` | A `ValueError` from `lane_pitch_mm()` means the measured cross-track error makes guaranteed coverage impossible at the assumed 76 mm target. **That is a real answer** — raise it as R-01, never loosen the check. When the floor is written, this row becomes "run `tests/persistent/`" |
| 11.5 | Record the motor variant, both wheel diameters, and the geometry | [../hardware/build-record.md](../hardware/build-record.md) § 2 and § 3 |
| 11.6 | Record the device on each port with the date a human watched it respond | [../hardware/port-map.md](../hardware/port-map.md) |
| 11.7 | Close the register rows — answer **+ source + date** | [../plans/known-unknowns.md](../plans/known-unknowns.md): KU-M3, KU-M4, KU-M5, KU-M8, KU-M9, KU-M10, KU-T3 |
| 11.8 | Write the session record, **including what was dropped and why** | `docs/session_records/YYYY-MM-DD_drivetrain-bench.md` |
| 11.9 | If M8's maximum blows the coverage budget, say so in writing that day | Risk **R-01** in [../plans/risk-register.md](../plans/risk-register.md); options are already costed in [../plans/2026-08-25-coverage-strategy-trade-study.md](../plans/2026-08-25-coverage-strategy-trade-study.md) |

---

## 12. When it goes wrong

| Symptom | Most likely cause | Do this |
|---|---|---|
| Script exits **port map incomplete** | Ports never assigned | Fill [../hardware/port-map.md](../hardware/port-map.md), set them in [../../src/sensors.py](../../src/sensors.py). Do **not** patch a port literal into the script |
| Robot drives **backward** or spins on M0.6 | A motor's sign or left/right is swapped | Fix the port map and the direction convention, then redo M0.5–M0.6. Every later number is wrong until this is right |
| M3 spread **> 2 %** | Slip, a loose wheel, a dragging third contact point, or inconsistent start alignment | Find the cause. **Do not average it away** — a wide spread averaged is a number that fails on Demo Day |
| M4 CW and CCW **disagree** | Not a track-width error — see § 6.5 | Record the disagreement, check M1.3, check the third contact point. Consider full UMBmark |
| Gyro reads **0.0 forever** | The documented SPIKE stuck-at-zero pathology | Reboot the hub and retest. Record that it happened — it becomes a Demo Day pre-run check |
| Loop rate far below 100 Hz | Expected. The 100 Hz figure is the hardware rate, not what a Python loop achieves | **This is the measurement, not a fault.** Record it and recompute `expected_width_samples()` |
| Any tool says **"Hub update required"** | — | **STOP.** Photograph, change nothing, ask the operator |
| The script hangs | It should not — it has a timeout | Kill it from the laptop. Do **not** open a terminal on the port to "have a look" |

---

## 13. What this runbook does not measure

- **BM-0, the colour go/no-go.** Owned by [../plans/verification-plan.md](../plans/verification-plan.md)
  § 3, scheduled 1 SEP, and expected to be done before this session starts. Not restated here.
- **Full UMBmark.** BM-8 measures the cross-track error the sweep design consumes. UMBmark separates
  *why* it is there, takes 30–40 minutes, and is only worth booking if BM-8 comes back over budget —
  [../plans/bench-measurement-plan.md](../plans/bench-measurement-plan.md) § What this plan does not do.
- **BM-6, the colour-sensor spot diameter.** It is specified in
  [../plans/bench-measurement-plan.md](../plans/bench-measurement-plan.md) (BM-6, 12 min, drop order 2nd)
  and the § 10 RESULT block keeps a line for it, but **no step-by-step exists here yet**. If it is
  attempted, write the procedure first — the method to copy is the bar-card step-across in
  [../research/color-discrimination.md § 5.1](../research/color-discrimination.md). Do **not** improvise
  it at the bench and record the number as if it were procedural.
- **Anything about the mission.** Nothing here counts a note.
- **Any build but this one.** These numbers die when the Designer changes the geometry. A rebuild gets a
  new revision row in the build record and this runbook runs again.

---

## Revision History

| Date | Change | By |
|---|---|---|
| 2026-08-25 | Created, unrun, no hub attached. Steps M0–M10 with the effective-diameter and closing-spin-turn methods, the saturation-vs-control-loss discrimination, a paper RESULT block, and the filing checklist. | Claude |
| 2026-08-26 | **Adversarial audit fixes.** § 5 no longer attributes the Prime Lessons 17.5 cm figure to LEGO, and no longer states loaded-tyre deflection as fact (the source marks it UNVERIFIED inference). M1.3 / § 6.1 sensitivity figures re-labelled to their real basis — a 3.05 m lane on the 112 mm Prime Lessons base, not our 176 mm placeholder. M3.6 no longer calls open-loop drift "the M8 result arriving early". Idle log 900 s → 2400 s (900 stopped it at T+15 of a 35-min session) and `mkdir -p runs` added. M2b.2 ramp capped at 600 deg/s so it stops violating § 0's own over-ceiling rule. M7 now runs on the same lane length `L` as M8 — an offset over 2 m cannot be compared against a per-lane allowance. § 6.4 chord method given a way to sign the residual. § 11.4 stopped pointing at a `tests/persistent/` that does not exist. RESULT-block § 8 → § 10; M6 declared to have no procedure; M5 loop-rate line no longer pre-labels the run as "sensing". | Claude (audit) |
