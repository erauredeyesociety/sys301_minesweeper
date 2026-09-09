# Journal reconstruction — evidence audit and what only the operator can answer

**Written 2026-09-09. Not an entry, not a submission — the working notes behind the six draft entries
in this folder.**

> ## ⚠ These are DRAFTS, reconstructed from the repository's dated record.
>
> They were assembled by an assistant that **was not in the room on any class day**. They exist for
> the operator to **review, correct, and own**. Every sentence in every draft cites the file it came
> from. Nothing was inferred about people, attendance, effort, or feeling, because the repo records
> artifacts and never records people.
>
> **Any day marked NO EVIDENCE below needs the operator's memory, not invention.**

---

## 1. How many entries are owed: six, and the source document says so

This is settled by the instructions, not inferred from convenience:

- *"You will spend the last 5-7 minutes each day independently writing a reflection… Each day there
  will be a posted question of the day (QOD) on the board (**in class**)."*
  (`../source-material/Introduction Project Student Instructions.txt`)
- The instructions' own calendar names six project dates: **25 AUG · 27 AUG · 1 SEP · 3 SEP · 8 SEP ·
  10 SEP** — all Tuesdays and Thursdays.

So writing happens in class, on a day there is a class, against a prompt posted in the room. **Six
entries. No entry is owed for any other calendar date**, and none of the evidence-free dates below
costs a point.

> ⚠ **Flagged, not assumed:** the instructions never use the literal phrase "class day" and never
> state an entry count. "Six" is derived from the calendar plus the in-class QOD rule. The repo
> already relies on that reading ([../deliverables.md](../deliverables.md) § Calendar,
> [INDEX.md](./INDEX.md) § Entry tracker). Separately unresolved: the Canvas assignment page header
> says "Ungraded, 50 Possible Points" while its own rubric sums to 80.

---

## 2. The calendar, day by day — what the repo actually proves

| Date | Class day? | Evidence in the repo | Draft |
|---|---|---|---|
| **2026-08-25** Tue | **YES** | **Rich.** Session record, three budget rows, the verbal briefing, three ADRs, the whole docs scaffold, three dated plans | [2026-08-25.md](./2026-08-25.md) |
| 2026-08-26 Wed | no | Rich — two session records, `src/` written, ADR-0004/0005/0006, four lessons. **Not a class day; it must not be reported as one** | — |
| **2026-08-27** Thu | **YES** | **Rich.** Session record, four findings, the firmware-integrity proof, raw run captures, three commits | [2026-08-27.md](./2026-08-27.md) |
| 2026-08-28 Fri | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| 2026-08-29 Sat | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| 2026-08-30 Sun | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| 2026-08-31 Mon | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| **2026-09-01** Tue | **YES** | **Rich.** Session record, four findings, five raw run captures, three commits | [2026-09-01.md](./2026-09-01.md) |
| 2026-09-02 Wed | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| **2026-09-03** Thu | **YES** | **Rich, plus the first real telemetry.** Session record, seven findings, one commit, `#end reason=complete rows=238` | [2026-09-03.md](./2026-09-03.md) |
| 2026-09-04 Fri | no | **THIN.** One commit that writes up the previous class day, and a single status line in a runbook. No session record, no telemetry, no hardware | — |
| 2026-09-05 Sat | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| 2026-09-06 Sun | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| 2026-09-07 Mon | no | **NO EVIDENCE IN THE REPOSITORY — operator to complete or confirm no work occurred.** | — |
| **2026-09-08** Tue | **YES** | **The richest day in the project.** Session record, four findings, eight dated plans, GATE 1 telemetry, the surface survey | [2026-09-08.md](./2026-09-08.md) |
| 2026-09-09 Wed | no | Rich — one commit and three new documents. **Not a class day** | — |
| **2026-09-10** Thu | **YES — DEMO DAY** | **In the future. Nothing can be drafted.** | [2026-09-10.md](./2026-09-10.md) (form only) |

**Five past class days have evidence. One class day is in the future. Eight calendar dates have no
evidence at all, and none of them is a class day, so none of them costs a point.**

Method, so it can be re-run: a search for each date string across every `.md` under `docs/`, plus
`git log --date=short`, plus the timestamps on `tmp/telemetry/`. The eight dates above return nothing
on all three.

---

## 3. ⚠ Three blockers on the drafts, in priority order

### Blocker 1 — the handwritten pages, not these files, are the submission

[INDEX.md](./INDEX.md) is explicit: *"The graded artifact is a handwritten page, written in class, on
the provided form"* and *"Writing the markdown file does not earn a single point."* **So the first
question is not what these drafts say — it is whether the five handwritten pages exist.** If they do,
these drafts are transcription support. If they do not, the operator needs to know whether late or
reconstructed pages are accepted at all before spending any more effort here.

### Blocker 2 — not one Question of the Day is recorded anywhere

The QOD is its own **20-point** rubric criterion ("entries clearly answer the question asked"). A
search for "QOD" across `docs/` returns only rules, templates and directives that *say to record it* —
**never a recorded question**, for any of the five past class days. Half of every entry's scoring
surface therefore cannot be drafted from this repo, by anyone. If the questions are lost, that fact
should change how the remaining effort is spent.

### Blocker 3 — the repo contains zero human names and no attendance record

All four names are `*TBD*` in [../team/roles.md](../team/roles.md), and the operator's own role is
flagged `[ASSUMED, UNCONFIRMED]` Programmer. There is no record of who was present on any date, who
did what, or how anyone felt. The rubric's own prompts — *"What frustrated you?"*, *"How did your
teammates do?"* — are unwritable from here. The one exception is *"decided by the team 2026-08-25"*
(differential drive), which is repo-supported but names nobody, and must stay phrased that way.

There is also a fourth-row ambiguity worth resolving: `roles.md` lists a **fifth** row, Scrum Master,
as *"An AI copilot agent, provided by the course"*. Whether "your teammates" means three other humans
needs the operator's confirmation before the peer evaluations, not after.

---

## 4. Questions the operator must answer

1. **Do the five handwritten pages already exist** for 25 AUG, 27 AUG, 1 SEP, 3 SEP and 8 SEP? If not,
   are late or reconstructed pages accepted? *(Outranks everything else on this page.)*
2. **What were the five Questions of the Day?** Notebook, phone photo, or lost?
3. **What is your name, and are you in fact the Programmer?**
4. **Who are the other three teammates by name**, and is the Scrum Master a human or the AI agent?
5. **Were you present in class** on each of the five past class days?
6. **What actually happened in the room** on each of those days? Even one line each turns five
   unsourceable halves into draftable ones.
7. **Was the Mid-Project Check-in Survey (20 points, on or around 1 SEP) submitted in Canvas?** The
   repo has no record either way.
8. **Has any record of team communications been exported?** `docs/course/team/comms-export/` does not
   exist and zero exports have been taken. A full record is a required submission
   ([../team/communications.md](../team/communications.md)) and it cannot be reconstructed later if
   the channel history is trimmed.
9. **Supplier reconciliation:** what was the 10 SB "Project budget reallocation" on 25 AUG (KU-T6,
   still open), and where did the two colour sensors on ports C and D come from, given the ledger
   records no sensor purchase?

---

## 5. Related

- [INDEX.md](./INDEX.md) — the entry tracker and why the handwritten page is the submission
- [TEMPLATE.md](./TEMPLATE.md) — the form the six drafts follow
- [../deliverables.md](../deliverables.md) — the rubric and the calendar
- [../report/draft.md](../report/draft.md) — the Intro Report draft, built from the same evidence
