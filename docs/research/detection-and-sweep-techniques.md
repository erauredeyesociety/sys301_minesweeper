# Detection and Sweep Techniques for a SPIKE Prime "Minesweeper"

**ERAU SYS 301 — external research note**
Scope: how to detect discrete flat floor targets and how to sweep a bounded floor area, using only a LEGO
Education SPIKE Prime Large Hub (45601), one Color Sensor (45605), one Distance Sensor (45604), one Force
Sensor (45606), the hub IMU, and motor encoders. Stock LEGO firmware, zero budget.

> **Provisional mission assumption.** Targets are flat sticky notes (standard Post-it = 76 mm x 76 mm,
> [3M](https://www.post-it.com/3M/en_US/p/d/v101665017/)) lying on a classroom floor. Every place where a
> different target type (3D object, colored tile, metal disc) would change the recommendation is flagged
> **[IF TARGETS DIFFER]**.

---

## Summary — the nine things that matter

1. **Use reflected light, not color ID.** `color_sensor.reflection(port)` returns 0-100 % and is the only
   mode that answers "is something non-floor under me?" without caring what color it is. Color mode
   silently fails on non-LEGO-colored printed surfaces — the Seshans document exactly this failure on the
   FLL mat ([flltutorials.com/.../FindingLines.pdf](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf)).
   LEGO's own competition curriculum agrees: "Reflected Light Intensity mode of the Color Sensor will give
   maximum precision"
   ([Training Camp 3](https://education.lego.com/en-us/lessons/prime-competition-ready/training-camp-3-react-to-lines/)).
   Consider `color_sensor.rgbi(port)[3]` (overall intensity, 0-1024) instead of `reflection()` if you need
   ~10x finer quantisation for thresholding.
2. **The binding constraint on this mission is the sensor swath, not navigation.** One downward color
   sensor senses a spot roughly a centimetre wide. To *guarantee* a 76 mm note is crossed, lane pitch must
   be `<= 76 mm - 2 x (cross-track error)`. That is 36-60 mm of lane pitch, which sets your arena size
   budget far more tightly than battery or gyro drift do. Do this arithmetic before you build. See
   [Coverage pattern comparison](#coverage-pattern-comparison).
3. **Calibrate at run start, on the actual floor.** Do not hard-code thresholds. Capture floor reflectance
   during the first 1-2 seconds of the run and derive thresholds from it.
4. **Hysteresis + minimum dwell, always.** A single threshold on a noisy 100 Hz stream double-counts. Two
   thresholds (Schmitt trigger) plus a minimum-dwell timer is the standard fix and costs ~15 lines of code.
5. **Boustrophedon (lawnmower) is the right coverage pattern**, with the gyro holding heading on the
   straight legs, a **wall re-square at the end of every lane**, and the *lane index* — not dead-reckoned XY
   — being the thing you trust. The CPP literature's own answer to "how do I sweep without localization" is
   to plan on cell *boundaries* precisely because they are observable and the interior is not.
6. **Do the UMBmark calibration.** Borenstein & Feng took a robot from 310 mm of systematic error over 16 m
   of travel down to 26 mm by calibrating two constants. It costs an afternoon and it is the single highest-
   leverage action available to you, whatever pattern you pick.
7. **Set expectations at ~85 % coverage, not ~99 %.** That is the measured sim-to-real gap on a comparable
   robot, and the misses concentrate at seams. Instrument your seams.
8. **De-duplicate by geometry, not by position memory.** Compare only *adjacent* lanes at similar
   along-track distance. Position-tagged de-duplication needs global accuracy you will not have after 2-3
   minutes.
9. **The distance sensor is a boundary sensor with a 50 mm blind zone and a +/-35 degree cone; the force
   sensor is your fallback when the distance sensor lies.** Ultrasound is unreliable against carpet, cloth
   and angled surfaces, which is exactly what a classroom arena border is likely to be made of.

---

## Verified hardware facts

All values below are quoted from the official LEGO Education technical-specification PDFs linked from the
[SPIKE Prime product-info page](https://education.lego.com/en-us/teacher-resources/lego-education-spike-prime/support-technical-info/lego-education-spike-prime-support-technical-info-product-info/).

### Color Sensor 45605 — [techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt62a78c227edef070/5f8801b9a302dc0d859a732b/techspecs_techniccolorsensor.pdf?locale=en-us)

| Property | Official value |
|---|---|
| Sensor sample rate | **100 Hz** |
| Optimal reading distance | **16 mm** ("depending on object size, color, and surface") — same figure for color mode *and* reflectivity mode |
| Reflectivity output range | 0 % = "non-reflective/nothing", 100 % = "very reflective" |
| Ambient light output range | 0 % = dark, 100 % = bright |
| Color output | No object + 8 LEGO colors (White 01, Blue 23, Black 26, Green 28, Yellow 24, Red 21, Medium azur 322, Bright reddish violet 124) |
| Illuminant | 3 x white LEDs, **4000 K**; cannot be driven as a light while sensing |

Two important consequences of that table:

- The emitter is **white**, not the EV3's red. Confirmed independently by Prime Lessons: "Unlike the EV3,
  reflectivity is with white light, not a red light"
  ([SP3ColorSensor.pdf](https://primelessons.org/en/ProgrammingLessons/SP3ColorSensor.pdf)). Note that the
  Seshans' *older* FLL Tutorials deck still says "shines a red light"
  ([FindingLines.pdf](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf)) — that
  sentence is EV3 legacy text and is wrong for SPIKE. The official spec (4000 K white) wins.
- White illumination means a **yellow** Post-it and a **pink** Post-it will *both* read brighter than most
  dark floors, but they will not read the *same* value as each other. This is why you threshold on
  "different from floor", not on an absolute number. See [Edge-counting](#edge-counting-state-machine).

### Distance Sensor 45604 — [techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt64c2b9534cf10f68/5f8801b8bc43790f5c4389ea/techspecs_technicdistancesensor.pdf?locale=en-us)

| Property | Official value |
|---|---|
| Technology / sample rate | Ultrasonic, **100 Hz** |
| Normal range | **50-2000 mm, +/- 20 mm** |
| Fast range mode | **50-300 mm, +/- 15 mm** |
| Entrance angle | **+/- 35 degrees** ("varies according to the distance") |
| Output resolution | 1 mm |

> **Spec discrepancy — flag this in your report.** The 45604 *marketing* page claims
> "1-200cm range with +/- 1cm accuracy"
> ([education.lego.com](https://education.lego.com/en-us/products/lego-technic-distance-sensor/45604/)),
> but the engineering spec sheet says 50-2000 mm +/- 20 mm. Design to the spec sheet: **+/- 20 mm, and
> nothing closer than 50 mm.**

### Force Sensor 45606 — [techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt23df304b05e587b2/5f8801ba721f8178f2e5e626/techspecs_technicforcesensor.pdf?locale=en-us)

| Property | Official value |
|---|---|
| Sample rate | 100 Hz (1 kHz internal in force-filter "peak" mode) |
| Touch activation | zone **0-2 mm**, firmware threshold 1 mm +/- 0.5 mm, force **0.5-1.0 N +/- 10 %**, binary output |
| Force sensing | zone 2-8 mm, 2.5-10 N, 0.1 N steps, **+/- 0.65 N accuracy** |

The plunger only travels **8 mm total**. That is the entire mechanical budget for a bumper — design
accordingly (see [Sensor role assignment](#sensor-role-assignment)).

### Large Hub 45601 — [techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltf512a371e82f6420/5f8801baf4f4cf0fa39d2feb/techspecs_techniclargehub.pdf?locale=en-us)

Six-axis motion sensor (3-axis accel + 3-axis gyro), 6 LPF2 ports, 5x5 white LED matrix, MicroPython OS.
**LEGO publishes no gyro drift, noise-density or bias-stability figure** — the sheet lists only the modes it
can report. Any drift number is something you must measure yourself.

### Large Angular Motor 45602 — [techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltb9abb42596a7f1b3/5f8801b5f4c5ce0e93db1587/le_spike-prime_tech-fact-sheet_45602_1hy19.pdf?locale=en-us)

| Property | Official value |
|---|---|
| Encoder | **360 counts/rev** (1 count = 1 deg at the output axle), **accuracy <= +/- 3 deg** ("tolerances in the sensor combined with the gearbox slack"), 100 Hz update |
| Speed | 175 RPM no load; **135 RPM +/- 15 % at max efficiency** (8 Ncm); 25 Ncm stall |

**+/- 3 degrees of encoder+backlash error is your odometry noise floor before the wheels ever touch the
floor** — ~1.5 mm on a 56 mm wheel. Slip dominates instead.

### SPIKE App 3 Python API surface actually available

From the auto-generated API reference built from LEGO's own help documents
([jvolkening.github.io/lego-spike-python-v3-docs](https://jvolkening.github.io/lego-spike-python-v3-docs/index.html)):

| Call | Returns |
|---|---|
| `color_sensor.reflection(port)` | int, 0-100 % |
| `color_sensor.color(port)` | int enum, map via the `color` module |
| `color_sensor.rgbi(port)` | `tuple[red, green, blue, intensity]`, **each 0-1024** |
| `distance_sensor.distance(port)` | int mm; **returns `-1` when it cannot read a valid distance** |
| `force_sensor.force(port)` | int **decinewtons**, 0-100 |
| `force_sensor.pressed(port)` | bool |
| `motion_sensor.tilt_angles()` | `(yaw, pitch, roll)` in **decidegrees**, range **-1795 to 1800**; negative = clockwise |
| `motion_sensor.reset_yaw(angle)` | sets the yaw offset |
| `motion_sensor.stable()` | bool — "whether or not the hub is resting flat" |
| `motion_sensor.angular_velocity(raw_unfiltered)` | `(x, y, z)` in **decidegrees/second** |
| `motor_pair.move(pair, steering, *, velocity, acceleration)` | continuous move |
| `motor_pair.move_for_degrees(pair, degrees, steering, *, velocity, stop, ...)` | awaitable |
| `motor_pair.move_tank(pair, left_velocity, right_velocity)` | continuous tank move |

Three practical gotchas that fall straight out of this table:

- **There is no ambient-light function in the SPIKE App 3 `color_sensor` module.** It exposes only
  `color()`, `reflection()` and `rgbi()`. Ambient-light sensing exists in the *hardware* (see the spec
  sheet above) and existed in the SPIKE 2 API as `ColorSensor.get_ambient_light()`
  ([primelessons ColorSensor.pdf](https://primelessons.org/en/PyProgrammingLessons/ColorSensor.pdf)), but
  on App 3 firmware you cannot call it. **Do not design an ambient-light-compensation scheme around an API
  you do not have.** (UNVERIFIED whether a later App 3 point-release re-added it — check your installed
  version.)
- `distance_sensor.distance()` returning **-1** is not an error to swallow; it is your most common reading
  when pointed at empty space, carpet, or an off-axis wall. Every consumer of it must handle -1 explicitly.
- `tilt_angles()` yaw is in **tenths of a degree**, so `yaw_deg = motion_sensor.tilt_angles()[0] / 10`.
  Getting this wrong by 10x is the single most common SPIKE 3 porting bug.

---

## Recommended sensing approach

### Which color-sensor mode for "target present / not present"?

**Use `reflection()` (or `rgbi()[3]`). Do not use `color()`.**

Reasoning, with sources:

- **Color mode is a nearest-neighbour classifier against LEGO's own 8 brick colours** (listed with exact
  RGB in the spec sheet). Anything not close to one of the eight is misclassified. The Seshans document the
  failure on printed material: "Since the mat's printing does not match LEGO brick colors the colors the
  sensor reports are often unpredictable. What looks green to you may look be closer to LEGO black than LEGO
  green" ([FindingLines.pdf](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf)).
  Sticky-note pastels are exactly that kind of desaturated printed colour.
- **Color mode spatially averages.** Same source: "If it sees a bit of yellow and a bit of blue - it may
  report the color as green." At a target *edge* colour mode reports a third colour that is neither — fatal
  for edge counting.
- **Reflected light is monotonic and floor-relative.** One scalar, one threshold pair, no classifier. You
  don't care that the note is yellow, only that it differs from the floor.
- **`rgbi()[3]` gives 0-1024 instead of 0-100** — free extra quantisation if floor/target contrast is small.
  **UNVERIFIED:** whether `rgbi()` runs at 100 Hz and whether channel 3 is a simple sum. Measure first.

**[IF TARGETS DIFFER]** If targets are *3D objects* (bricks, cups, discs) rather than flat notes, the
downward color sensor is the wrong sensor entirely — a forward-facing distance sensor sweeping for
sub-2000 mm returns, or the force sensor as a physical bump-counter, becomes primary. If targets are
*distinctly and consistently coloured LEGO-standard* colours (a red brick vs a white floor), `color()`
becomes viable and gives you free target *classification* on top of detection.

### Mounting geometry

| Parameter | Recommendation | Basis |
|---|---|---|
| Height above floor | **16 mm** nominal (2 LEGO modules) | Official spec "optimal reading distance: 16 mm" |
| Orientation | Perpendicular to floor, facing straight down | LEGO EV3 guide: "the sensor must be held at a right angle, close to - but not touching - the surface it is examining" ([EV3 color sensor guide PDF](https://le-www-live-s.legocdn.com/sc/media/images/resource-site/files/ev3_chromebook_userguide_us_color_sensor-169c6ea887da48723fa61f7a353b3f87.pdf)) |
| Position on chassis | **Ahead of the drive axle, on the robot centreline** | Puts the detection point ahead of the turn centre so a target is sensed before the wheels disturb it |
| Rigidity | Braced against pitch — do not cantilever it off a long beam | Height error directly changes reflectance |

The 16 mm figure is not folklore. Prime Lessons flags that LEGO's own reference build gets it wrong: "The
color sensor on ADB (Advanced Driving Base in SPIKE Prime) is mounted at about 8mm off the ground, but the
optimal distance for mounting the sensor according to the specs is 16mm. When using this robot design,
**Black does not read correctly in Color Mode** using electrical tape lines or a FIRST LEGO League challenge
mat." They ship a modification that raises the sensor by one LEGO module specifically to fix this
([SP3ColorSensor.pdf](https://primelessons.org/en/ProgrammingLessons/SP3ColorSensor.pdf)). **If you copy
ADB verbatim you inherit a known-bad sensor height.**

**Carpet caveat.** 16 mm is measured to the *sensing surface*. On carpet, pile height is part of the gap
and it varies as the robot rolls (and compresses under the wheels). A 5 mm pile that compresses to 2 mm
under load is a 3 mm swing in effective sensing distance, i.e. ~19 % of your nominal gap. Expect
substantially noisier reflectance on carpet than on tile. Practical mitigations: mount slightly higher
(18-20 mm) so pile variation is a smaller fraction of the gap, and lean harder on hysteresis and dwell
filtering. **UNVERIFIED:** no published measurement of SPIKE reflectance variance on carpet was found.
Measure it (see [Open questions](#open-questions)).

### Ambient-light shielding

Since you cannot read ambient light on App 3 (see gotchas above), shielding is your only ambient defence.

- The physical case is that room light adds an offset to the reflected signal and, under bright light,
  *compresses* the usable dynamic range. **UNVERIFIED:** I could not find an authoritative measurement of
  this effect on the SPIKE 45605. The marketing page claims the sensor works "from darkness to bright
  sunlight" ([education.lego.com](https://education.lego.com/en-us/products/lego-technic-color-sensor/45605/))
  but nowhere claims *constant sensitivity* across that range. Treat ambient robustness as unproven and
  design the shroud anyway — it is free.
- The ORTOP FLL wiki independently makes the same mode recommendation this document makes: sensor colours
  "may not match the colors on the annual challenge mat. In that case, using the reflected light mode of
  the sensor may be a more accurate way to detect or follow a line"
  ([ortop.org](https://ortop.org/wiki/index.php/FIRST_LEGO_League_Challenge_Sensors)).
- What practitioners actually build: a skirt or shroud of black LEGO panels/beams around the sensor,
  extending down to within a few millimetres of the floor, blocking the low-angle room light and the
  robot's own shadow edge. Keep it black (matte) so it does not itself bounce the emitter light back.
- **Do not seal it against the floor** — a skirt that drags on carpet will snag and will also change the
  effective sensing height.
- **Recalibrate whenever you move the arena.** Overhead fluorescents vs a window on a sunny afternoon are
  different optical environments, and your calibration is the compensation mechanism you actually have.

### Speed, dwell and sampling — the numbers

The sensor samples at 100 Hz, i.e. one sample every 10 ms. For a 76 mm target and forward speed `v`:

```
dwell_time_on_target = 76 mm / v
samples_on_target    = 100 Hz * dwell_time
```

| Speed | Dwell over a 76 mm note | Samples |
|---|---|---|
| 150 mm/s | 507 ms | ~51 |
| 250 mm/s | 304 ms | ~30 |
| 400 mm/s | 190 ms | ~19 |
| 700 mm/s | 109 ms | ~11 |

Even at 700 mm/s you get ~11 samples across a note, so **sampling rate is not your limiting factor** —
you can afford a generous minimum-dwell debounce. Drive as fast as your traction and heading control allow;
the sensor will keep up. The real speed limit is wheel slip degrading odometry, not the sensor.

**[IF TARGETS DIFFER]** If targets are small (a 20 mm dot), redo this table. At 20 mm and 400 mm/s you get
only 5 samples and dwell debounce starts eating real detections.

---

## Edge-counting state machine

This is the heart of the deliverable. A raw 100 Hz reflectance stream cannot be turned into a count with a
single `if value > threshold: count += 1`. Four mechanisms are needed, in this order.

### 1. Run-start calibration (mandatory)

The Seshans state "You do not need to calibrate your color sensor on a SPIKE Prime"
([FindingLines.pdf](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf)). **Correct for
their problem, wrong for yours.** They mean you need not run an EV3-style white/black *sensor* calibration,
because SPIKE's factory scale is consistent. It does **not** mean you can hard-code "target = reflection >
60" — dark grey carpet, beige VCT and light laminate span most of the 0-100 range on their own. So: skip
sensor calibration, but **always do floor characterisation**.

```
CALIBRATE_FLOOR():
    # Robot drives slowly forward over a stretch of BARE floor with no targets.
    # ~1.5 s at low speed. Operator's job is to guarantee that stretch is clean.
    samples = []
    start_motion(slow)
    for t in 0 .. 1500 ms step 10 ms:
        samples.append(read_scalar())     # reflection() or rgbi()[3]
    stop_motion()

    floor_mean = mean(samples)
    floor_sd   = stdev(samples)
    floor_min  = min(samples)
    floor_max  = max(samples)

    # Sanity gate: refuse to run if the floor itself is not stable.
    if floor_sd > MAX_ACCEPTABLE_SD:      # tune; carpet will be worse than tile
        abort("floor too noisy - reseat sensor / check height")

    return floor_mean, floor_sd, floor_min, floor_max
```

Then derive thresholds *from measured noise*, not from guesses:

```
DERIVE_THRESHOLDS(floor_mean, floor_sd, target_mean):
    # target_mean comes from a one-time bench measurement of a note on this floor,
    # OR from a second calibration pass where the operator places one known target.
    contrast = abs(target_mean - floor_mean)

    if contrast < 6 * floor_sd:
        warn("insufficient contrast - expect misses; change target colour or floor")

    midpoint  = (floor_mean + target_mean) / 2
    band      = max(HYST_MIN, 0.25 * contrast)   # hysteresis half-width

    if target_mean > floor_mean:                  # targets are BRIGHTER than floor
        T_enter = midpoint + band                 # must exceed this to declare ON-TARGET
        T_exit  = midpoint - band                 # must drop below this to declare OFF
        polarity = BRIGHT
    else:                                         # targets are DARKER than floor
        T_enter = midpoint - band
        T_exit  = midpoint + band
        polarity = DARK

    return T_enter, T_exit, polarity
```

**Why two thresholds derived from a *midpoint plus a band* rather than fixed numbers:** it makes the whole
system floor-agnostic. Move to a different classroom, rerun calibration, thresholds follow.

**Deciding polarity automatically** matters if you don't know the note colour in advance. A dark grey
carpet with yellow notes is `BRIGHT` polarity; a white tile floor with dark blue notes is `DARK`. Let the
calibration pass decide rather than baking it in.

### 2. Hysteresis (Schmitt trigger)

Two thresholds instead of one: "a noisy signal on Schmitt trigger input near one threshold can cause only
one switch in output value, after which it would have to move beyond the other threshold in order to cause
another switch" ([Schmitt trigger](https://en.wikipedia.org/wiki/Schmitt_trigger)).

Without hysteresis, when the sensor spot straddles the note's edge the scalar hovers at the threshold and
flickers — **the direct mechanical cause of the classic double-count.** A band of ~25 % of the floor/target
contrast absorbs it.

### 3. Minimum-dwell debounce

Hysteresis kills threshold chatter but not *transients*: a crumb, a scuff, a carpet seam, a glint. Require
the state to hold for `N` consecutive samples before committing. `N` must be shorter than the shortest
legitimate dwell and longer than the longest spurious one. At 250 mm/s a 76 mm note gives ~30 samples, so
`N = 5` (50 ms) sits comfortably inside and rejects anything under 12.5 mm of travel.

```
N_dwell_samples = clamp( 0.25 * expected_samples_on_target, 3, 12 )
```

Recompute `N` if you change drive speed. A team that tunes the debounce at 200 mm/s and then speeds the
robot up to 500 mm/s to fit the time budget will start missing targets and will not know why.

### 4. Exit-edge counting, not entry-edge counting

**Count on the falling edge (target -> floor), not the rising edge.** On the entry edge you have not yet
confirmed the feature is target-sized; on the exit edge you know how long you were on it and can apply a
*minimum width* test to reject a 4 mm scuff. And if the run ends mid-target, an entry-edge counter has
already committed, whereas an exit-edge counter can be flushed deliberately with the width test applied.

### Full pseudocode

```python
# ---- state ----
STATE_OFF = 0          # over floor
STATE_MAYBE_ON = 1     # above T_enter but not yet dwelt long enough
STATE_ON = 2           # confirmed on a target
STATE_MAYBE_OFF = 3    # past T_exit but not yet dwelt long enough

state          = STATE_OFF
dwell          = 0          # consecutive samples in the candidate condition
on_samples     = 0          # samples accumulated while confirmed ON
count          = 0
entry_odom_mm  = 0.0
detections     = []         # list of (lane_index, along_track_mm, width_mm)

N_DWELL        = 5          # samples, from sizing rule above
MIN_WIDTH_MM   = 25         # reject features narrower than this
MAX_WIDTH_MM   = 200        # reject features wider than this (a whole dark stripe, a shadow)

def active(v):
    # "looks like target" per polarity
    return (v > T_enter) if polarity == BRIGHT else (v < T_enter)

def inactive(v):
    return (v < T_exit) if polarity == BRIGHT else (v > T_exit)

# ---- called every 10 ms ----
def tick(v, odom_mm, lane_index):
    global state, dwell, on_samples, count, entry_odom_mm

    if state == STATE_OFF:
        if active(v):
            state = STATE_MAYBE_ON
            dwell = 1
            entry_odom_mm = odom_mm          # provisional entry position

    elif state == STATE_MAYBE_ON:
        if active(v):
            dwell += 1
            if dwell >= N_DWELL:
                state = STATE_ON
                on_samples = dwell
        else:
            state = STATE_OFF                # transient rejected
            dwell = 0

    elif state == STATE_ON:
        on_samples += 1
        if inactive(v):
            state = STATE_MAYBE_OFF
            dwell = 1
            exit_odom_mm = odom_mm

    elif state == STATE_MAYBE_OFF:
        if inactive(v):
            dwell += 1
            if dwell >= N_DWELL:
                # ---- FALLING EDGE COMMITTED: decide whether to count ----
                width = exit_odom_mm - entry_odom_mm
                if MIN_WIDTH_MM <= width <= MAX_WIDTH_MM:
                    count += 1
                    detections.append((lane_index,
                                       (entry_odom_mm + exit_odom_mm) / 2.0,
                                       width))
                    beep()                   # audible confirmation for the demo
                else:
                    rejected.append(width)   # keep for the report - shows tuning worked
                state = STATE_OFF
                dwell = 0
                on_samples = 0
        else:
            state = STATE_ON                 # dropout inside the target - not an exit
            dwell = 0

# ---- called at end of each lane ----
def flush_lane():
    global state, dwell
    if state in (STATE_ON, STATE_MAYBE_OFF):
        # robot stopped while still over a target; count it if wide enough so far
        width = current_odom_mm() - entry_odom_mm
        if width >= MIN_WIDTH_MM:
            count += 1
    state = STATE_OFF
    dwell = 0
```

Two design points worth defending in the write-up: **`STATE_ON -> MAYBE_OFF -> ON` is not redundant** — a
dropout *inside* a target (a printed line, a fold, a shroud shadow) would otherwise split one note into two
counts, and this transition is what prevents that second flavour of double-count. And **the width test is
the cheapest high-value filter you have**, converting a binary detector into a size-discriminating one for
free from odometry you already compute. Log rejected widths as evidence the filter works rather than hides
failures.

### Detector-level failure modes and what fixes them

| Failure | Cause | Mechanism that fixes it |
|---|---|---|
| Double count, one note | Threshold chatter at the note edge | Hysteresis band |
| Double count, one note | Sensor drops out mid-note (fold, print, shadow) | `MAYBE_OFF -> ON` recovery |
| Double count, one note | Robot re-crosses same note in an adjacent lane | Lane geometry / de-dup — see [De-duplication](#de-duplication-strategy) |
| Phantom count | Crumb, seam, glint, tape edge | Minimum dwell + `MIN_WIDTH_MM` |
| Phantom count | Robot's own shadow at a lighting boundary | Shroud + `MAX_WIDTH_MM` |
| Missed note | Sensor path passed beside the note | Lane pitch (the dominant miss cause — see below) |
| Missed note | Contrast below noise floor | Calibration contrast gate; change note colour |
| Missed note | Debounce longer than dwell (robot too fast) | Recompute `N_DWELL` from speed |
| Count drifts between identical runs | Ambient light changed, or sensor height changed | Recalibrate per run; brace the mount |


---

## Coverage pattern comparison

### First: the sweep geometry that decides everything

Before comparing patterns, do this arithmetic. It is the constraint that will actually kill the mission.

A single downward color sensor senses a **spot roughly a centimetre across** (exact figure is
[Open question 1](#open-questions--measure-these-before-committing-to-a-design)). It therefore traces a
*line*, not a swath. Robot width is irrelevant — **the detection swath is the sensor spot, not the chassis.**

For a target of width `W` and lane pitch `L`, with `e` = worst-case cross-track deviation of the actual
path from the planned lane:

```
guaranteed detection  requires  L <= W - 2e
guaranteed no double  requires  L >= W + 2e
```

**These are mutually exclusive.** With `W = 76 mm` (Post-it):

| Cross-track error `e` | `L` for guaranteed detection | Lanes across a 1.2 m arena | Path length |
|---|---|---|---|
| 5 mm | 66 mm | 19 | 22 m |
| 10 mm | 56 mm | 22 | 26 m |
| 20 mm | 36 mm | 34 | 41 m |
| 30 mm | 16 mm | 75 | 90 m |

Time budget check. Large Angular Motor at max efficiency is 135 RPM; on 56 mm wheels that is
`135/60 x 175.9 = 396 mm/s` at the wheel, so a practical, controllable drive speed is **200-300 mm/s**.
At 250 mm/s plus ~1.5 s per end-of-lane turn:

| `e` | Lanes | Drive time | Turn time | **Total** |
|---|---|---|---|---|
| 5 mm | 19 | 88 s | 29 s | **117 s** |
| 10 mm | 22 | 102 s | 33 s | **135 s** |
| 20 mm | 34 | 163 s | 51 s | **214 s** — over budget |

**Conclusions you can act on immediately:**

- A **1.2 m x 1.2 m arena is feasible in under 3 minutes only if cross-track error stays under ~10 mm.**
  That is a demanding but achievable number *if* you re-square every lane. It is not achievable from open-loop
  odometry over a 2-3 minute run (see [Odometry](#odometry-and-heading)).
- **Shrink the arena** rather than coarsen the lanes. Coverage time scales as `area / L`, so halving arena
  width halves the run time, while coarsening `L` costs you detections quadratically in disappointment.
- **The single highest-value change you cannot afford is a second color sensor.** Two sensors spaced `W`
  apart double the swath and halve the lane count. Say so in the trade study.
- **[IF TARGETS DIFFER]** Larger targets (a sheet of A4, 210 mm) transform this: `L` could be 170 mm, 8 lanes,
  ~45 s. If you have any influence over the mission definition, **argue for larger targets** — it is worth
  more than any algorithm on this list.

**Where does `e` come from? Mostly heading.** A residual heading error `theta` held over a lane of length
`L_lane` produces a lateral offset of `L_lane * sin(theta)`. Over a 1.2 m lane:

| Heading error held | Lateral offset at end of lane |
|---|---|
| 0.5 deg | 10 mm |
| 1 deg | 21 mm |
| 2 deg | 42 mm |
| 5 deg | 105 mm |

**Read that against the table above: `e = 10 mm` demands heading held to ~0.5 degrees across the whole
lane.** That is achievable only with an active heading-hold loop *and* a per-lane re-square — it is nowhere
near achievable open-loop. This single calculation is the strongest argument in the document for the hybrid
sweep below, and it is worth reproducing verbatim in your trade study.

### The four candidate patterns

| Pattern | Coverage guarantee | Sensitivity to odometry error | Self-correcting? | Verdict here |
|---|---|---|---|---|
| **Boustrophedon (lawnmower)** | Provable/complete under exact motion | Cross-track error directly becomes coverage gaps; error is bounded per-lane if you re-square at each end | Yes, if each lane ends at a wall | **Recommended** |
| **Spiral (inward/outward)** | Complete for a convex region under exact motion | Every lap compounds the previous lap's radius error; no natural reference to reset against mid-pattern | No | Reject |
| **Random walk / random bounce** | Probabilistic only; needs far longer for high coverage | Immune to drift (it never claims to know where it is) | N/A | Reject for a counting mission |
| **Wall following** | Covers only the perimeter band | Excellent — the wall *is* the reference | Yes | **Use as a primitive, not as the pattern** |

Why boustrophedon wins for *this* robot, specifically:

- **Every lane ends at a boundary** — a free, absolute, per-lane re-localization opportunity, exactly the
  "re-square every ~60 cm" discipline the odometry evidence demands. No other pattern has this built in.
- **Error does not compound along the sweep direction.** Heading is re-zeroed against the wall each lane, so
  the error carried into lane `n+1` is the squaring error, not the accumulated error of lanes `1..n`. This is
  why boustrophedon beats spiral by a wide margin on a robot with no global positioning.
- **Lane index is a discrete, exactly-known integer** that increments once per turn. You never trust a
  continuous `y` estimate, and de-duplication then needs only *adjacent-lane* comparisons.
- **The failure mode is legible** — visible stripes of missed targets, diagnosable and reportable. A drifting
  spiral produces an unintelligible mess.

**Spiral loses** because it has no boundary contact except at the very start or very end, so there is
nowhere to re-square; radius error accumulates lap over lap with no observation to correct it. Good for
robots with SLAM, bad for dead reckoning.

**Random walk loses** because the mission is to *count*, not to clean. No lane structure means no cheap
de-duplication test, and revisits are frequent by construction — every revisit is a potential double-count
that only global position could resolve. See the coverage-time numbers below.

### The recommended hybrid

```
1. START: gyro health gate; reset yaw once, stationary.
2. LOCALIZE: drive to a corner. Square against wall A (timed push, then back off 20 mm).
   Turn 90 deg (gyro, slow). Square against wall B. This defines the arena frame.
3. MEASURE: drive one full lane, recording length; this calibrates arena depth in encoder degrees.
   Optionally sweep the distance sensor to estimate arena width.
4. SWEEP: for lane in 0..N-1:
       a. Heading-hold straight down the lane at target heading, running the edge-counting tick().
       b. Terminate the lane on (distance_sensor < 120 mm) OR force_sensor.pressed()
          OR encoder distance > lane_length_max (timeout guard).
       c. flush_lane(); record lane index.
       d. Square against the end wall  -> re-zero heading, re-zero along-track origin.
       e. Turn 90 deg, advance exactly L, turn 90 deg (both gyro-controlled, slow).
       f. target_heading = target_heading + 180 (unwrapped).
5. REPORT: display count on the light matrix. Do NOT animate during the sweep.
```

Step 4d is what makes the whole thing work. **Without a per-lane re-square, the sweep degenerates into
open-loop dead reckoning and the error budget says you will fan out and miss whole stripes.**

Practical note on step 4e: **the lane advance `L` is the one distance you cannot re-square against
anything.** It is pure odometry, and its error is your `e`. If the arena has a side wall parallel to the
sweep direction, consider using a wall-riding wheel (the Seshans note "riding wheels can help your robot
drive along walls", [Wheels.pdf](https://flltutorials.com/translations/en-us/RobotGame/Wheels.pdf)) or
counting lanes against a physically indexed feature instead.


### What the coverage-path-planning literature actually says

The standard reference is Galceran & Carreras, *A survey on coverage path planning for robotics*, Robotics
and Autonomous Systems 61 (2013)
([open-access PDF](https://dugi-doc.udg.edu/bitstream/handle/10256/9088/Survey-coverage-path-planning.pdf)),
which restates the taxonomy from Choset's 2001 survey
([CMU RI page](https://publications.ri.cmu.edu/coverage-for-robotics-a-survey-of-recent-results/)).

**The boustrophedon guarantee, precisely stated.** Exact cellular decomposition splits free space into
non-overlapping cells whose union exactly fills it; each cell is swept with a zigzag ("seed-spreader")
motion, and **"complete coverage is guaranteed by finding an exhaustive walk through the adjacency graph"**
(Galceran §4). Choset & Pignon's *boustrophedon* decomposition merges trapezoids a single lawnmower pass can
cross, which "effectively reduces the number of cells" and "generates shorter complete coverage paths".

Note what that guarantee is conditional on: (i) a correct decomposition, (ii) every cell visited, and
(iii) **the within-cell zigzag actually covering the cell**. Condition (iii) is where odometry kills you,
and the survey says so directly (§10, Coverage under Uncertainty):

> "In many scenarios, the lack of a global localization system such as GPS makes the robot accumulate drift,
> and hence a growing uncertainty about its pose. Although the topological representations such as the
> adjacency graph are tolerant to localization error, **the performance of coverage algorithms, even if
> using such representations, is still affected**. This is because the amount of coverage within a cell
> depends on the direction of the zigzag pattern."

**The literature's own answer to "how do I sweep without localization" is: drive the boundaries.** Acar &
Choset (2002b), per Galceran §10, plan paths "by relying on the boundaries of each cell, **hence minimizing
the dead-reckoning error**." That is exactly the per-lane re-squaring recommended above, and it is the
single strongest justification for the hybrid design.

**Guaranteed coverage under bounded error exists, and it costs you distance.** Bretl & Hutchinson (ICRA
2013), again via Galceran §10: "Assuming a worst-case model of uncertainty they are able to guarantee
complete coverage. **This guarantee comes at the cost of a longer path, since paths generated by their
algorithm include retracing.**" (Paper itself is IEEE-paywalled — UNVERIFIED beyond this quotation.)

**Spiral-STC is theoretically the most efficient and the worst fit for you.** Gabriely & Rimon's Spanning
Tree Coverage "never visits any small cell twice and thus minimizes the coverage time" (Galceran §6.2), but
it works at 2x-robot-width "mega cell" granularity and therefore **leaves every partially-occupied cell —
i.e. the entire perimeter ring — uncovered**; the Backtracking Spiral Algorithm patches this "by a
wall-following procedure". More decisively, STC needs a globally consistent incremental grid map, i.e. pose
accurate to under half a cell for the whole run. **You cannot maintain that. Skip it.** (Primary Gabriely &
Rimon texts are paywalled; the STC `(n+m)*D` path-length bound and worst-case-optimality claim are
UNVERIFIED here.)

**Random coverage: the numbers.** iRobot's own patent US2003/0025472A1 states that to have high confidence
of covering **98 % of an obstacle-free room, a random-motion robot must run roughly five times as long as a
deterministic one** ([Google Patents](https://patents.google.com/patent/US20030025472A1/en)) — partisan
prose with no stated method, so treat it as an order-of-magnitude anchor. A 2024 KTH simulation study
(5000 runs per stochastic scenario) is blunter: **"In the same amount of moves BA* and CFS could completely
cover the area, random walk only managed around a 50%-60% coverage"**, with random walk's moves-to-coverage
running about an order of magnitude higher at 100 %
([Hellgren & Hovhannisyan, PDF](https://www.diva-portal.org/smash/get/diva2:1886194/FULLTEXT01.pdf)).
Theory agrees: cover time of a simple random walk on the `n x n` lattice torus is asymptotically
`(2 n log n)^2 / pi` ([Dembo et al.](https://arxiv.org/abs/math/0107191)) — **superlinear in area, so random
gets relatively worse as the arena grows.** For a 1-3 minute run this rules random out on time alone.

The one thing random has going for it, per the KTH study, is that it **needs fewer turns**, and the authors
flag why that matters: "Turns... introduce more possibility for inaccuracy as the robot is unlikely to turn
the exact amount of degrees indicated. Small inaccuracies in each turn can add up to a major problem if many
turns are conducted." Your boustrophedon does two point turns per lane — **budget for that.**

**Wall following is a localization primitive, not a coverage pattern.** Doty & Harrison's classic 1993 result
found the best strategy was a random walk **plus a 0.05 probability of wall-following after each obstacle
encounter**, reaching "about 85% of the floor space... after 20 minutes"
([AAAI 1993 abstract](https://aaai.org/papers/0008-fs93-03-008-sweep-strategies-for-a-sensory-driven-behavior-based-vacuum-cleaning-agent/)).
Perimeters are the last places a random walk reaches and the first places a lawnmower misses.

**Calibration is the highest-leverage single action available to you.** Borenstein & Feng's UMBmark
([PDF](https://johnloomis.org/ece445/topics/odometry/borenstein/paper60.pdf)) establishes that "on most
smooth indoor surfaces **systematic errors contribute much more to odometry errors than non-systematic
errors**", and that the two dominant systematic sources in a differential drive are **unequal wheel
diameters** and **uncertainty in the effective wheelbase**. Their headline result: on a 4x4 m bidirectional
square path (16 m of travel), a LabMate went from `E_max,syst` of **310 mm and 423 mm uncalibrated to 26 mm
and 20 mm calibrated** — roughly 2 % of path length down to 0.15 %, **a >10x improvement from an afternoon's
work.** Two procedural points you should copy: run the square path **both clockwise and counter-clockwise**
(a uni-directional test "might indicate a very small odometry error" while concealing two mutually
compensating errors), and calibrate the wheelbase and wheel-diameter ratio separately.

**Set expectations at ~85 %, not ~99 %.** Wong & MacDonald's topological coverage algorithm scored
**99.8 % / 99.2 % coverage in simulation but ~85 % on a real Khepera**, with path efficiency 1.06-1.11 in sim
vs 1.20 on hardware — and **every missed cell was "along borders of subregions"**
([PDF, mislabeled on the host as Spiral-STC](https://static.aminer.org/pdf/PDF/000/352/119/spiral_stc_an_on_line_coverage_algorithm_of_grid_environments.pdf)).
That sim-to-real gap on a comparable-scale robot with comparable sensing is the most honest prior you have.
**Instrument your seams.**

**One quantified warning about the wall-reset itself**, from an FLL practitioner:
"Back the bot into a wall at speed. Then drive forward by a small distance. **The robot will drive about
20 cm**" ([Hendricks FLL notes](https://lhendricks.org/fll2025/fll.html)) — hitting a wall hard corrupts the
*next* move. **Approach walls slowly.** Same source: "Driving short distances with acceleration does not
work. The bot drives too far" — which is exactly your inter-lane advance move. Use low acceleration and
verify the advance empirically.


---

## Odometry and heading

### What LEGO actually publishes vs what it doesn't

**Motors: fully specified.** 360 counts/rev (1 count = 1 degree at the output axle), accuracy **<= +/- 3
degrees including gearbox slack**, 100 Hz update. On 56 mm wheels, +/- 3 degrees is ~1.5 mm per wheel per
reading. That is your *floor*, and it is not the problem.

**Hub IMU: essentially unspecified.** The hub spec sheet lists the modes it can report and **no resolution,
no update rate, and no drift figure**. Contrast that with the motor sheets, which publish all three. Any
"official SPIKE gyro drift spec" you are shown does not exist — treat it as UNVERIFIED.

Silicon-level bounds, if you want a physical argument in the report: teardown work identifies the IMU as an
**ST LSM6DS3TR** ([gpdaniels/spike-prime](https://github.com/gpdaniels/spike-prime/blob/master/README.md)).
The LSM6DS3 datasheet gives typical zero-rate level **+/- 10 dps** (**+/- 600 deg/min** uncompensated — hence
the mandatory rest-bias estimate) and zero-rate drift vs temperature **+/- 0.05 dps/degC**, so a 10 degC
self-heating rise leaves ~0.5 dps ~ **30 deg/min** residual
([datasheet PDF](https://files.seeedstudio.com/wiki/Grove-6-Axis_AccelerometerAndGyroscope/res/LSM6DS3TR.pdf);
**caveat: that mirror is the LSM6DS3, not the TR-C variant**). A 2-3 min run sits inside the warm-up window.

### Wheel constants

SPIKE Prime core set ships four **56 x 14** tyres; the expansion set adds four **88 x 14**
([Seshan "Wheels" PDF](https://flltutorials.com/translations/en-us/RobotGame/Wheels.pdf)). Geometric
circumferences: 56 mm -> **175.9 mm/rev** (**20.45 motor-degrees per cm**), 88 mm -> **276.5 mm/rev**.

**Do not use the geometric number.** Prime Lessons calibrate empirically — roll until the encoder reads
exactly 360 degrees, measure with a ruler, use *that*
([ConfiguringRobotMovement.pdf](https://primelessons.org/en/PyProgrammingLessons/ConfiguringRobotMovement.pdf)).
Their worked example uses **17.5 cm**, not 17.6: the tyre compresses and the effective rolling radius is
smaller than the moulded diameter. **On carpet it sinks further, so calibrate separately per surface.**
Note also that SPIKE App 3's `motor_pair` has **no distance-unit API** — you convert cm to degrees yourself,
every time.

### Measured turn accuracy, stock firmware

The most actionable number found anywhere: on Prime Lessons' Drive Base 1, a gyro-controlled 90-degree turn
**at velocity 500 actually turns 98 degrees (8 degrees of overshoot); at velocity 200 the error drops to 2
degrees.** They attribute it to sensor read latency plus momentum during braking, and note "we did not
notice any significant difference using `move` vs `move_tank` — **adjusting the speed made the biggest
difference**" ([SP3AccurateTurningPython.pdf](https://primelessons.org/en/PyProgrammingLessons/SP3AccurateTurningPython.pdf)).
**A 4x error reduction for free, just by slowing turns down. Do this.**

An independent 10-trial cross-language benchmark (surface not stated — treat magnitudes cautiously) gives
mean error / spread on a 90-degree turn: **SPIKE App 3 Python 9.6 / 1.2 deg; Word Blocks 17.1 / 0.9 deg;
Pybricks 8.6 / 1.0 deg** ([dev.to benchmark](https://dev.to/_ff41734170f7cc70ac79/comparing-lego-spike-prime-programming-which-is-best-for-robotics-competitions-3-20h1)).
**Use Python, not Word Blocks** (2x better on identical firmware); and the low spread means the error is
systematic, therefore correctable.

**Per-hub scale error is real and consistent.** The Seshans report that turning a hub 360 degrees gives a
reading that is off by a fixed, hub-specific amount: "Hub 1 will consistently be 7 degrees off and Hub 2
will consistently be 4 degrees off." They also report the striking result that **"updating the light matrix
at the same time will increase the error by about 25 degrees per 360 degree turn"**
([SPIKEPrimevsEV3.pdf](https://primelessons.org/en/ProgrammingLessons/SPIKEPrimevsEV3.pdf)). **Do not
animate the 5x5 display during gyro-controlled motion.** Measure your hub's per-360 error once and apply it
as a scale factor.

### The gyro drift / stuck-at-zero pathology

Prime Lessons document a real stock-firmware failure affecting both SPIKE 2 and 3: after boot the yaw either
drifts continuously or **sticks at 0 forever**. Their diagnosis: "the gyro waits for the robot to be still
before reading gyro values. However, since drift has already been introduced at this point by shaking the
robot, the hub thinks that it is moving continuously even when the robot is still." Their fix is blunt:
**check for drift before every run; if it is drifting, reboot the hub**
([SP3GyroDrift.pdf](https://primelessons.org/en/ProgrammingLessons/SP3GyroDrift.pdf)).

Make this a mandatory pre-run gate:

```python
from hub import motion_sensor, light_matrix
import runloop

async def gyro_health_gate():
    motion_sensor.reset_yaw(0)
    await runloop.until(motion_sensor.stable)   # hub must be flat and still
    await runloop.sleep_ms(1000)                # let the bias estimate settle
    wz = motion_sensor.angular_velocity(False)[2]
    if wz != 0:
        light_matrix.write("X")                 # REBOOT THE HUB - do not run
        raise SystemExit
```

### Heading hold on the straight legs

Canonical FLL proportional loop ([GyroMoveStraight.pdf](https://primelessons.org/en/PyProgrammingLessons/GyroMoveStraight.pdf)),
with their published starting gain **Kp = 2** at a tank speed of ~60:

```
error      = yaw_deg - target_heading_deg
correction = -Kp * error
move_tank(base + correction, base - correction)
```

1. **It corrects heading, not cross-track offset.** After a bump the robot ends up *parallel to* but
   *laterally offset from* the lane — and lateral offset is exactly what ruins lane pitch and causes misses.
   **Add a cross-track term** (integrate `sin(heading_error) * ds` and drive it to zero), or accept the
   offset and re-square against the wall every lane.
2. **Practical loop rate is ~30-50 Hz** in MicroPython on this hub (measured 20-30 ms cycle,
   [FLL Pigeons gyro PID](https://fll-pigeons.github.io/gamechangers/gyro_pid.html)) — below the sensors'
   100 Hz. Size gains for that rate. Same source: worked PID values Kp 1.8 / Ki 0.184 / Kd 4.4, and the
   anti-windup rule `if error == 0: integral = 0`.
3. **Stock SPIKE 3 has no gyro-assisted motion primitive** — `motor_pair.move_for_degrees` is pure encoder,
   so this loop is yours to write. (Pybricks' `DriveBase.use_gyro(True)` does it, but needs non-stock
   firmware — out of scope.)

### Yaw handling rules

- `motion_sensor.tilt_angles()[0]` is **decidegrees** and is **opposite in sign** to the app's yaw. Convert
  with `yaw_deg = tilt_angles()[0] * -0.1`
  ([SP3GyroTurningPython.pdf](https://primelessons.org/en/PyProgrammingLessons/SP3GyroTurningPython.pdf)).
- **Reset yaw exactly once, at run start, while stationary**, gated on
  `await runloop.until(motion_sensor.stable)`. Resetting while rotating zeroes the bias against a rotating
  frame and injects a permanent phantom rotation.
- **Do not reset between turns.** Keep one global heading frame for the whole run and work with wrapped
  deltas ([Robot Wonders gyro turn](https://robotwonders.com/spike-prime-gyro-turn/)). Unwrap manually:
  `if d < -179: d += 360; if d > 180: d -= 360`. Their example: 170 -> -170 is a 20-degree rotation, but
  naive subtraction gives -340.
- **Always compare with `<` / `>`, never `==`** — the sensor may never be sampled at the exact value and
  your loop will hang (Prime Lessons, repeatedly).
- Steering convention: **+/-50 = pivot turn (one wheel), +/-100 = spin turn (both wheels opposite)**. Spin
  turns are faster but slightly less accurate; pivot turns need more room.

### Carpet vs tile — the finding that should drive your arena choice

**No FLL-community measurement of carpet dead-reckoning exists**, because FLL runs exclusively on a vinyl
mat. The best hard source is iRobot's carpet-drift patent, written specifically about floor-cleaning robots
([US9969089B2](https://patents.google.com/patent/US9969089B2/en)):

Carpet fibres are bent in a manufacturing direction (**grain / nap**): driving **with** the grain the robot
**travels farther than the encoders say**, **against** it **less**. The patent models carpet drift as a
**vector with magnitude and direction** whose magnitude "may be proportional or somewhat related to the
distance traveled". So it is a **directional, distance-proportional, systematic bias — not zero-mean
noise.** It does not average out over a sweep; it compounds. Hard floors lack this bias.

**Consequence for a boustrophedon sweep:** alternating lanes run with and against the grain, so they get
*different effective lengths for the same encoder count* and will not line up. On carpet, trust the gyro for
heading and distrust the encoders for distance. (Slip is a live issue on smooth floors too, by a different
mechanism — the Seshans note SPIKE tyres "tend to slip on the challenge mat" and need frequent cleaning,
[Wheels.pdf](https://flltutorials.com/translations/en-us/RobotGame/Wheels.pdf).)

### How far can you go before you must re-localize?

The clearest community rule of thumb ([RoboCatz navigation](https://robocatz.com/navigation.htm)):

| Distance | Verdict |
|---|---|
| <= 10 in (~25 cm) | Rotation sensor alone is fine |
| 10-24 in (25-60 cm) | Marginal; results vary run to run |
| > 2 ft (60 cm) | Unreliable without an intermediate position check |

Their error-propagation example: "A 5 degree error in turning multiplied by 30 inches travelled would result
in an error of almost 3 inches" (5 deg over 30 in -> 2.6 in lateral — the arithmetic checks out). And their
reliability argument: 95 % turn x 85 % straight x 90 % turn = **73 % mission success**. Chained open-loop
moves multiply failure.

**Design rule for your sweeper: never travel more than ~60 cm without touching an absolute reference.**

### Re-squaring techniques (all workable on stock firmware)

- **Two-sensor wall square.** Drive at the wall; when one bumper sensor hits, stop that motor and let the
  other keep driving until its sensor hits. Both touching => perpendicular. Zeroes heading *and* one
  position axis in one move ([RoboCatz, using the wall](https://robocatz.com/using-the-wall.htm)).
  **You have only one force sensor**, so you get the stall/time variants instead — or you build a
  two-microswitch equivalent out of... nothing you own. Flag this as a hardware-limitation finding.
- **Stall-into-wall.** Same source, with a critical detail: "set the power on the motor just low enough to
  move the robot" — too much power and the wheels slip instead of stalling, corrupting the encoder count
  *and* defeating detection. Harder on carpet, which grips enough that the robot skids or climbs rather than
  stalling cleanly. Note SPIKE 3 has built-in stall detection on **single-motor** functions (they return
  early when stalled) but "as of version 3.4, SP3 does not allow stall detection to be changed or queried"
  ([SP3MovingObjectsStallPython.pdf](https://primelessons.org/en/PyProgrammingLessons/SP3MovingObjectsStallPython.pdf)) —
  so you infer a stall by comparing commanded vs actual `motor.relative_position`.
- **Time-based wall push.** FLL teams use a *timed* drive into a wall rather than a degrees-based one
  because a degrees command **never completes if the motor cannot turn**, hanging the program. A timed move
  always returns. Simple, robust, and available to you.
- **Line squaring** needs two color sensors, spaced apart — "Your color sensors should NOT be placed right
  next to each other", because a short baseline amplifies angular error
  ([SP3SquaringonLine.pdf](https://primelessons.org/en/ProgrammingLessons/SP3SquaringonLine.pdf)).
  **You have one color sensor, so line squaring is unavailable.** Another argument for a physical border.
- **Wall dancing** ([Robot Wonders](https://robotwonders.com/wall-dancing/)): forward, turn a small amount
  (< 25 deg), reverse into the wall to re-square, repeat — walking along a wall while re-zeroing on every
  backward move so error never accumulates. Directly applicable to a perimeter sweep. No quantified accuracy
  published.

### Realistic error budget for a 2-3 minute run

| Source | Magnitude | Character |
|---|---|---|
| Encoder + backlash | +/- 3 deg per reading (~1.5 mm) | Random, averages out |
| Gyro turn overshoot @ velocity 200 | ~2 deg per turn | Systematic; correctable |
| Gyro scale error | 4-7 deg per 360 deg, hub-specific | Systematic; correctable by scale factor |
| Light matrix contention | up to ~25 deg per 360 deg | Avoidable — just don't do it |
| Tyre slip on turn start/stop | few mm per turn | Semi-random |
| Carpet grain drift | distance-proportional, direction-dependent | **Systematic, compounds, not correctable by gyro** |
| Gyro thermal drift after warm-up | order 30 deg/min residual (silicon-level estimate, UNVERIFIED for this firmware) | Slow ramp |

**Expect tens of cm of accumulated position error over a full run on tile with no re-localization, and
substantially worse on carpet.** This is the entire reason the de-duplication strategy below is built on
*local* lane-relative geometry rather than a global map.


---

## De-duplication strategy

The question: how do you avoid counting the same note twice when it may be seen on two adjacent passes?

### Approach A — Structural: lane-based single-visit (RECOMMENDED)

**Make double-counting geometrically impossible instead of detecting it after the fact.**

The sensor traces a set of parallel lines. **A target can only be counted twice if two different sensor
lines cross it** — and as shown in the coverage section, guaranteed detection and guaranteed no-double-
detection are mutually exclusive conditions on `L`. **That tension is the central design decision of the
mission and belongs explicitly in your trade study.**

Resolutions, in order of preference:

1. **Set `L` just under the guaranteed-detection bound and de-duplicate the small overlap by along-track
   position.** Two crossings of the *same* note occur in *adjacent* lanes at *nearly the same along-track
   distance* — a very cheap, very reliable test:

   ```
   for each new detection (lane, s, width):
       for each prior detection (lane', s', width'):
           if abs(lane - lane') == 1 and abs(s - s') < DEDUP_RADIUS:
               mark as duplicate; do not increment count
   ```
   `DEDUP_RADIUS` ~ `W` (76 mm) works because two crossings of one note are at most `W` apart along-track,
   whereas two *distinct* notes cannot overlap and so are at least `W` apart. **Accuracy needed: only
   along-track odometry accuracy within a single lane pair, i.e. a few seconds of driving — comfortably
   within encoder capability even on carpet.** This is the key insight: you never need *global* position,
   only *locally consistent* position between two adjacent lanes.
2. **Set `L = W` exactly and accept the resulting ~50 % detection probability for badly placed notes.**
   Simpler, and defensible if the mission metric is "count as many as possible" rather than "count all".
3. **Widen the effective swath.** With only one color sensor you cannot. **[IF A SECOND COLOR SENSOR WERE
   AVAILABLE]** two sensors spaced `W` apart would double the swath and halve the lane count — this is the
   single highest-value hardware change and is worth flagging in the report as a recommendation, even
   though budget forbids it.

### Approach B — Positional: dead-reckoned tagging with a de-dup radius

Store every detection as an `(x, y)` in a global arena frame and reject any new detection within `R` of an
existing one.

**Accuracy required:** `R` must exceed the *relative* position error between the two sightings but stay
below the minimum spacing between distinct targets. If notes can be 150 mm apart then `R < 150 mm`, so
accumulated relative error between adjacent passes must be well under 150 mm. Across one lane-turn-lane
cycle (tens of seconds) that is achievable; **across a full 2-3 minute run it is not.**

**Verdict:** B is strictly worse than A for the same information, because it invites comparisons between
detections minutes apart in odometry time. Use A. If you implement B, restrict the comparison window to the
last two lanes — at which point you have reinvented A.

**Approach C, physical marking** (mark or remove what you find) trivially solves de-duplication and is
**not available**: no spare actuator, no consumable budget. Worth one line in the trade study.

---

## Sensor role assignment

| Sensor | Primary role | Secondary role | Do NOT use it for |
|---|---|---|---|
| Color Sensor 45605 (down, centreline, 16 mm) | **Target detection** via `reflection()` | Boundary tape-line detection, *if* boundary tape reflectance is well separated from target reflectance | Target *classification* by colour on pastel/printed targets |
| Distance Sensor 45604 (forward, ~40-80 mm above floor) | **Arena boundary / wall detection**, end-of-lane trigger | Obstacle avoidance, coarse arena-width measurement at run start | Anything closer than 50 mm; anything soft or steeply angled |
| Force Sensor 45606 (front bumper) | **Contact fallback** when the distance sensor fails to see the boundary | Run start/stop button; stall/collision detection | Continuous distance measurement |
| Hub IMU (yaw) | **Heading hold and turn control** | Detecting that the robot has been picked up / tipped | Absolute position |
| Motor encoders | **Along-track distance, lane length, width test** | Slip detection (compare commanded vs achieved) | Absolute heading |

### Distance sensor: exactly where it fails

The physics is generic to ultrasound and the failure modes are all relevant to a classroom arena:

- **50 mm blind zone, and it is inherent:** "Immediately after transmitting an ultrasonic pulse, the
  transducer continues vibrating for a short period of time before it can reliably receive returning echoes"
  ([Same Sky](https://www.sameskydevices.com/blog/the-basics-of-ultrasonic-sensors)). **Trigger your turn at
  100-150 mm, not at 50 mm**, and let the force sensor catch anything closer.
- **Soft, porous surfaces absorb the pulse** — cardboard, cloth, foam, carpet. Industrial guidance lists
  "sound-absorbing materials, such as cotton and fine powder" as problem targets
  ([Azbil ultrasonic guide, PDF](http://us.azbil.com/uploadedSpecs/GUIAGFUSONICTEC-e3RD.pdf)). **Test your
  actual arena border; do not assume it echoes.**
- **Tilted flat surfaces are the worst case.** Same guide, on flat objects: "More waves are reflected, but
  if the target is tilted there is a greater effect on measurement." The +/-35 deg entrance angle in the
  spec is a *cone of emission*, not a promise of detection against a wall 35 deg oblique.
- **`distance()` returns -1, not an exception.** Treat -1 as "no boundary in range", never as 0.
- **Mounting height.** FLL convention is low ([ORTOP](https://ortop.org/wiki/index.php/FIRST_LEGO_League_Challenge_Sensors)),
  but a low sensor on carpet echoes off the pile. At +/-35 deg a sensor `h` above the floor first illuminates
  the floor about `1.43 h` ahead, so keeping the floor out of the beam for 200 mm needs `h >= 140 mm`.
  **Practical compromise: 60-80 mm, tilted up 5-10 degrees.**

### Force sensor: yes, it has a real role

It is worth one of your six ports, for three reasons:

1. **Ground-truth boundary contact.** A physical bumper cannot be fooled by a soft or angled border. Use it
   as the *authoritative* end-of-lane signal wherever the distance sensor proves unreliable in testing.
2. **Wall squaring.** Driving gently into a flat wall until contact gives a repeatable physical reference to
   re-zero heading against. Caution: only **8 mm of plunger travel**, triggering at **1 mm +/- 0.5 mm** and
   **0.5-1.0 N** — the bumper must be a light, free-sliding assembly, not a rigid beam, or you will trigger
   nothing and stall the drive instead.
3. **Free start button.** `force_sensor.pressed()` beats the hub button and can be placed where the operator
   can reach it.

**[IF TARGETS DIFFER]** If targets are 3D objects tall enough to bump, the force sensor could become the
*primary* target detector (a bump counter) with the color sensor demoted to boundary tape detection. That
is a completely different architecture and the trade study should say so.

---

## Failure modes to expect (run level)

Ranked by how likely they are to bite you in a demo, based on the constraints above.

1. **Lane pitch too coarse -> systematic misses.** Overwhelmingly the most likely cause of a low count.
   Symptom: count is consistently low and roughly proportional to `W / L`. Diagnose by placing notes on a
   known grid and comparing found vs placed by position.
2. **Insufficient floor/target contrast on carpet.** Symptom: erratic counts, high rejected-width log.
   Diagnose during calibration by checking `contrast > 6 * floor_sd` before the run even starts. Mitigate by
   choosing note colours at the opposite end of the reflectance scale from the floor — measure, don't guess.
3. **Heading drift turning a rectangular sweep into a fan.** Symptom: lanes fan out or converge; coverage
   gaps appear at one end of the arena. Mitigate with per-lane re-squaring.
4. **Turn-radius error accumulating cross-track.** Each end-of-lane turn is two 90-degree turns plus a short
   translation; errors in the translation directly become lane-pitch errors, which directly become misses.
   Consider using the wall as the pitch reference rather than odometry.
5. **Wheel slip on carpet during acceleration.** Symptom: along-track distances short by a few percent,
   consistently. Mitigate with gentle `acceleration=` values in `motor_pair.move_for_degrees` and by
   calibrating the degrees-to-mm constant *on the actual floor*, not on a table.
6. **The robot disturbs the targets.** Sticky notes are light. A robot at 400 mm/s pushes air; a low shroud
   or a low distance sensor may catch a note edge and drag it. Symptom: a note is counted, then found in a
   different place. Mitigate: keep everything above ~10 mm ground clearance except the sensor shroud, and
   press the notes down firmly before the run.
7. **Distance sensor returns -1 at the boundary** because the border is soft or angled -> robot never turns.
   Mitigate: force-sensor bumper as the authoritative fallback, plus a hard "max lane length" timeout.
8. **Ambient light change between calibration and run.** Symptom: works in rehearsal, fails in the demo room.
   Mitigate: recalibrate in the demo room, immediately before the run.
9. **Battery sag over a 3-minute run** changing effective speed and therefore dwell timing. Mitigate: base
   the debounce on *encoder distance*, not on sample count, if you can — `MIN_WIDTH_MM` already does this,
   so prefer the width test over `N_DWELL` as your primary filter. **UNVERIFIED:** LEGO publishes no
   speed-vs-battery-state curve for SPIKE motors.
10. **Gyro reading stuck at 0 or drifting from boot.** A documented SPIKE-specific pathology — see the
    odometry section. Mitigate with a pre-run gyro health check.

---

## Open questions — measure these before committing to a design

These are the things no source answers and that only your own bench testing can settle. Each is written as
a small experiment; together they are a good "verification" section for a SYS 301 deliverable.

| # | Question | Experiment | Why it matters |
|---|---|---|---|
| 1 | What is the color sensor's actual **spot diameter** at 16 mm? | Slide the sensor slowly across a sharp black/white boundary at 1 mm steps, log `reflection()`. The transition width is the spot diameter. | Sets the minimum feature the detector can resolve and the width of the hysteresis-flicker zone. |
| 2 | What are `floor_mean` and `floor_sd` on the **actual demo floor**, tile vs carpet? | Run `CALIBRATE_FLOOR()` on both, 1000 samples each. | Determines whether the mission is feasible at all on carpet. |
| 3 | What does each **candidate note colour** read on that floor? | Static reading, 100 samples per colour, at 16 mm. | Picks the note colour. Do this before buying/choosing notes. |
| 4 | Does `rgbi()[3]` actually give better discrimination than `reflection()`? | Log both simultaneously over a floor/note boundary; compare contrast-to-noise ratio. | Decides your scalar. |
| 5 | Does `rgbi()` sample at 100 Hz like `reflection()`? | Tight loop, timestamp 1000 reads. | If it is slower, the dwell arithmetic changes. |
| 6 | Is `color_sensor` ambient light available on your installed App 3 build? | `dir(color_sensor)` on the hub. | Determines whether ambient compensation is even an option. |
| 7 | What is your hub's **actual yaw drift**, stationary, over 180 s? | `reset_yaw(0)`, leave it still, log yaw every second for 3 minutes, repeat 5x. | Sets how often you must re-square. |
| 8 | What is the **degrees-to-mm** constant on carpet vs tile? | Drive a commanded 1000 mm, measure actual, 10 runs each surface. | Your single most important odometry constant; it is surface-dependent. |
| 9 | What is the **repeatability of a 90-degree gyro turn** on each surface? | 10 turns, measure final heading error. | Sets your lane-pitch error budget. |
| 10 | Does the arena border echo? | Point the distance sensor at it, perpendicular and at 20/30 degrees, from 100/300/1000 mm. Log -1 rate. | Decides whether the force-sensor bumper is a fallback or the primary. |
| 11 | Does the robot **move the notes**? | Run a sweep over 10 placed notes, photograph before and after. | If yes, the whole mission needs a redesign. |
| 12 | **Is the mission actually sticky notes?** | Ask the instructor. | Everything marked **[IF TARGETS DIFFER]** in this document hinges on it. |

---

## Sources

Every URL below was fetched during this research pass. Claims drawn from sources that could **not** be
fetched are marked UNVERIFIED in the text and are listed separately at the end.

**Official LEGO Education specifications (primary sources)**

- Color Sensor 45605 tech specs (PDF) — https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt62a78c227edef070/5f8801b9a302dc0d859a732b/techspecs_techniccolorsensor.pdf?locale=en-us
- Distance Sensor 45604 tech specs (PDF) — https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt64c2b9534cf10f68/5f8801b8bc43790f5c4389ea/techspecs_technicdistancesensor.pdf?locale=en-us
- Force Sensor 45606 tech specs (PDF) — https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt23df304b05e587b2/5f8801ba721f8178f2e5e626/techspecs_technicforcesensor.pdf?locale=en-us
- Technic Large Hub 45601 tech specs (PDF) — https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltf512a371e82f6420/5f8801baf4f4cf0fa39d2feb/techspecs_techniclargehub.pdf?locale=en-us
- Large Angular Motor 45602 tech specs (PDF) — https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltb9abb42596a7f1b3/5f8801b5f4c5ce0e93db1587/le_spike-prime_tech-fact-sheet_45602_1hy19.pdf?locale=en-us
- Medium Angular Motor tech specs (PDF) — https://le-www-live-s.legocdn.com/sc/media/files/support/spike-prime/techspecs_technicmediumangularmotor-19684ffc443792280359ef217512a1d1.pdf
- SPIKE Prime product info / spec index — https://education.lego.com/en-us/teacher-resources/lego-education-spike-prime/support-technical-info/lego-education-spike-prime-support-technical-info-product-info/
- Color Sensor 45605 product page — https://education.lego.com/en-us/products/lego-technic-color-sensor/45605/
- Distance Sensor 45604 product page — https://education.lego.com/en-us/products/lego-technic-distance-sensor/45604/
- Force Sensor 45606 product page — https://education.lego.com/en-us/products/lego-technic-force-sensor/45606/
- LEGO Education, "Training Camp 3: React to Lines" — https://education.lego.com/en-us/lessons/prime-competition-ready/training-camp-3-react-to-lines/
- LEGO EV3 Color Sensor user guide (PDF; EV3, cited only for mounting geometry) — https://le-www-live-s.legocdn.com/sc/media/images/resource-site/files/ev3_chromebook_userguide_us_color_sensor-169c6ea887da48723fa61f7a353b3f87.pdf

**SPIKE App 3 Python API**

- Auto-generated LEGO SPIKE Python v3 API reference — https://jvolkening.github.io/lego-spike-python-v3-docs/index.html
  (modules used: `color_sensor`, `distance_sensor`, `force_sensor`, `hub.motion_sensor`, `motor_pair`)
- Tufts CEEO SPIKE 3 Python mirror — https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE3.html
- Engineering with Bricks, SPIKE Prime sensors overview — https://www.engineeringwithbricks.com/posts/spike-prime-sensors
- Pybricks ColorSensor reference (non-stock firmware; cited for contrast) — https://docs.pybricks.com/en/stable/pupdevices/colorsensor.html
- Pybricks PrimeHub IMU reference — https://docs.pybricks.com/en/stable/hubs/primehub.html
- Pybricks DriveBase / robotics reference — https://docs.pybricks.com/en/stable/robotics.html

**FLL / SPIKE practitioner sources**

- Prime Lessons, "Introduction to Color Sensor" (SPIKE 3) — https://primelessons.org/en/ProgrammingLessons/SP3ColorSensor.pdf
- Prime Lessons, "Introduction to Color Sensor" (Python) — https://primelessons.org/en/PyProgrammingLessons/ColorSensor.pdf
- Prime Lessons, "Introduction to Distance Sensor" — https://primelessons.org/en/PyProgrammingLessons/DistanceSensor.pdf
- FLL Tutorials, "Lesson 3: Finding Lines on the Mat" — https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf
- FLL Tutorials, "Wheels" — https://flltutorials.com/translations/en-us/RobotGame/Wheels.pdf
- Prime Lessons, "Gyro Drift" — https://primelessons.org/en/ProgrammingLessons/SP3GyroDrift.pdf
- Prime Lessons, "Gyro Turning" (Python) — https://primelessons.org/en/PyProgrammingLessons/SP3GyroTurningPython.pdf
- Prime Lessons, "More Accurate Turning" (Python) — https://primelessons.org/en/PyProgrammingLessons/SP3AccurateTurningPython.pdf
- Prime Lessons, "Configuring Robot Movement" — https://primelessons.org/en/PyProgrammingLessons/ConfiguringRobotMovement.pdf
- Prime Lessons, "Gyro Move Straight" — https://primelessons.org/en/PyProgrammingLessons/GyroMoveStraight.pdf
- Prime Lessons, "Moving Objects / Stall Detection" — https://primelessons.org/en/PyProgrammingLessons/SP3MovingObjectsStallPython.pdf
- Prime Lessons, "Squaring on a Line" — https://primelessons.org/en/ProgrammingLessons/SP3SquaringonLine.pdf
- Prime Lessons, "SPIKE Prime vs EV3" — https://primelessons.org/en/ProgrammingLessons/SPIKEPrimevsEV3.pdf
- FLL Pigeons, gyro PID tutorial — https://fll-pigeons.github.io/gamechangers/gyro_pid.html
- RoboCatz, "Navigation" (dead-reckoning distance limits) — https://robocatz.com/navigation.htm
- RoboCatz, "Using the Wall" (squaring techniques) — https://robocatz.com/using-the-wall.htm
- Robot Wonders, "SPIKE Prime gyro turn" — https://robotwonders.com/spike-prime-gyro-turn/
- Robot Wonders, "Wall dancing" — https://robotwonders.com/wall-dancing/
- Sprattronics, precise turns with the yaw sensor — https://sprattronics.com/mastering-precise-turns-with-lego-spike-prime-and-the-yaw-sensor
- ORTOP wiki, FLL Challenge sensors — https://ortop.org/wiki/index.php/FIRST_LEGO_League_Challenge_Sensors
- dev.to, SPIKE Prime language benchmark, part 2 (360 deg test) — https://dev.to/_ff41734170f7cc70ac79/comparing-lego-spike-prime-programming-which-is-best-for-robotics-competitions-2-3pb1
- dev.to, SPIKE Prime language benchmark, part 3 (90 deg test) — https://dev.to/_ff41734170f7cc70ac79/comparing-lego-spike-prime-programming-which-is-best-for-robotics-competitions-3-20h1

**Coverage-path-planning literature**

- Galceran & Carreras, "A survey on coverage path planning for robotics", RAS 61 (2013), full text (PDF) — https://dugi-doc.udg.edu/bitstream/handle/10256/9088/Survey-coverage-path-planning.pdf
- Choset, "Coverage for robotics — A survey of recent results" (2001), CMU RI record — https://publications.ri.cmu.edu/coverage-for-robotics-a-survey-of-recent-results/
  (the full PDF at that host is an image-only scan with no text layer — **its interior is UNVERIFIED here**)
- Hellgren & Hovhannisyan, "Comparison of Coverage Algorithms for Robot Vacuum Cleaners in Cluttered Environments", KTH 2024 (PDF) — https://www.diva-portal.org/smash/get/diva2:1886194/FULLTEXT01.pdf
- Doty & Harrison, "Sweep Strategies for a Sensory-Driven, Behavior-Based Vacuum Cleaning Agent", AAAI 1993 (abstract) — https://aaai.org/papers/0008-fs93-03-008-sweep-strategies-for-a-sensory-driven-behavior-based-vacuum-cleaning-agent/
- Dembo, Peres, Rosen & Zeitouni, "Cover Times for Brownian Motion and Random Walks in Two Dimensions" — https://arxiv.org/abs/math/0107191
- Wong & MacDonald, "A topological coverage algorithm for mobile robots" (PDF; **the host mislabels this file as Gabriely & Rimon's Spiral-STC**) — https://static.aminer.org/pdf/PDF/000/352/119/spiral_stc_an_on_line_coverage_algorithm_of_grid_environments.pdf
- Jonnarth et al., "Learning Coverage Paths in Unknown Environments with Deep RL" — https://arxiv.org/pdf/2306.16978
- iRobot, US2003/0025472A1, "Method and system for multi-mode coverage for an autonomous robot" — https://patents.google.com/patent/US20030025472A1/en
- Hendricks, FLL navigation notes — https://lhendricks.org/fll2025/fll.html

**Hardware / physics references**

- gpdaniels, SPIKE Prime hardware teardown (IMU and MCU identification) — https://github.com/gpdaniels/spike-prime/blob/master/README.md
- ST LSM6DS3 datasheet (mirror; see caveat in text) — https://files.seeedstudio.com/wiki/Grove-6-Axis_AccelerometerAndGyroscope/res/LSM6DS3TR.pdf
- Wikipedia, Schmitt trigger — https://en.wikipedia.org/wiki/Schmitt_trigger
- Same Sky, "The basics of ultrasonic sensors" (blind zone, beam angle) — https://www.sameskydevices.com/blog/the-basics-of-ultrasonic-sensors
- Azbil, ultrasonic sensor technical guide (PDF; target-type table) — http://us.azbil.com/uploadedSpecs/GUIAGFUSONICTEC-e3RD.pdf
- iRobot, US9969089B2, "Carpet drift estimation using differential sensors" — https://patents.google.com/patent/US9969089B2/en
- Borenstein & Feng, "UMBmark: A Benchmark Test for Measuring Odometry Errors in Mobile Robots", SPIE 1995 (PDF) — https://johnloomis.org/ece445/topics/odometry/borenstein/paper60.pdf
- 3M Post-it Super Sticky Notes 3 in x 3 in (target dimensions) — https://www.post-it.com/3M/en_US/p/d/v101665017/

**Pybricks issue tracker (non-stock firmware; cited for what stock lacks)**

- https://github.com/pybricks/support/issues/989 — heading only valid in horizontal orientation
- https://github.com/pybricks/support/issues/1687 — >15 deg heading error resolved by border realignment
- https://github.com/pybricks/support/issues/1907 — guided IMU calibration routine
- https://github.com/orgs/pybricks/discussions/980 — 5-10 deg per 360 deg error with the official LEGO app

**Could NOT be fetched — anything attributed to these is marked UNVERIFIED**

- `forums.firstinspires.org` — all threads return HTTP 403 to automated fetch. The "1 deg/s drift on a
  defective hub" and "wait 1 s before resetting the gyro" claims come from search snippets only.
- `www.fllcasts.com` — HTTP 403 / Cloudflare challenge. Several promising SPIKE color-sensor and
  line-following tutorials exist there and are worth reading manually.
- `https://spike.legoeducation.com/prime/help/lls-help-python` — LEGO's own Python knowledge base is a
  JavaScript SPA and returns no text to a fetcher. The `jvolkening` and Tufts CEEO mirrors were used instead.
- `sensorpartners.com`, `ifm.com`, `chiefdelphi.com`, `antonsmindstorms.com` — HTTP 403.
- Gabriely & Rimon's Spanning Tree Coverage / Spiral-STC primary papers (ScienceDirect, ACM, Springer) — all
  403 or auth-walled. Everything said about STC here is quoted from Galceran & Carreras' description of it.
  The STC `(n+m)*D` path-length bound and worst-case-optimality claim are **UNVERIFIED**.
- Bretl & Hutchinson, "Robust coverage by a mobile robot of a planar workspace", ICRA 2013 — IEEE-paywalled.
  Quoted only via Galceran & Carreras.
- Choset 2001 full text — the CMU-hosted PDF is an image-only scan; no overlap ratio or error analysis could
  be extracted from it. **No source fetched gives a recommended boustrophedon overlap percentage as a
  function of localization error** — the closest is iRobot's 33-50 % spiral spacing.
