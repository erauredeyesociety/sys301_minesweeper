# Finding — Classroom conversation, relayed 2026-09-01: rules, economy, design ideas

**Provenance, read before quoting.** This is a **loose, second-hand** account: the professor spoke to a
teammate, the teammate recounted it (partly in their own ideas), and the operator relayed that to this
repo as an unpunctuated transcript. **Nobody in this repo heard the professor directly.** Everything is
tagged QUOTED-PROFESSOR (relayed as the professor's words), TEAMMATE-IDEA (a teammate's proposal, not a
rule), or AMBIGUOUS. **Do not promote a teammate idea to a requirement.** Confirm anything load-bearing
with the professor in writing.

The first relayed conversation (yellow mines, floor-tape boundary, autonomy contradiction) is filed in
[mission-answers-2026-08-27.md](./mission-answers-2026-08-27.md). This records the SECOND one.

## Competition rules and arena

| Item | Tag | What was said | Status / action |
|---|---|---|---|
| Grading is roughly **A or F** | QUOTED-PROFESSOR (relayed) | *"it's either you get an A or F pretty much"*, and *"I'm not sure if just passing grade, just make it work"* | Argues for a **robust, demonstrably-working** minimum over a fragile clever build. Shapes risk appetite; confirm the actual rubric (still owed as a professor question). |
| *"if the field was **12′ × 12′**"* | AMBIGUOUS | Spoken as a hypothetical ("if"), not a stated size | **Does NOT answer the units question (KU-P1).** Still the top blocker. Do not treat 12 ft as given. |
| Start **in a known corner** | AMBIGUOUS / teammate | *"starting in the corner, you know where the corner is"* | Enables dead-reckoning from a known pose — attractive but unconfirmed as a rule. Ask whether the start pose is fixed and known. |
| Mine count | TEAMMATE-IDEA | *"why would there be more than like 15"* | A guess, not a stated count. Do not hard-code. |
| A sticky note **near the boundary** | QUOTED-PROFESSOR (relayed) | *"he could put a sticky note on the boundary… it won't be touching the boundary, but he could have a very thin line in between"* | Mines may sit close to the tape → detection must separate a mine from the boundary even when adjacent. Feeds the boundary/detection design. |
| Sticky notes were **in the box** | QUOTED-PROFESSOR (relayed) | *"the sticky notes that could be on the field most likely"* | The pack in the kit is representative — use it for the real GATE 1. |

## The class economy and sourcing (new — not previously documented)

| Item | Tag | What was said | Implication |
|---|---|---|---|
| **Contract roles from other teams** | QUOTED-PROFESSOR (relayed) | *"you can contract out roles from other companies"* | Teams can hire labour/roles from other teams for Schrute Bucks. We may sell our programming/design services — which means targeting **other hubs** (different device_uuid/MAC), reinforcing the identity-of-record rule in [../scope.md](../scope.md). Captured also in [../plans/competitive-interference.md](../plans/competitive-interference.md). |
| **No frame needed** | TEAMMATE-IDEA | *"we don't need a frame, you can attach to the hub itself, don't need to be overspending money"* | Build directly on the hub; do not spend SB on structural bricks. A cost/build decision for the Builder — matches the "deliberately simple" design doctrine. |
| **Sell-back at 90 %** | QUOTED-PROFESSOR (relayed) | *"you can sell it for 90%"* | Consistent with [../plans/purchasing-strategy.md](../plans/purchasing-strategy.md): reversing a purchase costs ~`ceil(P/10)` SB. Buying cheap parts on sight stays low-risk. |
| Parts scarcity between teams | QUOTED-PROFESSOR (relayed) | *"his team didn't have any, he broke [one]"* | Parts are finite across the class; a broken/again-needed part may be unavailable. Argues for not depending on a spare we do not hold. |

## Robot design ideas (teammates' — assess on merit, none is a requirement)

- **Lawnmower sweep with a pivot-turn**, loop condition *"absolute value of travel is less than target
  degrees"* — matches the boustrophedon design already in
  [../plans/competition-program-design.md](../plans/competition-program-design.md). Adopt.
- **Start-in-corner + dead-reckoning** rather than finding the boundary by colour: *"I'm relying solely
  on the distance of the map."* Removes a hard sensing problem but bets everything on odometry accuracy
  — and wheel diameter/track width are unmeasured. Assess in the odometry/coverage research; adopt only
  with a re-localization fallback.
- **Fuse a colour event with odometry POSITION**: *"a change in colour but it's at this distance… so
  it's probably a boundary."* Genuinely strong — it disambiguates the blue-tape-vs-blue-note collision
  using *where* the robot is, not just hue. Feeds the colour-fusion research.
- **Width as a discriminator**: *"how wide the tape is versus how wide the sticky notes are."* A strip
  crossed at known speed has a width in time — ties to the event-width gates already in
  [`src/detector.py`](../../src/detector.py). Adopt as a second, hue-independent signal.
- **Port-swap field variants**: *"plug the motors into 3 and 4… runs an entirely different format… you
  never even deployed."* A program that branches on which ports are occupied (`device.id` per port,
  already readable) to select a field variant with no re-deploy. Clever for demo day; adds failure
  modes — hold as an option, not a commitment.
- **Stream over Bluetooth and "call it out" / build a map** — the untethered-telemetry path under
  active research ([telemetry-while-driving research](../research/), launched 2026-09-01).

## New questions for the professor (added to the list)

- The actual grading rubric (is it truly pass/fail, or scored?).
- Is the start pose fixed and known (a specific corner, a heading)?
- Can a mine be placed directly adjacent to the boundary tape, and how close?
- Confirm the parts-contracting economy rules (can we sell services, at what rate).

**Related:** [mission-answers-2026-08-27.md](./mission-answers-2026-08-27.md) ·
[../plans/competitive-interference.md](../plans/competitive-interference.md) ·
[../plans/questions-for-the-professor.md](../plans/questions-for-the-professor.md)
