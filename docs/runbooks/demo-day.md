# Runbook — Demo Day (10 SEP 2026) and every dry run before it

> **Audience: the BUILDER.** You are the **only** person permitted to operate the robot
> (course instructions p.1; violations cost 2 Schrute Bucks each). Read this once now, and once at the
> start of class on 10 SEP. Under pressure you follow the checklist — you do not improvise.
>
> **Status:** written 2026-08-25. The mission and the arena are still **PENDING**
> ([../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25)), so every step that depends on them is marked
> **`PENDING`** and must be filled in before the first dry run. The hub's light/sound vocabulary in § 5
> is **`PROPOSED`** — it is not implemented yet.
>
> Related: [hub-identification.md](./hub-identification.md) ·
> [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md) ·
> [../directives/hardware-safety.md](../directives/hardware-safety.md)

---

## 0. Who may touch what, at the table

| Person | May | May **not** |
|---|---|---|
| **Builder** (blue) | Operate the robot. Assemble exactly what the Designer planned. | Redesign it on the spot |
| **Programmer** (red) | Plug the robot into their laptop and unplug it. Nothing else. | Touch any other supply |
| **Designer** (yellow) | Sketch, direct, observe | Touch supplies |
| **Supplier** (green) | Handle money; buy/sell at the store; load the yellow box | Touch supplies once boxed, except to sell back |

If the robot needs a part change mid-demo, **the Builder does it** — nobody hands you a piece.

---

## 1. The calendar problem — read this first

The class rule is **"You MAY NOT work on the project outside of class,"** and supplies live in the
yellow box between classes. That means:

- There is **no meaningful "night before" hardware check.** The robot will be in the box.
- **The real readiness check is at the END of class on 8 SEP** — the last class before Demo Day. Do it
  as a pack-out ritual (§ 2), because whatever state you box on 8 SEP is the state you unbox on 10 SEP.
