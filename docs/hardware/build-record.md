# Build Record — the robot as actually built

> Status: **EMPTY SKELETON — 2026-08-25.** Nothing has been built. Every field below is a prompt for
> the operator to answer by describing the real robot. **`<<< ... >>>` marks an unfilled placeholder.**
>
> ⚠ **Nothing in this file may be filled in from a plan, a guess, or a LEGO reference build.** It
> records what the Builder actually assembled. If a field is unknown, leave the placeholder in place —
> a blank is honest, an invented number is a bug you will chase on Demo Day
> ([../directives/honest-instrumentation.md](../directives/honest-instrumentation.md)).

**This is a record, not a design.** The Designer designs and the Builder builds; we write down the
result. Do not use this file to propose a chassis. See [INDEX.md](./INDEX.md).

**Port assignments do not live here** — they live in [port-map.md](./port-map.md), which is the single
source of truth. Reference it; do not restate it.

---

## 1. Identity and date

| Field | Value |
|---|---|
| Build name / revision | `<<< e.g. "Rev A — first driving chassis" >>>` |
| Date assembled | `<<< YYYY-MM-DD, class session >>>` |
| Built by (Builder) | `<<< name >>>` |
| Designed by (Designer) | `<<< name >>>` |
| Superseded by | `<<< leave blank until a rebuild >>>` |

> A rebuild that changes geometry gets a **new revision row and a changelog entry**, because it
> invalidates every measured number below it.

## 2. Drive configuration

| Field | Value |
|---|---|
| Drive type | `<<< differential (two driven wheels + caster/skid) / tank / other >>>` |
| Number of driven wheels | `<<< n >>>` |
| Motor variant used | `<<< Large Angular 45602 / Small Angular 45607 — the only two the store offers (scope RR-4); read the number moulded on the motor >>>` |
| Gearing between motor and wheel | `<<< direct drive, or the gear ratio, e.g. 1:1.67 (20t → 12t) >>>` |
| Third point of contact | `<<< caster wheel / skid / ball bearing / none >>>` |
| Which motor is left, which is right | `<<< as observed from behind the robot facing forward >>>` |
| Motor direction convention | `<<< does a positive command drive the robot FORWARD on each side? observed, not assumed >>>` |

**Why this matters:** direct drive vs geared changes the conversion from encoder degrees to millimetres
travelled, and a mirror-mounted motor needs its sign inverted in `src/`. Both are observations,
not preferences.

## 3. Wheel and chassis geometry — needed for odometry

| Field | Value | How obtained |
|---|---|---|
| Wheel diameter | `<<< mm >>>` | `<<< measured with calipers / printed on the tyre sidewall / LEGO part spec >>>` |
| Wheel width | `<<< mm >>>` | `<<< >>>` |
| Track width (centre-to-centre of the two driven wheels) | `<<< mm >>>` | `<<< measured >>>` |
| Wheelbase (drive axle to caster) | `<<< mm >>>` | `<<< measured >>>` |
| Overall footprint (L x W) | `<<< mm x mm >>>` | `<<< measured >>>` |
| Mass with hub and battery | `<<< g, or NOT MEASURED >>>` | `<<< >>>` |

**Why these two numbers specifically.** Any odometry math the mission logic does depends on exactly
them:

- **Wheel diameter** converts encoder degrees to distance: `distance = π × D × (degrees / 360)`.
  A 10 % error in `D` is a 10 % error in every straight-line distance, and it compounds over a sweep.
- **Track width** converts a turn into wheel travel: an in-place turn of `θ` moves each wheel
  `π × track × (θ / 360)`. Get it wrong and every lane change ends off-heading.

LEGO tyres are compliant, so the **rolling** diameter under load is smaller than the moulded diameter.
If lane spacing drifts during a sweep, the honest fix is to **measure an effective wheel diameter** —
drive a commanded 2000 mm, measure what the robot actually travelled, and back the number out — then
record it here as a measurement with its date and floor surface. Do not tune a magic constant in code
([../directives/code-discipline.md](../directives/code-discipline.md)).

Record the surface the geometry was calibrated on; carpet and tile do not give the same answer.

| Field | Value | Conditions |
|---|---|---|
| Effective (rolling) wheel diameter | `<<< mm >>>` | on `<<< surface >>>`, `<<< date >>>`, from a `<<< n >>>` mm test drive |

