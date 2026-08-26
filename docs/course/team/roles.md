# Team Roles, Permissions, and Prohibitions

> **Source:** `../source-material/Introduction Project Student Instructions.pdf`, p.1 ("Description of Roles").
> **VIOLATION OF THESE RULES RESULTS IN −2 SCHRUTE BUCKS PER VIOLATION** — the instructions' own
> capitalization. That comes out of the 100 SB budget that buys the robot.

Teams of four, one role each, identified by nametag colour. **If a team member is late or absent, you
may NOT change roles.** Exceptions (e.g. missing five days in a row due to illness) go through Dr. Watson.

---

## The four roles

| Role | Nametag | Name |
|---|---|---|
| **Builder** | 🔵 Blue | *TBD* |
| **Designer** | 🟡 Yellow | *TBD* |
| **Supplier** | 🟢 Green | *TBD* |
| **Programmer** | 🔴 Red | *TBD* — **[ASSUMED]** the operator of this repo, pending confirmation |
| **Scrum Master** | — | An AI copilot agent, provided by the course (separate instructions) |

> ⚠ **[ASSUMED, UNCONFIRMED]** — the operator's role is taken to be **Programmer**, inferred from their
> early notes (`../../archives/operator-notes/2026-08-25_spike-platform-notes.md`: "ok i need to program a lego spike") and from their instruction not to worry
> about physical design specifications. Recorded as an assumption in
> [../../scope.md § Assumptions](../../scope.md#assumptions). **Confirm this and fill in all four names.**
> Advice in this repo is addressed to the Programmer; if that is wrong, some of it is pointed at the
> wrong person and could cost 2 SB a time.

---

### Builder 🔵

| May | May NOT |
|---|---|
| Assemble the team's solution | Assemble anything the Designer has not planned |
| **Operate the robot — the ONLY person who may do so** | — |
| Return a design to the Designer and ask for changes when it will not work | Fix the design themselves |

> "The builder assembles your solution. The builder can only assemble what has been planned by the
> designer. If the design will not work, the builder must return the design to the designer and ask for
> changes. The builder is also your operator (the only one who can operate the robot)."

**Consequence for us:** on Demo Day the Builder presses the button. The Programmer does not. Any runbook
in `docs/runbooks/` that says "run the program" is an instruction **to the Builder**.

### Designer 🟡

| May | May NOT |
|---|---|
| Sketch and design the solution | **Touch the supplies** |
| Revise a design the Builder returns | Build it themselves |

> "The designer is responsible for sketching and designing your solution. The designer may not touch
> the supplies."

**Consequence for us:** the physical/mechanical design is the Designer's, and this repo *records* it
rather than authoring it ([../../scope.md § Boundaries](../../scope.md#boundaries)). Sensor mounting
height and angle materially affect the code, so that is a **request to the Designer**, in writing, not
something the Programmer decides alone.

### Supplier 🟢

| May | May NOT |
|---|---|
| **Handle the team's money — the ONLY person who may** | — |
| **Purchase supplies from the store — the ONLY person who may** | — |
| Put purchased supplies into the team's yellow plastic shoebox | **Touch the supplies again after that**, except to sell them back |
| Sell items back at **90% of listed price, rounded down** | — |
| **Stand within 5 feet of the store — the ONLY person who may** | — |
| Pay the team's meeting bills | — |

> "Only the Supplier may handle your team's money or purchase supplies. Once the supplies are purchased,
> the supplier must put them in your team's plastic shoebox. The Supplier cannot touch the supplies
> again, unless selling them back to the store… Only the supplier can stand within 5 feet of the store."

**Consequence for us:** every purchase is a written request to the Supplier. Sell-back at 90% rounded
down means a wrong purchase costs ~10% permanently, so **decide before buying** — e.g. sensor mounting
geometry before mounting blocks. `inventory.py` is the ledger; `sellback(price)` computes the rounding.
If a meeting bill cannot be paid, **materials must be returned to cover the difference** (p.2 item 7).

### Programmer 🔴

| May | May NOT |
|---|---|
| Write all the code | **Touch the supplies** — one exception below |
| **Plug the robot into / unplug it from their laptop** (the only permitted supply contact) | Build, mount, assemble, or adjust anything |
| — | Operate the robot (that is the Builder's) |

> "The programmer writes the code necessary for your solution. The programmer may not touch the supplies
> (with the exception of plugging or unplugging the robot into their laptop)."

**Consequence for us:** ⚠ **the plug/unplug exception is narrow.** Plugging in the USB cable is allowed.
Repositioning the colour sensor because it is 3 mm too high is **not** — that is a −2 SB violation. It
is also why [ADR-0002](../../decisions/0002-split-mission-logic-from-hub-io.md) matters: the Programmer
can develop and test `src/` on the Ubuntu host without touching hardware at all.

### Scrum Master (AI agent)

Course-provided; see the separate instructions. The one procedural duty named in the rules: **the Scrum
Master states "Meeting Adjourned"** to end a billed face-to-face meeting (p.2 item 5). Until that phrase
is said, the meter is running.

---

## Everyone

- **All supplies live in the team's yellow plastic box between classes.**
- **"You MAY NOT work on the project outside of class."** See
  [../../scope.md § Critical Notes](../../scope.md#critical-notes) — the operator's call to interpret,
  not this repo's.
- **Written digital communication is unlimited** and is a graded submission collected in full —
  [communications.md](./communications.md).
- **Face-to-face beyond the 5-minute standup costs money** — 1 SB per person per minute.

---

## How your teammates will grade you

Teammates should know the scoring formula **before** the project ends, not on 15 SEP. Full detail:
[../deliverables.md § Peer Evaluations](../deliverables.md#peer-evaluations--50-points--due-15-sep).

```
Participation + Attitude + (Contribution * 8) = Total Score
```

Instructions' worked example: `7 + 5 + (8*8) = 76`.

| Rule | |
|---|---|
| Evaluate **all** team members **including yourself** | Required |
| **No two people may have the same Total Score** | Required — you must rank everyone |
| Whole numbers only, each axis 1–10 | Required |
| Total the last column yourself using the formula | Required |
| Write specifics for anyone scored below a **75** total | Required |

> "Average score for an individual below 75 can at the professor's discretion reduce the student's
> overall grade." (p.3)

**Contribution carries 8× the weight of the other two axes.** Range is 10 (1+1+8) to 100 (10+10+80).
Because ties are forbidden and Contribution moves the total in jumps of 8, ties get broken with ±1 on
Participation or Attitude.

The definitions to score against — the instructions' own, not your own:

| Axis | Definition (p.3) |
|---|---|
| **Participation** | Attendance at meetings (in and outside class), punctuality, active participation in discussions and decisions, willingness to take on tasks. |
| **Contribution** | Actual completion of a "fair share" of tasks in a timely manner. |
| **Attitude** | Ability to work with the other team members in a positive and enjoyable manner. |

> "Please be OBJECTIVE. Do not let personal feelings (either good or bad) let you sway your evaluation
> of your team members." (p.3)

The **Mid-Project Check-in Survey** (1 SEP, 20 pts) also asks you to assess your peers — "who would you
fire", "whose roles would you switch", "who would you hire from another team and for how many Schrute
Bucks". Both assessments are much easier to write honestly and specifically if the journal already
records who did what, on which day.