- The night before is **paper only**: re-read this runbook and § 6 (the failure drill) until you can
  recite the five actions. **`[ASSUMED — operator's ruling pending]`** that re-reading a procedure is not
  "working on the project". That rule is the operator's to interpret with the instructor
  ([../scope.md § Critical Notes](../scope.md#critical-notes)) and this runbook does not decide it; if the
  ruling goes the other way, this bullet goes.
- **`PENDING — operator question`:** may the hub be **charged** between classes, and by whom? Charging
  is arguably handling a supply, which the Builder may do and the Programmer may not. Get a ruling from
  Dr. Watson or the TA in **writing** (written comms are unlimited, and the record is submitted).

Class days remaining before the demo, as of 2026-08-25: **27 AUG · 1 SEP · 3 SEP · 8 SEP**
(six class days total — [../course/deliverables.md](../course/deliverables.md) § Calendar).
Every one of them ends with § 2.

---

## 2. Pack-out check — end of every class, and above all 8 SEP

| # | Check | Pass looks like |
|---|---|---|
| 2.1 | **Battery.** Hub charged as far as the class allows. | Reading recorded, not guessed. Read it from the hub, not from the app — see the battery probe in [hub-identification.md § 5.7](./hub-identification.md). **`UNVERIFIED`:** which call returns battery on this hub. **`PENDING`:** what "enough charge for a run" is in volts/percent — measure it during dry runs and write the number here. |
| 2.2 | **The program is on the hub, in a known slot.** | Slot number written on a card that goes in the yellow box. **`PENDING`:** the slot number. |
| 2.3 | **The program runs standalone, laptop unplugged.** | You unplug the USB, press run on the hub, and it starts. If it only runs tethered, it will fail on Demo Day. This is requirement TR-3. |
| 2.4 | **Port map matches the physical build.** | Every cable seated, and each one matches [../hardware/port-map.md](../hardware/port-map.md) exactly. Photograph the ports; a photo settles arguments a memory cannot. |
| 2.5 | **Nothing loose.** | Gentle shake, nothing rattles or shifts. Sensor mounting height unchanged — detection thresholds depend on it. |
| 2.6 | **Box contents.** | Robot · USB cable · spare cable if the budget bought one · slot card · the last calibration numbers |

**Do not open the LEGO SPIKE App or Web App to do any of this** unless the operator has explicitly
approved it, and if it prompts to update the Hub OS, **STOP**
([../directives/hardware-safety.md](../directives/hardware-safety.md)).

---

## 3. Start of class, 10 SEP — readiness check

Fifteen minutes, in this order. Anything that fails goes to the Programmer immediately, in writing.

| # | Check | Pass |
|---|---|---|
| 3.1 | Unbox; visual inspection against the 2.4 photo | Build identical to pack-out |
| 3.2 | Power on | Hub boots; no error pattern on the matrix |
| 3.3 | Battery | At or above the threshold from 2.1. If low, charge now and say so in the team channel. |
| 3.4 | Correct slot selected | Slot from the card in 2.2 |
| 3.5 | **Dry start, robot held off the floor or on a safe patch** | Program starts, reaches the calibrate/ready state, then you stop it. Confirms the program is alive **before** you are on the clock. |
| 3.6 | Laptop **disconnected and put away** | The run must not depend on a cable, and a dangling cable is the classic way a robot gets yanked mid-run |
| 3.7 | Failure drill (§ 6) read aloud once | You can name all five actions without looking |

---

## 4. Calibrate on the arena floor, immediately before the run

**Do not skip this. It is the single most likely cause of a failed demo.**

The detection threshold is not a property of the robot; it is a property of **this floor, under these
lights, at this sensor height, right now**. Requirement TR-4 says thresholds are calibrated at run
start, not hard-coded, precisely so that a different room does not require a code edit. A threshold
carried over from a dry run on a different surface will read a target as floor, or floor as a target,
and the count will be wrong in a way that looks like a logic bug and is not.

Things that change between your dry run and the demo, all of them silently: the arena moved to another
part of the room · overhead lights vs. window light vs. an afternoon slot · a shadow from spectators
standing around the arena · carpet vs. tile vs. poster board · the sensor sitting 2 mm lower after a
knock.

| # | Step | Record |
|---|---|---|
| 4.1 | Place the robot on the arena floor, on **bare floor** with no target under the sensor | — |
| 4.2 | Run the calibration step | Floor reading, in the sensor's units (reflected light %), plus spread over several samples |
| 4.3 | Place a target under the sensor as it will actually lie in the arena | Target reading, same units, same spread |
| 4.4 | Confirm the two do not overlap | Gap between the two bands. If they overlap, the run will miscount — tell the Programmer **before** running, not after |
| 4.5 | Write both numbers down **now**, with the floor surface and the lighting | Goes straight into § 7 and into `docs/findings/` |

**`PENDING` — color.** [../scope.md](../scope.md) FR-2b requires a target to be classified by **color**,
so 4.2–4.4 are not one floor band against one target band: they are the floor band plus **one band per
color in play**, and any two bands that overlap name a color this robot cannot call today. Sample every
color the briefing puts in the arena, in the arena's own light, and keep an UNKNOWN bucket for readings
that fit no band — FR-2b requires reporting those rather than forcing them into a class.

**`PENDING`:** what the calibration routine actually is, how it is triggered, and how many samples it
takes — the mission code does not exist yet. **`PENDING`:** the target's physical form (the working
assumption is sticky notes, unconfirmed). **`PENDING`:** whether you are allowed to place a sample
target on the arena floor before the run — ask, in writing.

---

## 5. Run procedure

| # | Action | Expected |
|---|---|---|
| 5.1 | Announce to the instructor that you are starting | — |
| 5.2 | Place the robot at the start position and orientation | **`PENDING`** — the start position is defined by the briefing. Whatever it is, use the **same** one you calibrated at, and the same one you used in dry runs. |
| 5.3 | Hands clear, then press run | Robot enters CALIBRATING (§ 5 vocabulary) |
| 5.4 | **Do not touch anything.** Watch the matrix and listen to the beeps. | One beep per counted target — keep your own tally out loud or on paper |
| 5.5 | Robot signals DONE and stops | Final count displayed on the matrix |
| 5.6 | Read the count aloud and let the instructor confirm | — |
| 5.7 | Pick the robot up **only after** it has stopped | — |
| 5.8 | Fill in § 7 **immediately**, before the next team's turn | — |

**`PENDING`:** time limit, number of attempts allowed, and whether operator intervention is permitted
mid-run — all come from the briefing. Ask before Demo Day; the failure drill in § 6 depends on them.

### The hub's state display — `PROPOSED, NOT YET IMPLEMENTED`

The point of this is that a failure is **diagnosable from across the room with no laptop**
([../directives/honest-instrumentation.md](../directives/honest-instrumentation.md)). The hub has a 5×5
light matrix and a speaker; both are free instrumentation. This is a proposal for the Programmer to
implement, and this table must be re-checked against the actual program before the first dry run.

| Stage | Matrix | Sound | Means |
|---|---|---|---|
| BOOT / IDLE | Hub default | — | Program not started |
| SELF-CHECK | Single centre pixel | — | Program started, ports being checked |
| CALIBRATING | Blinking border | Rising two-tone | Sampling floor and target — **do not move the robot** |
| READY | Solid square outline | One short beep | Calibrated, waiting to move |
| SWEEPING | Arrow in the direction of travel | — | Normal running |
| TARGET COUNTED | Whole matrix flashes once | **One short beep per target** | Increment. Your audible tally must match the final number. |
| TURN / BOUNDARY | Arrow rotates | — | Executing a planned turn, not lost |
| DONE | The count, as digits | One long tone | Run complete, motors stopped |
| FAULT | **X** pattern | Descending tone | Something the program itself detected — see § 6 |

The per-target beep matters: it gives you a tally that is **independent** of the number the robot
prints. If they disagree, that is a real finding and it belongs in the report.

**DONE owes more than one number.** [../scope.md](../scope.md) FR-4 asks for **per-color counts, a total,
and the count of unclassified readings**, and a 5×5 matrix shows one of those at a time. The order DONE
steps through them is **`PENDING`** on the Programmer — agree it in writing before the first dry run, or
the Builder will read the wrong number aloud to the instructor.

---

## 6. FAILURE DRILL — decided now, not in the moment

Five atomic actions. Memorise these; the table below maps each symptom to **exactly one** of them.

| ID | Action |
|---|---|
| **A1 STOP** | Press the hub's centre button **once** to stop the running program |
| **A2 RESTART** | Press the centre button **once** to re-launch the selected slot |
| **A3 HANDS OFF** | Do nothing. Let the run finish. Watch and remember. |
| **A4 POWER CYCLE** | Hold the centre button to power off, press again to power on, reselect the slot. **`UNVERIFIED`:** the exact hold duration — measure it on a dry run and write it here. |
| **A5 CALL IT** | Announce to the instructor that the attempt is over, and record what happened |

**`UNVERIFIED` — every button behaviour above.** The hub has never been connected
([hub-identification.md](./hub-identification.md)): single-press-stops, single-press-relaunches-the-slot,
and hold-to-power-off are the expected stock-firmware behaviours, not observed ones. Confirm all three on
the first dry run and rewrite this table with what the hub actually did.

| Observable symptom | Action | Why this one |
|---|---|---|
| Robot **drifts** off heading but is still inside the arena and still counting | **A3 HANDS OFF** | Drift is data. Chasing it guarantees a bad run; letting it finish gives you a real coverage measurement to tune from. Note where the drift started. |
| Robot **leaves the arena** (crosses the boundary) | **A1 STOP** | It is out of the mission. Stop it before it hits something. Do not carry it back and resume — the run is over; record it and ask the instructor whether a re-run is allowed. |
| **Count is obviously wrong** while running (beeps in empty floor, or silence over an obvious target) | **A3 HANDS OFF** | Let it finish and record the wrong number honestly. Mid-run correction is not possible and not permitted. A wrong number with the conditions written down is a results section; an aborted run is nothing. |
| Robot **does not start** — no self-check, no calibration, within ~3 s of pressing run | **A2 RESTART** | Once. If the second press also does nothing, then **A4 POWER CYCLE**, and if that fails, **A5 CALL IT**. |
| **Hub disconnects / powers off** mid-run (matrix goes dark) | **A4 POWER CYCLE** | Almost always battery or a knocked-loose cable. Power cycle, check the ports against the port map, then restart the attempt from § 4 — **re-calibrate**, do not resume. |
| **FAULT** display (X pattern, descending tone) | **A1 STOP** | The program caught its own problem. Read the matrix, write down exactly what it showed, hand it to the Programmer. |
| Robot is about to hit a person, a wall, or another team's equipment | **A1 STOP** | Safety outranks the demo, every time |

**Never** grab a moving robot. **Never** improvise a sixth action. **Never** let anyone but you touch it.

---

## 7. Record it immediately — this is the report's results section

Fill this in **on the spot**, before you pack up. Ten minutes later you will remember the number and
none of the conditions, and the conditions are what make the number mean anything
([../directives/documentation-discipline.md](../directives/documentation-discipline.md)). File it in
**`docs/findings/`** and add a row to [../findings/INDEX.md](../findings/INDEX.md).

```text
RUN RECORD
Date / time:              ____________________  Run #: ____  [ ] dry run  [ ] DEMO
Builder (operator):       ____________________  Witnessed by: ____________________

CONDITIONS
Arena surface:            ____________________  (carpet / tile / poster board / other)
Lighting:                 ____________________  (overhead fluorescent / window / mixed; time of day)
Start position + heading: ____________________
Battery at start:         ____________________  (units!)
Targets placed by:        ____________________  Target type: ____________________

CALIBRATION (from § 4, in sensor units — say which)
Floor reading:            ______ ± ______      Target reading: ______ ± ______
Threshold used:           ______              Bands overlap?  [ ] no  [ ] YES
Per-color bands (§ 4):    ____________________________________________

RESULT
Observed count (robot):   ______              Your beep tally: ______
Observed per color:       ____________________________________________
Unclassified / UNKNOWN readings reported:     ______
TRUE count (ground truth): ______             Counted by: ____________________
TRUE per color:           ____________________________________________
Run duration:             ______ s            Completed on its own?  [ ] yes  [ ] no
Coverage: did it visit the whole arena?  [ ] yes  [ ] no — where not: ______________

WHAT HAPPENED
Failure drill actions taken (A1–A5, in order):  ____________________
Anything surprising, verbatim:  ____________________________________________
Matrix/sound at the moment it went wrong:  ____________________________________
Next change to try:  _______________________________________________________
```

**Rules for this block:** an unobserved field is left blank or `UNKNOWN` — never filled from memory or
inference. If observed count and true count differ, **write both**; the disagreement is the most
valuable line in the whole document.

---

## 8. Everything on this page that is still PENDING

| Item | Blocked on |
|---|---|
| Start position, arena dimensions, boundary type | The instructor's briefing |
| Target type and how targets are placed | The briefing |
| Time limit, attempts allowed, whether intervention is permitted | The briefing |
| Whether the deliverable is a count, a map, a retrieval, or avoidance | The briefing |
| Program slot number; what the calibration routine does | Mission code, not yet written |
| Per-color calibration bands (§ 4) and the order DONE displays per-color counts, total, unclassified (§ 5) | Briefing (which colors) + Programmer (FR-2b / FR-4 implementation) |
| Battery threshold in real units; **all** hub button behaviours in § 6, including the power-off hold time | Observation on the first hub session / dry run |
| Whether the hub may be charged between classes, and by whom | Written ruling from Dr. Watson / the TA |
| § 5 light-and-sound vocabulary | Programmer implements it, then this table is verified against the code |

**Sources:** course instructions (`../course/source-material/Introduction Project Student Instructions.pdf`, pp. 1–2) ·
[../scope.md](../scope.md) · [../roadmap.md](../roadmap.md) M3 ·
[../directives/honest-instrumentation.md](../directives/honest-instrumentation.md).
