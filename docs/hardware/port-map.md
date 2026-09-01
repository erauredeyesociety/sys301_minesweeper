# Hub Port Map — SINGLE SOURCE OF TRUTH

> Status: **ASSIGNED AND CONFIRMED ON HARDWARE, 2026-09-01.** `device.id()` read on the hub, and the
> drive directions confirmed by watching the robot (`examples/drive_moves.py`). On 2026-08-27 all six
> ports read empty; parts were mounted since.
> Hub: LEGO Education SPIKE Prime Technic Large Hub 45601 `[ASSUMED — see ../scope.md § Assumptions]`,
> 6 LPF2 ports labelled **A–F**.

This file exists to satisfy scope requirement
**[TR-5](../scope.md#technical-tr): "Sensor/motor port assignments shall live in ONE place and be
referenced by the code, not scattered as literals."**

**The code reads this file's contents; it does not re-decide them.** When `src/` is written it
gets a single port-constants module transcribed from the table below, and that module is the only
place in the codebase where the letters A–F appear. If you find a bare `port.C` anywhere else,
that is the bug.

---

## Port assignments

| Port | Device | Purpose | Physically confirmed (date) |
|---|---|---|---|
| **A** | Motor (`device.id` 48) | **LEFT drive wheel.** Forward = NEGATIVE velocity (`LEFT_FWD = -1`). | 2026-09-01 (drive test) |
| **B** | Motor (`device.id` 48) | **RIGHT drive wheel.** Forward = POSITIVE velocity (`RIGHT_FWD = +1`). | 2026-09-01 (drive test) |
| **C** | Colour sensor (`device.id` 61) | Target/boundary detection. Mounted low, underneath. | 2026-09-01 |
| **D** | Colour sensor (`device.id` 61) | Second detector, straddling robot width. | 2026-09-01 |
| **E** | *empty* | — | 2026-09-01 (OSError) |
| **F** | *empty* | — | 2026-09-01 (OSError) |

**Drive convention, confirmed by watching the robot** (`examples/drive_moves.py`, encoder deltas
symmetric to ±1°): direct drive, 1 wheel rev = 360 encoder-deg. Forward drove left −366 / right +366;
turn-right pivoted clockwise. So a positive robot-forward command is `A: -v, B: +v`. **Motors are
mounted mirrored — this is the sign flip, and it is now MEASURED, not assumed.**

`Device` = the LEGO part and its part number (e.g. "Large Angular Motor 45602").
`Purpose` = what the mission code calls it (e.g. "left drive", "floor sensor", "front bumper").
`Physically confirmed` = the date a human watched this exact device respond on this exact port.
A blank in that last column means the row is a **plan, not a fact**, and the code must not rely on it.

---

## Parts owned — what can actually be plugged in today

Per `./inventory.py --verbose` (run it; do not trust a copy of it):

| Part | Qty owned | Takes a port? | Notes |
|---|---|---|---|
| Motor | 2 | **Yes — 2 ports** | **Both are Technic Medium Angular 45603** — answered by the operator 2026-08-27, closing KU-T3. ⚠ This row previously said the store offers *only* the **Large Angular 45602** and **Small Angular 45607** ([../scope.md RR-4](../scope.md#resource-rr)); that was already contradicted by `scope.md`, and the answer settles it — the Medium is available and is what we own. Confirm the part number against the motor casing when it is next handled, and record it in [build-record.md](./build-record.md). |
| Wheel | 2 | **No** | Wheels are mechanical, not electrical — they consume no port. Their **diameter** is nevertheless load-bearing for odometry; see [build-record.md](./build-record.md). |

That is 2 of 6 ports spoken for once the drive is assembled, leaving **4 free**.

## Sensor candidates — available to buy, none purchased or mounted

None of these is owned. They are the only sensors the course supplies
([../scope.md RR-3](../scope.md#resource-rr)). Specifications and the reasoning about which one does
what are in [../research/detection-and-sweep-techniques.md](../research/detection-and-sweep-techniques.md)
— cited, not recopied here.

| Sensor | Part no. | Likely role `[ASSUMED mission]` | Status |
|---|---|---|---|
| Color Sensor | 45605 | Downward floor sensor — target detection, plus **color classification** of the target ([../scope.md FR-2b](../scope.md#functional-fr)) | **Not purchased** |
| Distance Sensor | 45604 | Forward boundary / wall detection (ultrasonic, 50 mm blind zone) | **Not purchased** |
| Force Sensor | 45606 | Contact bumper / run-start button (8 mm total plunger travel) | **Not purchased** |

Built into the hub and needing **no port**: the 6-axis gyro/accelerometer, the 5x5 light matrix, the
speaker, and each motor's rotary encoder.

> The "likely role" column follows the working mission assumption (arena sweep + count floor targets,
> refined 2026-08-25 to also **discriminate targets by color**), which is **UNCONFIRMED** — [../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25). If the briefing
> says something else, these roles change before anything is bought.

---

## How to confirm a port assignment

**A row is recorded only after it has been physically observed. Never from a plan, a sketch, a build
instruction, or "that's where we always put it."** This is
[honest-instrumentation.md](../directives/honest-instrumentation.md) applied to the one table that
every line of hub code depends on.

The procedure:

1. Plug the device in. Note which lettered port on the hub it went into — **read the label on the
   hub**, do not infer it from cable routing or from which side of the robot the device is on.
2. Make the hub prove it — with a diagnostic script in [`scripts/`](../../scripts/) that queries the
   port and prints what it found, with a timeout, and never a blocking serial read
   ([../directives/automation-first.md](../directives/automation-first.md)).
   **Not with the LEGO SPIKE App or Web App.** Connecting a hub the app considers version-mismatched
   raises a "Hub update required" prompt that LEGO documents as non-dismissible — blacklist item 3 in
   [../scope.md](../scope.md#permanently-out-of-scope-blacklist--enforced-not-deferred), sourced in
   [../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md) — and it
   seizes the serial port. The app stays shut until the Hub OS generation has been identified from
   Linux ([../runbooks/hub-identification.md](../runbooks/hub-identification.md)).
3. For a **motor**, confirm direction too: command a small positive move and record which way the wheel
   actually turns. A motor mounted mirror-image runs backwards, and "left/right swapped" and
   "one motor inverted" look identical in a log but behave completely differently on the floor.
4. Fill in the row **and** the confirmation date. Add a changelog line below.
5. Tell the Programmer. A port change the code does not know about is the classic silent failure — the
   program runs, exits 0, and the robot does the wrong thing.

**If you cannot observe it, the row stays UNASSIGNED.** An unverified guess in this table is worse than
a blank, because a blank stops someone and a wrong entry does not.

---

## Changelog

Every change to the table above gets a line here — including a device being moved from one port to
another, or unplugged. Append; never rewrite history.

| Date | Change | Confirmed by | Code updated? |
|---|---|---|---|
| 2026-08-25 | File created. All six ports UNASSIGNED; nothing mounted. | — | n/a — no code exists |
| 2026-08-27 | **MEASURED on the hub over USB: all six ports A–F read EMPTY.** `device.id(port)` raised `OSError` on every port; `motor.status(port)` returned `5` on every port. Nothing was plugged in at the time. **No row changes** — the table already said UNASSIGNED and this confirms it rather than filling it. Two facts worth carrying forward: **`5` is what an unoccupied port returns** (which named `motor` constant equals 5 is unread — KU-M15), and **an `OSError` from `device.id()` means "empty plug", not "broken hub"** — do not let it read as a hardware failure on the day. [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md) | Probe over USB, operator present | n/a — nothing assigned to update |

`Code updated?` is not decoration. It is the checkbox that stops a port move from silently breaking a
program that still works perfectly on the old wiring.