## 4. Sensor mounting

Fill one block per sensor mounted. **None are purchased as of 2026-08-25.**

### Sensor 1

| Field | Value |
|---|---|
| Sensor and part number | `<<< e.g. Color Sensor 45605 >>>` |
| Hub port | `<<< see port-map.md — record it THERE, cross-reference here >>>` |
| Position on chassis | `<<< e.g. "on centreline, 40 mm ahead of the drive axle" >>>` |
| Height above floor (sensing face to floor) | `<<< mm, MEASURED with the robot standing on the arena surface >>>` |
| Angle | `<<< e.g. "perpendicular, facing straight down" / "forward, 0° from horizontal" >>>` |
| Mounting rigidity | `<<< braced / cantilevered — a sensor that bounces changes its own reading >>>` |
| Ambient-light shroud fitted? | `<<< yes/no; describe >>>` |

**Colour-sensor height reference.** LEGO's technical specification for the Color Sensor 45605 gives an
**optimal reading distance of 16 mm**, qualified as "depending on object size, color, and surface".
That figure is quoted from the official LEGO Education techspecs PDF in
[../research/detection-and-sweep-techniques.md](../research/detection-and-sweep-techniques.md), which
links the PDF directly. Nobody re-read the source PDF while writing *this* file, so treat 16 mm here as
**taken from that research note, not independently re-verified**. The same note records that LEGO's own
Advanced Driving Base mounts the sensor at about 8 mm, which Prime Lessons reports as reading black
incorrectly in colour mode. **Copying a reference build's sensor height is not evidence that the height
is right.** Mounting geometry for *color discrimination* specifically (a harder problem than presence
detection, scope FR-2b) is to be worked through in `docs/research/color-discrimination.md` — **not
written as of 2026-08-25**; until it exists, the colour material in the detection note above is all we
have.

Two consequences for this record:

- **Our robot's actual sensor height is UNVERIFIED until someone measures it** with the robot standing
  on the arena floor. Write the measured number above, not 16.
- On carpet, pile height is part of the gap and it changes as the robot rolls. Record the **surface**
  the height was measured on.

### Sensor 2

`<<< duplicate the block above, or delete if only one sensor is mounted >>>`

## 5. Hub mounting

| Field | Value |
|---|---|
| Hub orientation | `<<< which face is up; which end is "forward" >>>` |
| Is the hub level when the robot is on the floor? | `<<< yes/no — the gyro's yaw reading assumes it is >>>` |
| Light matrix readable during a run? | `<<< yes/no — it is our only laptop-free status display (FR-4) >>>` |
| Battery / power | `<<< rechargeable pack / AA batteries; charge state routine >>>` |
| Cable routing notes | `<<< anything that can snag a wheel or get yanked on plug-in >>>` |

Hub orientation is not cosmetic: it determines which gyro axis is yaw, and mounting it on its side
silently changes what `motion_sensor.tilt_angles()` means.

## 6. What was tried and rejected

Short notes. This is the cheapest source of Intro Report content in the whole repo — a design that was
built, failed, and was changed is a **results** paragraph, and it is unrecoverable from memory in
three weeks.

| Date | What was tried | What happened | What we changed |
|---|---|---|---|
| `<<< >>>` | `<<< >>>` | `<<< >>>` | `<<< >>>` |

## 7. Photos

Put images in **`docs/hardware/photos/`** (create it when the first photo exists) and link them from
the relevant section above. Name by concept and revision, not by camera filename:
`rev-a-side-view.jpg`, `rev-a-sensor-height.jpg`, `rev-b-drive-train.jpg`.

Worth photographing, because these are the ones you will wish you had:

- Side view showing the **sensor height above the floor**, ideally with a ruler in frame.
- Top view showing the **wheel track** and where the sensor sits relative to the drive axle.
- The **hub face**, so the port map is checkable against a picture rather than memory.
- The robot **on the actual arena floor**, which documents the surface for the report.

The report needs embedded figures (CSER template). A photo taken in class costs nothing; a photo not
taken cannot be retaken after the parts go back in the yellow box.

---

## Changelog

| Date | Change | By |
|---|---|---|
| 2026-08-25 | Skeleton created. No build exists; every field is a placeholder. | Claude |
