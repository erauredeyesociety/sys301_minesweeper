# Finding — Colour sensor, first real surfaces: range, separability, and saturation

**Date:** 2026-09-01 · **Hub:** connected over USB · **Sensor:** port C (front-corner) ·
**Written to hub:** nothing — `examples/color_live.py` run in RAM via `hub_programmer/run.py`.
Raw capture: [runs/color-surfaces-2026-09-01.txt](./runs/color-surfaces-2026-09-01.txt).

> **These are measurements**, but on **substitute surfaces**, not the mission's. We had no yellow
> sticky note and no arena tape. The operator presented, in order: **khaki fabric (trousers), a red
> laminated name card, a green one, a blue one, and white paper.** Class carpet was too far below the
> ~51 mm-high sensor to read. So this characterises the **sensor and the method**, which is what
> GATE 1 needs first — it does **not** yet answer the mission's yellow-note / blue-tape / silver-tape
> question. `[ASSUMED]` nothing about the real surfaces from this.

## What was measured (sensor C, 380 samples over 95 s)

| Surface (operator-labelled) | `color()` | mean r/g/b | r% / g% / b% | `reflection()` |
|---|---|---|---|---|
| khaki + white paper | WHITE | 387 / 426 / 434 | 31 / 34 / 35 | ~85 |
| **red card** | RED | 761 / 264 / 341 | **55** / 20 / 25 | 89 |
| **blue card** | AZURE | 532 / **967 / 1015** | 21 / 38 / 40 | ~100 |
| **green card** | GREEN | 572 / **1024 / 1024** | 22 / 39 / 39 | ~100 |
| air / transition | UNKNOWN | ~50 each | ~neutral | 7 |

## Findings

### 1. `rgbi()` range is 0–1024 — closes KU-M20

The maximum channel value observed was exactly **1024**, on the shiny cards. So `rgbi()` returns
**0–1024 per channel** (r, g, b, and the 4th "intensity"), *not* 0–255. Every threshold we write is in
these units, and the finding is that channels **can and do hit the 1024 ceiling** — see § 3.

### 2. A dominant hue separates cleanly

Red was unmistakable: **55 % red fraction against a ~30 % neutral baseline**, reflection 89. The
built-in `color()` also called it RED correctly. **This validates the classification approach**: a
matte yellow note (high red + high green, low blue) has a dominant-channel signature and should
separate from the floor the same way. `reflection()` cleanly separates *surface present* (85–100) from
*air* (7).

### 3. ⚠ Saturation collapses discriminability — the specular problem, measured

The shiny blue and green cards drove **both the green and blue channels to the 1024 ceiling**. Once two
channels saturate, the ratios that carry colour information flatten out:

```
blue card :  r% 21  g% 38  b% 40      (g=967,  b=1015)
green card:  r% 22  g% 39  b% 39      (g=1024, b=1024)
```

**They are nearly identical, so blue and green were NOT separable here.** The cause is **gloss, not
hue** — a specular surface returns the sensor's own bright LED straight back and pins the channels at
maximum. This is precisely the mechanism behind the feared **blue-tape-vs-blue-sticky-note** confusion,
and behind the **silver duct tape** worry: a shiny surface saturates, and a saturated reading throws
away the very information needed to classify it.

**Consequences for the design:**
- **Detect saturation and treat it as its own signal.** A reading with any channel at/near 1024 is
  "specular", which is itself diagnostic (tape and laminate are glossy; matte paper is not) and must
  never be fed to a ratio-based classifier as if the ratio were meaningful.
- **`reflection()` + saturation-flag may separate what hue cannot** — the fusion idea from the team
  transcript. A glossy boundary (near-100 reflection, saturated) vs a matte note (high but
  unsaturated) may be separable even when their hues collide.
- **The real mines are matte**, so yellow-vs-floor is likely clean; the saturation risk is specific to
  glossy surfaces (the tape, the laminate). **Must re-measure with actual matte yellow notes and the
  real arena tape** before trusting any of this for the mission.
- **There is a working range, and it is narrow.** At **<1 cm** the glossy cards **saturated**; at the
  **mounted ~51 mm** the carpet **read as nothing**. Both extremes destroy information. LEGO's **16 mm**
  optimum sits between them, which is a second, independent reason to lower the sensors to ~16 mm
  ([../hardware/design-description.md](../hardware/design-description.md)). The height sweep that maps
  saturation-floor to signal-floor is still owed.

### 4. `color()` disagrees usefully with itself

The blue card read `AZURE`, the green `GREEN` — the built-in classifier used the pre-saturation
channel balance and still got close. But it offers no "saturated / don't trust me" flag, which is why
**our own classifier reading raw `rgbi()` plus a saturation check is worth having** over relying on
`color()` alone (scope FR-2b).

## What this does and does not close

- **Closes KU-M20** — `rgbi()` is 0–1024.
- **Advances GATE 1 method-side** — a dominant hue separates; gloss saturates; `reflection()` marks
  presence. The decision rule now has a shape: *classify by dominant-channel fraction, but bail to a
  specular/UNKNOWN branch when any channel saturates.*
- **Does NOT close the mission question.** Needs matte yellow notes, real blue painters tape, and real
  silver duct tape, at the corrected ~16 mm height. That is the real GATE 1.
- **Opens a range question:** the usable standoff is bounded below by saturation and above by signal
  loss. Map it with a height sweep once the sensors are at ~16 mm.

**Related:** [../plans/verification-plan.md](../plans/verification-plan.md) (GATE 1) ·
[../research/color-discrimination.md](../research/color-discrimination.md) ·
[../hardware/design-description.md](../hardware/design-description.md) (sensor height)

## Addendum — sensors re-mounted low, and they agree

**Later 2026-09-01:** the wheel geometry let the sensors be re-mounted **underneath the robot**, near
the ground (no longer ~51 mm at the front corners). A 30 s read at the new height, both sensors over
the same surface (a dark desk):

```
C:  rgbi 98 / 98 / 103   intensity 233   reflection 22   ratios 33 / 33 / 34
D:  rgbi 96 / 99 / 106   intensity 233   reflection 22   ratios 32 / 33 / 35
```

**The two sensors read the same surface identically** — within a couple of counts per channel. That
matters for the two-sensor design: a mine seen by *either* sensor must count, and boundary/floor
classification must agree between them, so a matched pair is a precondition. **Confirmed: C and D
agree.** (The surface here is a desk, not carpet or the arena floor — this is a sensor-agreement
check, not the arena baseline.) The mounted-low position also means colour and motor work can happen
in one session, removing the earlier either/or.

