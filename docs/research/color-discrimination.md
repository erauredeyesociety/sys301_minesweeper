# Colour Discrimination with the SPIKE Prime Colour Sensor 45605

> **EXTERNAL research.** Nothing here was measured on our hardware. Every number that came off a real
> instrument carries its source; every number that must come off *our* instrument is marked
> **MUST BE MEASURED**. Last updated 2026-08-25. Status: reference, not a decision.
>
> **Companion file: [detection-and-sweep-techniques.md](./detection-and-sweep-techniques.md)** — presence
> detection, hysteresis, edge counting, de-duplication, sweep coverage, odometry. **This file does not
> repeat it.** Where the two meet (mounting height, sampling, run-start calibration) this file states only
> what changes *because we now want to tell colours apart*, and points there for the rest.
>
> Mission `[ASSUMED, UNCONFIRMED]`: sweep a bounded floor area, detect sticky notes, and now also report
> **which colour** each is. See [../scope.md § Mission](../scope.md#mission--pending). If the briefing says
> the targets are LEGO elements rather than paper, [§3](#3-colour-id-vs-raw-rgb--the-recommendation) flips.

---

## Summary — the eight things that matter

1. **Three documented modes** — colour ID, reflected light %, ambient light % — plus a raw **RGB+intensity**
   tuple whose range is undocumented on SPIKE 3. Officially 100 Hz, **16 mm optimal reading distance**,
   reflectivity and ambient both 0-100 % ([techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt62a78c227edef070/5f8801b9a302dc0d859a732b/techspecs_techniccolorsensor.pdf?locale=en-us), ©2019).
2. **What you can reach depends on the API generation, and ours is UNKNOWN.** SPIKE 2 exposes ambient light;
   **SPIKE 3 does not**. Both expose raw RGB+I. Method table in [§1.2](#12-spike-2-vs-spike-3--the-method-table).
3. **Built-in colour ID is a nearest-neighbour match against LEGO's own eight brick colours**, whose
   reference RGB triplets the spec sheet prints. Pastel matte paper is near none of them, and practitioners
   report exactly this failure on printed mats.
4. **So classify in software from `rgbi()`**: normalise to chromaticity (divides brightness out),
   nearest-centroid against a reference set calibrated at run start, **with the floor as a calibrated class**
   so "not a sticky note" is an ordinary outcome rather than a special case.
5. **Reject, don't guess.** Three gates — signal too weak, too far from every centroid, too close between the
   best two — each yield `UNKNOWN` with a reason code.
6. **Calibration can fail, and failing loudly at run start beats any run-time cleverness.** If pink and
   orange are not separable on this floor under these lights, the operator must learn that at 09:00 on Demo
   Day, not from the results.
7. **Mounting: 16 mm nominal, black matte shroud, sensor ahead of the drive axle.** The spot is **~12 mm
   across** at that height (one independent measurement) — that sets edge mixing and therefore speed.
8. **A classified sweep is speed-limited where a detected sweep is not.** Presence needs one differing
   sample; classification needs a run of clean interior samples. `v_max = f·(L_min − D_spot)/N_pure`, and
   `L_min` is the shortest **chord** across a note, not the note's width.

---

## 1. What the sensor can actually output

### 1.1 Official hardware specification

From the LEGO Education **Technic Color Sensor technical specifications**
([PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt62a78c227edef070/5f8801b9a302dc0d859a732b/techspecs_techniccolorsensor.pdf?locale=en-us),
footer "©2019 The LEGO Group"; extracted locally with `pdftotext`, 2026-08-25):

| Property | Official value |
|---|---|
| Key features | "Color sensing (**RGB, HSV, and LEGO® colors**)", reflectivity sensing, ambient light sensing, emission of white light |
| Sample rate | **100 Hz** |
| Optimal reading distance | **16 mm** "(depending on object size, color, and surface)" — stated identically for colour and reflectivity modes |
| Colour output | "No object" + 8 LEGO colours, each with a reference RGB triplet (below) |
| Reflectivity | 0 % "Non-reflective/nothing" … 100 % "Very reflective" |
| Ambient light | 0 % dark … 100 % bright |
| LED output | White **4000 K**, 3 individually controlled LEDs, 0-100 % in 1 % steps |
| LED caveat | "**Cannot be used while sensor is in color/light sensing mode**" |
| Connector / wire | LPF2, 250 mm fixed |
| Sheet disclaimer | "The LEGO® Education SPIKE™ app may not support all hardware features and functionalities." |

That last line is not boilerplate: it is the sheet telling you **HSV exists in the hardware and may not be
exposed to you**. It is not exposed in either Python API ([§1.3](#13-raw-lpf2-modes--what-exists-underneath)).

The eight reference colours, verbatim, with LEGO IDs and the RGB values LEGO gives:

| LEGO name | ID | RGB | | LEGO name | ID | RGB |
|---|---|---|---|---|---|---|
| White | 01 | 244, 244, 244 | | Yellow | 24 | 250, 200, 10 |
| Blue | 23 | 30, 90, 168 | | Red | 21 | 180, 0, 0 |
| Black | 26 | 0, 0, 0 | | Medium azur | 322 | 104, 195, 226 |
| Green | 28 | 0, 133, 43 | | Bright reddish violet | 124 | 144, 31, 118 |

**Look how saturated those are.** Red is `(180,0,0)` — zero green, zero blue. Nothing in a stationery pack
sits near it, or near LEGO Black `(0,0,0)`. This table *is* the reason built-in colour ID struggles on
paper: it is a classifier whose entire training set is injection-moulded ABS.

The [45605 product page](https://education.lego.com/en-us/products/lego-technic-color-sensor/45605/) (©2026)
adds only "detects colors and measures reflected and ambient light **from darkness to bright sunlight**" and
repeats 100 Hz. It never claims *constant sensitivity* across that range and never states a colour count.

### 1.2 SPIKE 2 vs SPIKE 3 — the method table

**Our Hub OS generation is UNKNOWN** ([CLAUDE.md](../../CLAUDE.md)); identify it read-only first
([../runbooks/hub-identification.md](../runbooks/hub-identification.md)). Until then, support both behind the
`src/` adapter ([ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md)).

| Capability | **SPIKE 2 (legacy)** `from spike import ColorSensor` | **SPIKE 3 (current)** `import color_sensor`, `from hub import port` |
|---|---|---|
| Address the sensor | `cs = ColorSensor('E')` — port is a **string** | no object; each call takes `port.E` |
| Colour ID | `cs.get_color()` → **string** | `color_sensor.color(port.E)` → **int**, map via `import color` |
| "nothing / unsure" | **`None`** | `color.UNKNOWN` == **`-1`** |
| Reflected light | `cs.get_reflected_light()` → **0-100 %** | `color_sensor.reflection(port.E)` → **0-100 %** |
| Ambient light | `cs.get_ambient_light()` → **0-100 %** | **NOT EXPOSED** — no ambient function in the module |
| Raw RGB + intensity | `cs.get_rgb_intensity()` → tuple, docs say **0-1024** | `color_sensor.rgbi(port.E)` → `tuple[r,g,b,i]`, **range undocumented** |
| Single raw channel | `cs.get_red()` / `get_green()` / `get_blue()`, 0-1024 | not exposed — index the tuple |
| Block until a colour | `cs.wait_until_color('blue')` | `await runloop.until(lambda: color_sensor.color(port.E) is color.BLUE)` |
| Block until colour changes | `cs.wait_for_new_color()` → string | no equivalent — write it yourself |
| Drive the emitter LEDs | `cs.light_up_all(b)` / `cs.light_up(l1,l2,l3)` | not in `color_sensor`; see [§1.3](#13-raw-lpf2-modes--what-exists-underneath) |
| Disconnected port | raises **`RuntimeError`** | undocumented; `device.ready(port)` exists — **MUST BE MEASURED** |
| Mode-change warning | explicit: ambient and light-up modes "cannot read colors" | not restated; same hardware constraint applies |

SPIKE 2 rows: [Tufts CEEO SPIKE 2 mirror](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE2.html) § Color
Sensor. SPIKE 3 rows: [Tufts CEEO SPIKE 3 mirror](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE3.html),
"Based on LEGO Education SPIKE website, **Version 3.4.3**", copied 30 Apr 2024. Both are reformatted copies
of LEGO's in-app Knowledge Base — the closest thing to official Python reference at a stable URL.

Three consequences that change the design:

- **Ambient compensation is unavailable on SPIKE 3.** You cannot read the room and subtract it. Your
  defences are a physical shroud and a calibration that bakes the room in. Do not design around an API you
  may not have.
- **`rgbi()` ranges are undocumented on SPIKE 3.** Prime Lessons, after hands-on testing: "In testing v3.4 …
  The r,g,b,i value ranges are unclear and not documented in the Knowledge Base"
  ([SP3ColorSensorPython.pdf](https://primelessons.org/en/PyProgrammingLessons/SP3ColorSensorPython.pdf),
  ©2021, last edit 09/17/2023). 0-1024 comes from the SPIKE 2 docs and the raw LPF2 mode table. Treat it as
  a hypothesis and **write the classifier so it never depends on the absolute scale** — chromaticity ratios
  are scale-free, which is a second reason to use them.
- **Mode switching is real.** One sensor, one LPF2 mode at a time; the SPIKE 2 docs warn about it plainly.
  Alternating `reflection()` and `rgbi()` every loop invites a mode-change stall of unknown length. **Pick
  one mode for the whole run, and pick `rgbi()`**: its intensity channel feeds the companion doc's presence
  detector and its RGB channels feed the classifier here.

### 1.3 Raw LPF2 modes — what exists underneath

Unofficial reverse-engineered documentation lists ten modes for this sensor
([hubmodule.readthedocs.io § Sensors](https://hubmodule.readthedocs.io/en/latest/sensors/), undated,
community-maintained):

| Mode | Name | RAW range | | Mode | Name | RAW range |
|---|---|---|---|---|---|---|
| 0 | COLOR (index) | 0-10 | | 5 | **RGB I** | 0-1024 |
| 1 | REFLT | 0-100 | | 6 | **HSV** | 0-360 |
| 2 | AMBI | 0-100 | | 7 | SHSV | 0-360 |
| 3 | LIGHT (drive LEDs) | 0-100 | | 8 | DEBUG | 0-65535 |
| 4 | RREFL (raw reflected) | 0-1024 | | 9 | CALIB | 0-65535 |

On **SPIKE 2** these are reachable as `dev = port.E.device; dev.mode(6); dev.get()` — the pattern Anton
Vanhoucke documents (`color = port.E.device; color.mode(1); port.E.pwm(-70)`) in
[*Advanced Python on LEGO SPIKE Legacy…*](https://www.antonsmindstorms.com/2021/01/14/advanced-undocumented-python-in-spike-prime-and-mindstorms-hubs/)
(updated 6 Aug 2026). Note mode 4 would give ~10 bits of presence signal instead of `reflection()`'s 7.

On **SPIKE 3** the `device` module exposes `data(port)`, `id(port)`, `ready(port)`,
`get_duty_cycle`/`set_duty_cycle` — **no documented mode setter**. Asked directly how to port
`device.mode(7); device.get()` to App 3, that article's author replied "I don't think you can. LEGO does not
allow raw data anymore" (comment 16 Nov 2024). `device.data(port)` presumably returns the payload of
whatever mode the last `color_sensor` call selected — **UNVERIFIED, and not something to build on**.

**Assume HSV mode is unavailable; compute hue ourselves from `rgbi()`** (six lines, [§4.3](#43-classification-pseudocode)).
Checking whether raw modes work costs nothing during bring-up, but it must never become a dependency — and
per **BLACKLIST rule 2** in [CLAUDE.md](../../CLAUDE.md) we do not change Hub OS to get a nicer API.

### 1.4 Settle the generation by introspection, not by trusting any document

```python
# scripts/ diagnostic, not mission code.
try:
    import color_sensor, color
    print("SPIKE 3:", [n for n in dir(color_sensor) if not n.startswith('_')])
    print("constants:", [n for n in dir(color) if n.isupper()])
except ImportError:
    from spike import ColorSensor
    print("SPIKE 2:", [n for n in dir(ColorSensor) if not n.startswith('_')])
```

Record the output in [../hardware/](../hardware/) as a dated fact. Everything downstream branches on it.

---

## 2. The discrete colour-ID palette, and how far to trust it

### 2.1 What the palettes actually are

**SPIKE 2** — `get_color()`, `wait_until_color()` and `wait_for_new_color()` share one value set, verbatim:
`'black'`, `'violet'`, `'blue'`, `'cyan'`, `'green'`, `'yellow'`, `'red'`, `'white'`, **`None`**.

**SPIKE 3** — `color_sensor.color()` returns an int mapped through the `color` module, which defines twelve
names: `BLACK` 0, `MAGENTA` 1, `PURPLE` 2, `BLUE` 3, `AZURE` 4, `TURQUOISE` 5, `GREEN` 6, `YELLOW` 7,
`ORANGE` 8, `RED` 9, `WHITE` 10, **`UNKNOWN` -1**.

**But the same page says the sensor "can recognize the following colors: Red, Green, Blue, Magenta, Yellow,
Orange, Azure, Black, White"** — nine, not eleven. `PURPLE` and `TURQUOISE` are constants the module defines
that the docs never claim the sensor produces. And Prime Lessons, testing v3.4, report **"Orange color could
not be recognized"**, taking the practical list to eight.

Four sources, four different palettes (8 SPIKE 2 strings; 9 documented SPIKE 3 names; 11 SPIKE 3 constants;
8 hardware reference colours, minus Orange in practice). **The palette is firmware-version dependent and
partly wrong in the docs.** Never hard-code an expected colour list.

**"Unsure" and "nothing" are the same value.** SPIKE 2 returns `None` — which silently poisons `c == 'red'`
and crashes `c.upper()`. SPIKE 3 returns `-1`; Prime Lessons phrase it as "No color or unrecognized color is
the UNKNOWN value". **Empty floor and unclassifiable note are indistinguishable in colour mode** — and that
is exactly the distinction our mission needs. Raw RGB *can* separate them: "nothing there" is low total
signal; "cannot match" is adequate signal far from every centroid.

### 2.2 Paper vs plastic — the crux, from practitioners

The strongest published analogue to matte paper is FLL coaching material about *printed mats*:

> "In color mode, the sensor shines a whitish light on the board and tries to match the reflected light to
> of the standard LEGO brick colors. **Since the mat's printing does not match LEGO brick colors the colors
> the sensor reports are often unpredictable. What looks green to you may look be closer to LEGO black than
> LEGO green.**" … "The color sensor also reads regions of the table at a time. **If it sees a bit of yellow
> and a bit of blue – it may report the color as green.**"
> — [FLLTutorials.com, *Finding Lines*](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf), ©2023, last edit 29 May 2023

Both sentences are damning, for different reasons: the first says the *classifier* is wrong on non-LEGO
pigments; the second says the *optics* average over an area, so at a note's edge the reported class is a
colour physically present nowhere.

Independent corroboration, Feb 2026: SPIKE Prime colour sensors returning black as "None or blue", white as
"yellow or green", green as "blue or black", with HSV and reflection values shifting substantially between
surfaces ([pybricks/discussions #2591](https://github.com/orgs/pybricks/discussions/2591), 24-26 Feb 2026).
That thread's platform **is permanently excluded for us** ([ADR-0001](../decisions/0001-stock-lego-firmware-only.md))
— cite it for physics and technique, never as a suggestion to switch firmware. The maintainer's remedy
transfers directly and is the architecture recommended below: restrict the candidate set to the colours you
actually expect and round everything to the nearest of those; for **drive-by** detection compute an *error*
to each candidate and take the lowest, "potentially using hue distance as a primary variable while enforcing
saturation and value thresholds." That is a nearest-neighbour classifier with rejection gates, and we can
implement it on stock firmware from `rgbi()`.

Two cautions about the FLL deck: its "shines a **red** light" line is EV3 legacy and **wrong for SPIKE**
(4000 K white per the spec sheet), and its "You do not need to calibrate your color sensor on a SPIKE Prime"
means only that *the EV3 min/max reflectance ritual* is unnecessary — not that you can skip capturing
per-colour references for pastel paper on an unknown floor, which solves a different problem.

### 2.3 Verdict

**Do not use `color()` / `get_color()` as the mission's classifier.** Four independent reasons, any one
sufficient: (1) its reference set is eight saturated ABS colours; (2) the palette varies by generation and
contradicts the docs; (3) it collapses "nothing there" and "cannot classify"; (4) it spatially averages, so
edges produce phantom classes.

**Use it as a logged cross-check.** If it turns out the notes we are given *are* saturated enough that
`color()` agrees ≥95 % of the time, that is a finding worth recording — and a one-line fallback.

---

## 3. Colour ID vs raw RGB — the recommendation

**Classify in software from `rgbi()`, in normalised chromaticity space, against a run-start-calibrated
reference set that includes the floor as a class.**

*Why chromaticity rather than raw RGB.* The sensing gap changes as the robot rolls (chassis pitch, carpet
pile compressing under the wheels, a note on a wrinkle), and gap changes scale **all three channels
together** — brightness, not colour. Dividing by `R+G+B` removes that common factor to first order. Battery
sag over a long run does the same thing, and is removed the same way. And the absolute scale of `rgbi()` is
undocumented on SPIKE 3; ratios do not care.

*Why not plain hue.* Hue alone discards the pale-pink/saturated-red distinction, and it is numerically
unstable exactly where sticky notes live — near the achromatic axis, where a small channel change swings hue
wildly. Chromaticity `(r_n, g_n)` keeps both "where on the wheel" and "how far from grey" in one
well-conditioned pair. **Compute hue and saturation too, but as gates, not as the primary metric.**

*Why the floor must be a class.* Without it, every decision is "which note colour is this most like", and
bare floor gets forced into one. With the floor as class zero, "no note here" is just the nearest-centroid
answer, and the presence detector and the classifier become the same code. The companion doc's
hysteresis/dwell state machine still runs on top — see
[detection-and-sweep-techniques.md § Edge-counting state machine](./detection-and-sweep-techniques.md#edge-counting-state-machine).

**This recommendation flips** if the briefing specifies LEGO-coloured LEGO elements: `color()` is then
LEGO's own factory-calibrated classifier for exactly that input, and it costs one line.

---

## 4. Calibration and classification

### 4.1 What "calibration" means here

Not the EV3 white/black reflectance stretch. It means: **before every run, on the actual floor, under the
actual lights, with the actual pack of notes, capture a reference cluster per class** — one per note colour,
plus the floor, plus the arena boundary tape if there is one. Every threshold is then derived from those
clusters instead of typed into the source, which is scope requirement **[TR-4](../scope.md#technical-tr)**.

### 4.2 Operator procedure (belongs in `docs/runbooks/` once agreed)

The **Builder** is the only person who may operate the robot ([CLAUDE.md](../../CLAUDE.md) § Course rules),
so these are Builder steps.

1. Robot on the arena floor, in the arena, lighting in its Demo Day state (blinds, overheads, projector).
   Note the time of day.
2. Run the calibration program; it prompts on the 5×5 matrix for each class in a fixed order.
3. Per class, the Builder holds the sensor over a sample and presses the left hub button; the program
   captures a burst, then prompts for the next **placement** of the same class.
4. **Three placements × 20 samples = 60 samples per class.** Three placements, not one, because that is what
   captures within-class variation — print inhomogeneity, the adhesive strip, a wrinkle, a pen mark. One
   placement gives a beautifully tight cluster that lies about the real spread.
5. The **floor** gets five placements from different parts of the arena; floors are less uniform than notes.
6. The program prints a separability report and either passes or **fails loudly** ([§4.4](#44-detecting-that-calibration-failed)).
7. Recalibrate on any change: lighting, floor, note pack, battery, or sensor height.

20 samples at 100 Hz is 200 ms, so the whole capture is under 30 s including handling. Statistics stop
improving much past ~20 per placement; the *placements* buy the accuracy. Take **medians, not means** — one
flicker beat or stray highlight must not move a centroid — and use `σ ≈ 1.4826 × MAD` for spread.

### 4.3 Classification pseudocode

Pure Python, no hub imports: this belongs in `src/`, is unit-testable on the Ubuntu host against
recorded sample vectors, and never sees a port letter ([ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md)).

```python
# ---- adapter (src/): the ONLY place that knows the API generation ----
# SPIKE 3: color_sensor.rgbi(PORT_COLOR)      SPIKE 2: sensor.get_rgb_intensity()
# Both yield (r, g, b, i). No absolute scale is assumed anywhere below.

def features(sample):
    """(r,g,b,i) -> (r_n, g_n, sat, total), or None if there is no usable signal."""
    r, g, b, i = sample
    total = r + g + b
    if total <= 0:
        return None
    r_n, g_n = r / total, g / total          # chromaticity: brightness divided out
    mx, mn   = max(r, g, b), min(r, g, b)
    sat      = 0.0 if mx == 0 else (mx - mn) / mx
    return (r_n, g_n, sat, total)

def hue_deg(sample):
    """Diagnostic / secondary gate only. Undefined near grey - gate on sat first."""
    r, g, b, _ = sample
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return None                          # achromatic: hue is undefined, not zero
    if   mx == r: return 60 * (((g - b) / d) % 6)
    elif mx == g: return 60 * (((b - r) / d) + 2)
    else:         return 60 * (((r - g) / d) + 4)

def calibrate_class(name, bursts):
    """bursts: one list of raw (r,g,b,i) samples per placement."""
    pts = [f for f in (features(s) for burst in bursts for s in burst) if f]
    cx, cy = median([p[0] for p in pts]), median([p[1] for p in pts])
    dists  = [hypot(p[0] - cx, p[1] - cy) for p in pts]
    sigma  = max(1.4826 * median([abs(d - median(dists)) for d in dists]), 1e-4)
    return Reference(name=name, centroid=(cx, cy), sigma=sigma,
                     sat_median=median([p[2] for p in pts]),
                     total_median=median([p[3] for p in pts]), n=len(pts))

K_FAR    = 3.0     # reject if the best distance exceeds K_FAR sigmas of that class
K_MARGIN = 0.80    # reject if d_best / d_second > K_MARGIN (the two are too close)

def classify(sample, refs, s_min):
    f = features(sample)
    if f is None or f[3] < s_min:
        return ("UNKNOWN", "LOW_SIGNAL", None)          # nothing there / too far / fault
    x, y = f[0], f[1]
    scored = sorted(((hypot(x - r.centroid[0], y - r.centroid[1]) / r.sigma, r) for r in refs),
                    key=lambda t: t[0])
    (d1, best), (d2, _) = scored[0], (scored[1] if len(scored) > 1 else (float('inf'), None))
    if d1 > K_FAR:
        return ("UNKNOWN", "FAR_FROM_ALL", best.name)   # keep the nearest anyway, for the log
    if d2 > 0 and (d1 / d2) > K_MARGIN:
        return ("UNKNOWN", "AMBIGUOUS", best.name)
    return (best.name, "OK", best.name)

def decide_event(samples, refs, s_min, edge_guard):
    """samples: every raw sample from target-entry to target-exit, in order.
       edge_guard: samples to drop at each end - computed from speed, see section 5."""
    core = samples[edge_guard:len(samples) - edge_guard]
    if len(core) < MIN_CORE_SAMPLES:
        return ("UNKNOWN", "TOO_FEW_SAMPLES", len(samples))
    votes = [v for v in (classify(s, refs, s_min)[0] for s in core) if v != "FLOOR"]
    if not votes:
        return ("UNKNOWN", "NO_TARGET_VOTES", len(core))
    winner, n = most_common(votes)
    if n / len(votes) < MODAL_FRACTION_MIN:             # 0.60 is a sane starting point
        return ("UNKNOWN", "SPLIT_VOTE", len(core))
    return (winner, "OK", len(core))
```

`K_FAR = 3.0`, `K_MARGIN = 0.80`, `MODAL_FRACTION_MIN = 0.60`, `MIN_CORE_SAMPLES = 5` are **chosen for
shape, not tuned** — every one **MUST BE MEASURED** by replaying recorded runs ([§8](#8-what-must-be-measured-on-real-hardware)),
and recorded in the results alongside the numbers they produced, per [CLAUDE.md](../../CLAUDE.md) "record the
measurement, not just the conclusion."

`S_MIN` must come from the calibration data, not a guess. Defensible rule: `S_MIN = 0.5 × min(total_median)`
over all calibrated classes — anything less than half as bright as the darkest thing you calibrated is not a
thing you calibrated.

### 4.4 Detecting that calibration failed

Run all of these at the end of calibration; **refuse to start the mission** on any failure, and print why.

| Check | Condition | What it means |
|---|---|---|
| Signal floor | any class `total_median < S_MIN_ABS` | sensor too high, unplugged, or shroud blocking the emitter |
| Cluster tightness | `sigma_c > SIGMA_MAX` | robot moved during a burst, or that stock is wildly inhomogeneous |
| Pairwise separability | `dist(mu_a, mu_b) < 3·(sigma_a + sigma_b)/2` for any pair | **those two colours cannot be told apart today** — name the pair in the message |
| Floor separability | any note class fails the above against `FLOOR` | that colour is invisible on this floor (white note, white tile) |
| Bimodality | within one class, `max(dist) > 5·sigma` | two different surfaces captured under one label |
| Sample count | `n < 0.9 × expected` | bursts were dropped; the loop is not running at the rate you think |

The pairwise check earns its keep: it converts the worst Demo Day outcome — confidently reporting four pinks
that were two pinks and two oranges — into a 09:00 message saying "PINK and ORANGE are not separable."

---

## 5. Mounting geometry and the speed arithmetic

The companion doc's conclusions hold — **16 mm nominal, perpendicular, ahead of the drive axle, braced,
black matte shroud that does not touch the floor**
([§ Mounting geometry](./detection-and-sweep-techniques.md#mounting-geometry), § Ambient-light shielding).
Below is only what changes when the requirement is *classification*.

### 5.1 Spot size governs everything

One independent measurement exists. Marek at biasedlogic built a rack-and-pinion rig, set the sensor
"exactly 2 studs above" the surface (2 studs = **16 mm**, the spec's optimal distance) and stepped it across
24/16/8 mm bars: field of view **≈1.5 studs ≈ 12 mm**, and "the sensor watches a bigger field" than a point
sensor, so edges give gradual transitions
([biasedlogic.com](https://biasedlogic.com/index.php/lego-spike-color-sensor/), 18 Dec 2021). Corroborating
detail: the 8 mm stripe never reached the reading the 24 mm stripe did — the spot was never wholly inside it.

**Single source, one sensor, one height: treat `D_spot ≈ 12 mm at 16 mm` as a working figure and re-measure
it on ours** ([§8](#8-what-must-be-measured-on-real-hardware)). It is a 30-minute experiment with a printed
card and it feeds every speed decision below.

Colour-specific consequences:

- **Every edge produces ~12 mm of physically blended readings** whose chromaticity belongs to no class —
  the mechanism behind "a bit of yellow and a bit of blue → green". Defence: `edge_guard` in `decide_event()`.
- **Spot area scales with height.** Higher averages over more floor (worse edges, weaker signal); lower
  breaks colour mode outright — Prime Lessons found LEGO's own Advanced Driving Base mounts at ~8 mm and
  that "**Black does not read correctly in Color Mode**" as a result, and ship a modification raising it one
  LEGO module. **Copying ADB inherits a known-bad height.** Start at 16 mm.
- **Shielding matters more for colour than for presence.** A presence threshold only needs the floor-target
  *difference* to survive an ambient offset; a chromaticity classifier needs the *ratios* to. Additive
  broadband ambient pulls every class toward the ambient source's own chromaticity — i.e. it compresses the
  classes together, which is precisely what stops two similar pastels being separable.

### 5.2 Sample pitch and the maximum sweep speed

Officially 100 Hz for the sensor and 100 Hz for the motor encoders. That is the *hardware* rate; the rate a
Python loop achieves is **UNVERIFIED and must be measured** — you poll from an async runloop, you do not
receive a hardware-timed stream. Sample pitch is `d = v / f`; the samples spent crossing one edge is
`D_spot·f / v`:

| Forward speed `v` | mm per sample (`f`=100 Hz) | samples per 12 mm edge |
|---|---|---|
| 100 mm/s | 1.0 | 12 |
| 150 mm/s | 1.5 | 8 |
| 200 mm/s | 2.0 | 6 |
| 300 mm/s | 3.0 | 4 |
| 400 mm/s | 4.0 | 3 |

**Set `edge_guard = ceil(D_spot·f/v)` from the *measured* speed — never hard-code it.**

Presence needs one sample differing from the floor. Classification needs `N_pure` samples with the spot
**entirely inside** the note. For a straight crossing of chord `L`:

```
pure_samples = f · (L − D_spot) / v            v_max = f · (L_min − D_spot) / N_pure
```

With `f = 100 Hz`, `D_spot = 12 mm`:

| Worst-case chord `L_min` | `v_max`, `N_pure` = 5 | `v_max`, `N_pure` = 10 |
|---|---|---|
| 76 mm (dead-centre crossing of a 3 in note) | 1280 mm/s | 640 mm/s |
| 50 mm | 760 mm/s | 380 mm/s |
| 40 mm | 560 mm/s | 280 mm/s |
| 30 mm | 360 mm/s | 180 mm/s |
| 20 mm | 160 mm/s | 80 mm/s |
| 15 mm | 60 mm/s | 30 mm/s |

**`L_min` is the shortest chord the sweep can produce, not the note's width.** A lane clipping a corner gives
a few millimetres and no speed makes that classifiable — a *coverage geometry* problem, and the companion
doc's territory ([§ De-duplication strategy](./detection-and-sweep-techniques.md#de-duplication-strategy)).
The colour requirement adds one constraint to that design: **lane spacing must guarantee every note is
crossed by at least one lane with chord ≥ `L_min`**, and `L_min` then sets the speed. Choosing overlap so
`L_min ≥ 40 mm` puts the limit above anything the drivetrain can do — the comfortable regime.

Contrast with the companion doc's presence-only finding ("sampling rate is not your limiting factor" even at
700 mm/s). **For classification it can become the limiting factor, and it does so at glancing chords.** That
is the single most important difference between the two requirements.

### 5.3 Motor choice, gearing, wheel size, offset

Official figures, extracted from LEGO's spec sheets with `pdftotext` on 2026-08-25
([45602](https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltb9abb42596a7f1b3/5f8801b5f4c5ce0e93db1587/le_spike-prime_tech-fact-sheet_45602_1hy19.pdf?locale=en-us),
[45607](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt20ee0f27f6735942/60fe86455483765886b0da3c/LE_SPIKE_Essential_Tech_fact_sheet_Small_Angular_Motor_45607_2HY21_Digital.pdf)):

| | **Large 45602** | **Small 45607** |
|---|---|---|
| No-load speed | 175 RPM ±15 % | 110 RPM ±15 % |
| Max-efficiency point | 135 RPM @ 8 Ncm | 85 RPM @ 1.8 Ncm |
| Stall torque | 25 Ncm | 5 Ncm |
| Encoder | 360 counts/rev at output axle, 100 Hz | 360 counts/rev at output axle, 100 Hz |
| Accuracy | ≤ ±3° (sensor + gearbox slack) | ±1° sensor, ±3° control |
| Rated supply | 7.2 V | 5 V |

With LEGO's own wheel — "**a diameter of 5.6 cm (2.2 in.) and travels a distance of 17.6 cm (6.9 in.) per
rotation**" ([*Going the Distance*](https://education.lego.com/en-us/lessons/prime-extra-resources/going-the-distance/), ©2026)
— direct drive gives **513 mm/s** no-load and **396 mm/s** at max efficiency for the large motor, versus
**323** and **249 mm/s** for the small one. Commanded velocity is degrees per second at the motor, so
`ω = v × 360/176 = v × 2.045`:

| Target `v` | `ω` command | % of large's no-load (1050 °/s) | % of small's (660 °/s) |
|---|---|---|---|
| 100 mm/s | 205 °/s | 20 % | 31 % |
| 150 mm/s | 307 °/s | 29 % | 46 % |
| 200 mm/s | 409 °/s | 39 % | 62 % |
| 300 mm/s | 614 °/s | 58 % | 93 % |

- **Slow-speed smoothness, not top speed, is what colour work needs.** In the 150-250 mm/s classification
  band the large motor sits at 29-49 % of no-load with torque headroom for carpet; the small motor sits at
  46-77 %, close enough to its ceiling that a carpet seam or battery sag becomes a speed dip — which becomes
  a wrong `edge_guard` and a variable sample pitch. **Use the large 45602 for drive.**
- **A gear reduction buys resolution.** The encoder counts at the *motor*. Direct drive: 176 mm ÷ 360 =
  **0.489 mm/count**, and ±3° control accuracy is **±1.5 mm** of travel. A 2:1 reduction (20t → 40t) gives
  720 counts per wheel revolution = **0.244 mm/count**, ±0.73 mm, double torque, half top speed (large motor:
  256 mm/s — still above the classification band). Cost: added backlash, and the ±3° figure already includes
  gearbox slack once. **UNVERIFIED how much external gears add** — measure if we gear it.
- **Smaller wheels are the cheaper version of the same trick**, halving both speed and mm-per-count with no
  gear train. Whatever we choose, the *effective rolling circumference under load* is not the nominal 176 mm
  and **MUST BE MEASURED**; `v` in every formula above is ground speed, not commanded speed.
- **The small 45607 has a real role** — a sensor lift or a marker gate. Its 5 Ncm stall torque is useless
  for pushing a chassis on carpet.
- **Forward offset** puts the sensing point ahead of the wheels (companion doc). Two colour riders: the
  offset is the budget for any "stop on the target" behaviour, so it must exceed stopping distance at sweep
  speed (**MUST BE MEASURED**, five trials); and during a turn it multiplies heading error into lateral
  error as `offset × sin θ` — 60 mm offset with 5° error is 5.2 mm, a real fraction of a 12 mm spot. Keep
  the offset modest rather than cantilevering the sensor far out front.

---

## 6. Failure modes specific to colour

| # | Failure | Mechanism | Mitigation |
|---|---|---|---|
| C1 | **Two adjacent different-coloured notes read as one target** | The presence signal never returns to floor between them, so one event spans two colours | Detect rather than prevent: if modal fraction falls below `MODAL_FRACTION_MIN` **and** the vote sequence is *contiguous* (14×PINK then 12×BLUE, not interleaved), split at the changepoint and emit two results; if interleaved it is noise — emit one `UNKNOWN`. Log the two cases distinctly |
| C2 | **One note reported as two colours at its edge** | ~12 mm of blended readings at every boundary; a blend can land on a third class's centroid | `edge_guard = ceil(D_spot·f/v)` at each end; modal vote over the core; `K_MARGIN` rejects between-centroid blends. **Never classify on a single sample** |
| C3 | **The robot's own shadow** | Chassis and shroud cast a moving hard shadow edge; ambient under the skirt is not uniform across the spot | Shroud is the fix, but make it *symmetric* so residual ambient is at least constant with heading; calibrate with it fitted and the robot in running attitude. **MUST BE MEASURED:** same target, four headings — the chromaticity spread across headings is the shadow error budget |
| C4 | **Coloured floor mistaken for a target** | A beige tile is chromatically close to a beige note | Floor is a calibrated class, so this is caught by the floor-separability check at calibration, not at run time. If it fails, the honest answer is "we cannot count beige notes on this floor" |
| C5 | **Arena boundary line counted as a target** | Tape is usually strongly coloured, so it classifies cleanly — as *something* | Calibrate it as its own `BOUNDARY` class and exclude it from the counts; this also hands the boundary logic a classifier for free. If the tape colour matches a note colour, say so and ask the instructor |
| C6 | **Mains lighting flicker** | Mains-driven lamps modulate at twice line frequency — **120 Hz in the US** — and simple LED drivers approach full modulation depth ([DIAL, IEEE 1789](https://www.dial.de/en-GB/articles/ieee-1789-a-new-standard-for-evaluating-flickering-leds), 23 Jun 2022) | Sampling at ~100 Hz against 120 Hz aliases to a **20 Hz beat (50 ms, 5 samples)** — *derived here, not measured*. Median-filtering over a multiple of 5 samples cancels an exact 20 Hz beat; `N_pure ≥ 10` covers two beat periods. Physically the shroud plus the 4000 K emitter should dominate at 16 mm. **UNVERIFIED whether the sensor strobes its LED to subtract ambient** — LEGO does not say |
| C7 | **Ambient level changes mid-run** | Sun moves, a door opens, a projector switches on | Chromaticity divides out *scaling*, not *additive* ambient. Detect drift instead: the floor is the majority of every lane, so track its centroid; if it migrates by more than `K_FAR·σ`, flag `CALIBRATION_STALE` in the result and keep going |
| C8 | **Mode thrash** | Alternating `reflection()` and `rgbi()` forces LPF2 mode changes of unknown latency | One mode (`rgbi()`) for the whole run. Never call `light_up_all()` during a sweep — the spec sheet says LED output "cannot be used while sensor is in color/light sensing mode" |
| C9 | **Gloss / specular highlight** | A specular reflection of the 4000 K emitter is near-white and swamps the pigment | Appears as a low-saturation outlier: the `sat` gate catches it, median centroids resist it, and mounting perpendicular keeps the specular lobe out of the aperture. A whole note reading white is a real finding — record it |
| C10 | **`None` / `UNKNOWN` handling bug** | SPIKE 2 returns `None`, SPIKE 3 returns `-1`; either silently corrupts a comparison chain | Do not use colour mode as the classifier; if logged as a cross-check, normalise it to one sentinel in the adapter before it reaches `src/` |
| C11 | **Sensor unplugged or not ready mid-run** | SPIKE 2 raises `RuntimeError`; SPIKE 3 offers `device.ready(port)` | Wrap reads in the adapter and emit a `SENSOR_FAULT` sample, never a value. Gate run start on `device.ready()` |
| C12 | **Battery sag over a long run** | Emitter output and motor speed both fall; chromaticity survives the first, but `v` changes under the second | Compute `edge_guard` from measured wheel speed, not commanded speed. Log battery level at start and end |

---

## 7. Recommended result data model

**Report per-colour counts, a total, and the unclassified — always, including when the unclassified count is
zero.** "12 pink, 9 blue" that quietly discarded four unreadable notes is not a measurement, it is a story.
The unknown count is the instrument's own error bar and belongs in the Intro Report's results section next
to the numbers it qualifies.

```python
# src/ - pure data, no hub imports, JSON-serialisable, host-testable

TargetEvent = {
    "event_id": int, "lane": int, "distance_mm": float,   # odometry - see companion doc
    "n_samples": int, "n_core": int, "edge_guard": int,
    "decision": str,        # "PINK" | "BLUE" | ... | "UNKNOWN"
    "reason":   str,        # "OK" | "LOW_SIGNAL" | "FAR_FROM_ALL" | "AMBIGUOUS"
                            #      | "SPLIT_VOTE" | "TOO_FEW_SAMPLES" | "SENSOR_FAULT"
    "modal_fraction": float,             # confidence 0..1
    "nearest": str,                      # best class even when rejected - best debug field there is
    "d_best": float, "d_second": float,  # in sigmas
    "chroma": (float, float),            # event-median (r_n, g_n) - enables offline re-classification
}

RunResult = {
    "counts":            {"PINK": 12, "BLUE": 9, "YELLOW": 7},   # calibrated classes only
    "unknown":           4,        # NEVER omit, NEVER fold into a colour
    "unknown_by_reason": {"AMBIGUOUS": 2, "SPLIT_VOTE": 1, "LOW_SIGNAL": 1},
    "classified_total":  28,       # sum(counts)
    "detected_total":    32,       # sum(counts) + unknown  <- the presence detector's number
    "boundary_hits":     6,        # BOUNDARY events, deliberately not counted as targets
    "events":            [TargetEvent, ...],
    "calibration": {"timestamp": str, "operator": str, "classes": {...centroids, sigmas, n...},
                    "separability_min_pair": ("PINK", "ORANGE"), "separability_min_value": 4.1,
                    "stale": False},
    "run": {"speed_mm_s": 200, "edge_guard": 6, "lanes": 8, "sample_rate_measured_hz": 96.4,
            "battery_start": 92, "battery_end": 78, "aborted": False, "abort_reason": None},
}
```

- **`detected_total` must equal `classified_total + unknown`** — assert it in the floor tests. If they ever
  disagree, an event was dropped and the run is not trustworthy.
- **`detected_total` is directly comparable with the companion doc's presence-only count.** Classification is
  a layer *on top of* detection, so a colour bug can never reduce the headline count — worst case it moves a
  note from a colour bucket to `unknown`. Preserve that separation in the code, not just the write-up.
- **Every rejected event keeps `nearest`, `d_best`, `d_second`, `chroma`.** Because raw chromaticity is
  retained, a run can be **re-classified offline on the host** with different constants and no re-run. That
  turns every practice run into calibration data and is the highest-value line in this model.
- **Untethered reporting** (scope **[FR-4](../scope.md#functional-fr)**) is constrained by a 5×5 matrix:
  scroll the total, then each colour's count, then `?` and the unknown count; a distinct beep on each
  rejected event so the Builder *hears* ambiguity happening. Full `RunResult` goes to `print()` for capture
  when tethered. **UNVERIFIED whether stock firmware permits writing a file on the hub** — do not depend on it.

---

## 8. What must be measured on real hardware

Nothing here was measured by its author. In order of decisions unblocked per minute; all are `scripts/`
diagnostics, not tests ([CLAUDE.md](../../CLAUDE.md) § Testing), all Builder-operated.

1. **API generation** — run [§1.4](#14-settle-the-generation-by-introspection-not-by-trusting-any-document). *Blocks everything.*
2. **`rgbi()` range and behaviour** — white paper, black paper, held in air. Min/max per channel and for `i`.
   Confirms or refutes 0-1024, shows what "no object" looks like, sets `S_MIN`.
3. **Achieved sample rate** — time 1000 `rgbi()` calls in the real runloop with motors running. Gives the
   real `f` for every formula in §5. Expect below 100 Hz.
4. **Spot size** — printed card with 24/16/12/8/4 mm black bars on white; drive across at a known slow speed
   at 16 mm; plot intensity. Repeat at 12 and 20 mm for the height trade-off curve.
5. **Per-colour separability on the real note pack** — full calibration on the real floor, print the pairwise
   matrix. **This is the go/no-go for the whole colour requirement** and belongs before any sweep code, while
   the team can still ask for a different pack.
6. **Height sweep** — repeat #5 at 12/16/20/24 mm; pick the height with the best *worst-pair* separability,
   not the best average.
7. **Heading/shadow sensitivity (C3)** — same note, four headings, robot in running attitude.
8. **Flicker (C6)** — 500 stationary samples under arena lighting; look for periodicity in total intensity.
   Control: room lights off.
9. **Speed validation** — with calibration loaded, drive a known layout at 100/150/200/300 mm/s, five passes
   each; report classified/unknown/missed per speed. Pick the speed from *this* table; §5.2 only says where
   to start looking.
10. **Effective rolling circumference and stopping distance** — companion doc's odometry section; needed here
    because `v` in every formula must be ground speed.

---

## 9. Open questions

- **The mission is still assumed.** Are the targets sticky notes? How many colours? Does scoring care which
  colour? **Is a misclassification worse than an `UNKNOWN`?** — that last one sets `K_FAR` and `K_MARGIN`,
  and nothing else can. → [../scope.md § Mission](../scope.md#mission--pending)
- **Hub OS generation** — unknown; blocks the method names. → [../runbooks/hub-identification.md](../runbooks/hub-identification.md)
- **Is `rgbi()` sampled at the same 100 Hz as `reflection()`, and is `i` a simple sum of R+G+B?** Undocumented.
  Decides whether `i` is a drop-in for `reflection()` in the companion doc's presence detector.
- **Does the sensor internally compensate for ambient light** (e.g. by strobing its emitter)? LEGO claims
  operation "from darkness to bright sunlight" but documents no mechanism. Sets what the shroud is worth.
- **Mode-change latency** between LPF2 modes — unmeasured anywhere found. Only matters if we mix modes; the
  recommendation is not to.
- **Floor material on Demo Day** — carpet vs tile changes both gap stability and the floor's own chromaticity.
- **Does the arena have a coloured boundary?** If so it must be calibrated as `BOUNDARY` (C5).
- **UNVERIFIED: `device.data(port)` on SPIKE 3** — whether it returns the current mode's raw payload and
  whether any mode selection is possible. Cheap to check at bring-up; must not become a dependency.

---

## 10. Sources

All URLs fetched by the author on **2026-08-25** unless noted; PDFs extracted locally with `pdftotext`.

**Official LEGO Education**

- [Color Sensor 45605 — technical specifications PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt62a78c227edef070/5f8801b9a302dc0d859a732b/techspecs_techniccolorsensor.pdf?locale=en-us) (©2019) — modes, 100 Hz, 16 mm, the eight reference colours and their RGB values, 4000 K emitter, the "may not support all hardware features" disclaimer.
- [Color Sensor 45605 — product page](https://education.lego.com/en-us/products/lego-technic-color-sensor/45605/) (©2026) — "darkness to bright sunlight", 100 Hz. Marketing; no colour count, no RGB claim.
- [Large Angular Motor 45602 — techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/bltb9abb42596a7f1b3/5f8801b5f4c5ce0e93db1587/le_spike-prime_tech-fact-sheet_45602_1hy19.pdf?locale=en-us) (©2019) — 175/135 RPM, 25 Ncm, 360 counts/rev, ≤±3°.
- [Small Angular Motor 45607 — techspecs PDF](https://assets.education.lego.com/v3/assets/blt293eea581807678a/blt20ee0f27f6735942/60fe86455483765886b0da3c/LE_SPIKE_Essential_Tech_fact_sheet_Small_Angular_Motor_45607_2HY21_Digital.pdf) (©2021) — 110/85 RPM, 5 Ncm, ±1° sensor accuracy.
- [Lesson "Going the Distance"](https://education.lego.com/en-us/lessons/prime-extra-resources/going-the-distance/) (©2026) — wheel 5.6 cm diameter, 17.6 cm per rotation.

**LEGO's own Python Knowledge Base, mirrored at stable URLs**

- [SPIKE 3 Python docs (Tufts CEEO mirror)](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE3.html) — mirrors LEGO site **v3.4.3**, copied 30 Apr 2024. `color_sensor.color/reflection/rgbi`, the `color` constants, the `device` module, and the absence of any ambient function.
- [SPIKE 2 Python docs (Tufts CEEO mirror)](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE2.html) — legacy `ColorSensor`: `get_color` (with `None`), `get_ambient_light`, `get_reflected_light`, `get_rgb_intensity` (0-1024), `get_red/green/blue`, `wait_until_color`, `wait_for_new_color`, `light_up_all`, `light_up`, `RuntimeError` on disconnect, explicit mode-change warnings.

**Practitioner sources, dated, read with their platform in mind**

- [Prime Lessons, *Introduction to Color Sensor* (SPIKE 3 Python)](https://primelessons.org/en/PyProgrammingLessons/SP3ColorSensorPython.pdf) — ©2021, last edit 17 Sep 2023. White (not red) emitter; 16 mm; "Orange color could not be recognized"; "r,g,b,i value ranges are unclear and not documented"; the ADB 8 mm mounting problem and its fix.
- [FLLTutorials.com, *Finding Lines*](https://flltutorials.com/translations/en-us/RobotGame/FindingLines.pdf) — ©2023, last edit 29 May 2023. Colour mode unreliable on printed mats; area-averaging producing phantom colours at edges. (Its "red light" line is EV3 legacy and wrong for SPIKE.)
- [biasedlogic.com, *LEGO Spike Color Sensor*](https://biasedlogic.com/index.php/lego-spike-color-sensor/) — 18 Dec 2021. Measured field of view ≈1.5 studs (12 mm) at 2 studs height; gradual edge transitions. Single measurement — re-measure.
- [pybricks/discussions #2591](https://github.com/orgs/pybricks/discussions/2591) — 24-26 Feb 2026. Real misclassification reports; maintainer's remedy = restrict the candidate set, take the lowest-error match, hue distance with saturation/value gates. **Pybricks is excluded for us ([ADR-0001](../decisions/0001-stock-lego-firmware-only.md)); cited for technique only.**
- [antonsmindstorms.com, *Advanced Python on LEGO SPIKE Legacy…*](https://www.antonsmindstorms.com/2021/01/14/advanced-undocumented-python-in-spike-prime-and-mindstorms-hubs/) — updated 6 Aug 2026. Low-level `port.X.device.mode()/get()` on SPIKE 2; author's comment (16 Nov 2024) that raw mode access is gone on App 3.
- [hubmodule.readthedocs.io, *Sensors (Device)*](https://hubmodule.readthedocs.io/en/latest/sensors/) — undated, unofficial. The ten LPF2 colour-sensor modes including HSV (6) and RGB I (5, 0-1024).
- [DIAL, *IEEE 1789: a new standard for evaluating flickering LEDs?*](https://www.dial.de/en-GB/articles/ieee-1789-a-new-standard-for-evaluating-flickering-leds) — 23 Jun 2022. Mains-driven lamps modulate at twice line frequency (100 Hz EU / **120 Hz US**); simple LED drivers reach very high modulation depth.

**In this repo**

- [detection-and-sweep-techniques.md](./detection-and-sweep-techniques.md) — presence detection, hysteresis and dwell, edge counting, de-duplication, coverage, odometry. Read it first; this file assumes it.
- [../scope.md](../scope.md) · [../../CLAUDE.md](../../CLAUDE.md) · [ADR-0001](../decisions/0001-stock-lego-firmware-only.md) · [ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md) · [../runbooks/hub-identification.md](../runbooks/hub-identification.md)
