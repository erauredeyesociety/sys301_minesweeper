# CLAUDE.md — sys301_minesweeper

Read this first, every session. Then [docs/todo.md](docs/todo.md) for where we are.

## What this is

ERAU **SYS 301 Systems Engineering — Introductory Project** (Fall 2026). A four-person team builds and
programs a LEGO Education SPIKE Prime robot for an instructor-briefed design challenge, and produces the
graded course deliverables. This repo holds all of it: robot code, engineering record, hardware record,
journal, report drafts, budget ledger.

## The mission — PARTIAL, and there is no document to find

The briefing was **verbal**, and this is the whole of it:

> *"Build a mine sweeper robot that finds all the mines (I think yellow sticky notes) in a 10×10 area."*

That is the requirement of record. **"10×10" has no units**, the boundary type is unknown, "finds" is
undefined, and whether other colors are present is unknown. Full breakdown and how we proceed anyway:
[docs/scope.md § Mission](docs/scope.md#mission--partial-verbal-briefing-captured-2026-08-25).
Open questions to put to the professor: [docs/plans/questions-for-the-professor.md](docs/plans/questions-for-the-professor.md).

**⚠ The units question is not academic.** If "10×10" means feet, a single downward color sensor needs
125–204 m of sweeping — 8 to 23 minutes — and the design has to change, not the tuning.
[docs/findings/coverage-time-budget.md](docs/findings/coverage-time-budget.md).

**Never invent mission details.** Everything still guessed is marked `[ASSUMED]`. Build to the narrowest
defensible reading and parameterize, so a clarified answer changes a value, not the architecture.

## BLACKLIST — enforced, never worked around

1. **The hub keeps its stock LEGO firmware.** Pybricks and every third-party firmware are permanently
   excluded because they flash the hub. No DFU, no bootloader, no filesystem format, no factory reset.
2. **Never accept a "Hub update required" prompt.** A Hub OS change is an operator decision recorded as
   an ADR — never a side effect of opening a tool. If something asks, stop and ask the operator.
3. **Never open a blocking serial read from a tool call.** It hangs the session. Every hub-touching
   command lives in a `scripts/` helper with an explicit timeout that exits.
4. **Git mutations are human-only.** Never `git add`/`commit`/`push`. Reads are fine. Propose the exact
   commands at a real milestone and let the operator run them.
5. **Never touch hardware unasked.** The operator says when the hub is connected; until then it is
   absent. Never initiate a connection, pairing, scan, or hub-touching script on your own.
6. **Never fabricate a result.** No invented sensor readings, no "should be around 70%", no reporting a
   hub result while the hub is unplugged, no green over untested hardware. If it wasn't run, say so.
7. **Never invent the mission, the arena, the build, or a teammate's name.**
8. **"Measured" means on real hardware.** Say "computed" or "confirmed against \<source\>" for anything else — [docs/lessons_learned/say-which-kind-of-verified.md](docs/lessons_learned/say-which-kind-of-verified.md).

## Hard facts

- **Hardware:** SPIKE Prime Technic Large Hub 45601 — 6 ports A–F, 5×5 light matrix, speaker, 6-axis gyro,
  USB + Bluetooth. Sensors available: Color 45605, Distance 45604, Force 45606. Motors available: Technic
  Large Angular 45602, **Medium Angular 45603**, Small Angular 45607. Plus the hub gyro and the motors' rotary encoders.
  **Not currently connected.**
- **Owned so far:** 2 motors, 2 wheels — differential drive, decided by the team 2026-08-25. **Types of
  BOTH are unknown**, and several wheel sizes are on hand. **No sensors, no mounting blocks, no axles yet.**
  Store prices can change; `inventory.py` records the price actually paid per line, not a price list.
- **Hodge-podge hardware: measure, don't model.** Wheel diameter, track width, top speed, loop rate and
  cross-track error are all unmeasured. Carry them as config variables and close them on the bench —
  [docs/lessons_learned/model-only-to-the-next-decision.md](docs/lessons_learned/model-only-to-the-next-decision.md).
- **The team wants color *classification*, not just presence detection** (scope FR-2b). Sticky notes are
  matte and pastel — the worst case for the sensor's built-in color ID. An unclassifiable reading is
  reported as UNKNOWN, never forced into a class.
- **ModemManager is active on this host** and will corrupt the first hub serial session. Fix it *before*
  the hub is ever plugged in — [docs/findings/host-environment.md](docs/findings/host-environment.md).
- **Hub OS / API generation: UNKNOWN.** Determines SPIKE 3 (`import motor`, `from hub import port`,
  `import runloop`) vs legacy SPIKE 2 (`from spike import PrimeHub`). Most tutorials online target the
  obsolete SPIKE 2 API — check what generation a source targets before believing it. Don't write mission
  code against a guessed API. Identify read-only first: [docs/runbooks/hub-identification.md](docs/runbooks/hub-identification.md).
- **Host:** native Ubuntu 22.04, Python 3.10.12, user in `dialout`, google-chrome present. LEGO does not
  officially support Linux desktop.
- **Architecture:** **flat `src/`**, no packages ([ADR-0004](docs/decisions/0004-flat-src-supersedes-package-split.md),
  superseding ADR-0002). **The filename is the rule:** `hub_*.py` may touch the LEGO API, nothing else may.
  Pure — `config` · `calibration` · `detector` · `sweep` · `result` · `odometry` · `classify` · `telemetry`,
  all host-runnable with no robot. Hub-facing — `hub_api` · `hub_color` · `hub_distance` · `hub_motors` ·
  `hub_imu` · `hub_ui` · `hub_selfcheck`, **one file per device**. Every reader returns `None`, never `0`,
  when it cannot read. **`./scripts/check-docs.py` enforces the boundary** — there is no test suite
  ([ADR-0005](docs/decisions/0005-no-test-suite-verify-on-hardware.md)), so that check is its only guard.
  `src/main.py` is deliberately unwritten: it is where every open unknown converges.
- **Budget:** `./inventory.py` (`--verbose` for a statement) is the live Schrute Buck ledger and the single
  source of truth. Edit the `ENTRIES` list; don't build a parallel markdown table.

## Course rules that override engineering preference

- **"You MAY NOT work on the project outside of class" — resolved, not a blocker.** The operator ruled
  (2026-08-25) that this governs *team collaboration*, not individual work: programming and design happen
  whenever. Physical assembly and store purchases still happen in class with roles enforced.
- **Roles are enforced, −2 Schrute Bucks per violation.** Builder assembles and is the *only* operator of
  the robot · Designer designs, may not touch supplies · Supplier alone handles money and supplies ·
  Programmer codes, may touch the robot only to plug/unplug it. Address advice to the right role.
- **All written team communication is a graded deliverable submitted in full.**
- **Face-to-face beyond the daily 5-min standup costs 1 SB per person per minute.** Prefer writing.
- **The journal is 80 points and loses 5 per missing day** — the cheapest guaranteed score in the project.
- **Dates:** Demo Day 10 SEP · Peer review + journal 15 SEP · Intro Report 18 SEP (CSER 2022 Word template).

## How we work here

Project-local rules: **[docs/directives/INDEX.md](docs/directives/INDEX.md)** — read the ones that apply.
Start with `course-compliance.md` and `hardware-safety.md`. Upstream standards live in
`~/llm-project-bootstrap/` (guides + directives); the project-local files are the distillation.

Docs routing — every folder has an `INDEX.md`, and **no `.md` in the repo root** (`tmp*.md` excepted):

| Content | Folder |
|---|---|
| Discoveries about our own robot/code, with measurements | `docs/findings/` |
| Study of things outside this repo (LEGO APIs, tools, techniques) | `docs/research/` |
| Rules distilled from our own mistakes (WHEN → DON'T → BECAUSE) | `docs/lessons_learned/` |
| Why we chose X over Y | `docs/decisions/` (ADRs, immutable) |
| Repeatable operator procedures | `docs/runbooks/` |
| Tactical "how" artifacts, dated | `docs/plans/` |
| Dated session narrative | `docs/session_records/` |
| Graded course artifacts | `docs/course/` |

**Diagrams are mermaid, never ASCII art** — ```` ```mermaid ```` blocks, `flowchart` / `stateDiagram-v2`.
Command output and code stay as plain fenced blocks.

**Script the ritual; don't re-improvise it inline.** Prefer a `scripts/` helper over a long shell
one-liner — the operator has to approve complex commands, and a re-typed pipeline drifts from the
tested one. After touching docs or `src/`, run **`./scripts/check-docs.py`** (links · INDEX coverage ·
no stray root `.md` · the `src/` purity boundary · every module imports on the host; `--fix-rag`
re-ingests). If you find yourself running the same multi-step thing twice, that is the signal to write
it down as a script — [docs/directives/automation-first.md](docs/directives/automation-first.md).

**Record the measurement, not just the conclusion.** "Threshold 45" is useless in the report; "floor
20±3%, target 68±4% on classroom carpet under overhead fluorescents, 2026-09-03, threshold 45 with 8-point
hysteresis" is a results section. The Intro Report gets written *from* this repo.

**Testing: there is none, by decision** ([ADR-0005](docs/decisions/0005-no-test-suite-verify-on-hardware.md)).
No `tests/`, no pytest, and **do not create any without a new ADR**. Verification is: the interpreter (a
module that won't import is broken), throwaway one-liners while developing, and the robot on the floor.
The `src/` import boundary is the one standing check, in `./scripts/check-docs.py`.
Full reasoning, and why minimalism replaces both a debugger and a suite: [test_methodology.md](test_methodology.md).

**Report the conclusion, not the transcript** (operator, 2026-08-26). Say what a check found; don't paste
the command that found it. This does **not** loosen the rule against reporting an unobserved result — the
verification still happens, it just isn't narrated. Paste output when it's surprising, when it *is* the
deliverable, or when asked.

**Retrieval.** This project has a **docs-rag** over its own `docs/` at `http://127.0.0.1:10060`
([runbook](docs/runbooks/docs-rag.md)). ⚠ **It is only PARTIALLY working: search yes, `/api/ask` no.**
That distinction is the whole value — `ask` synthesises an answer so you don't read and reason over
chunks yourself; search alone still makes you do that work and burn the tokens. Until `ask` works,
docs-rag saves you *finding* the file, not *reading* it.

> **Temporary pass, granted by the operator 2026-08-26:** use search-only docs-rag anyway. It is
> genuinely useful for locating the right file in a 90-file tree, and the VPN outage blocking `ask` is
> not a reason to leave it idle. **This is revocable — the operator will say when to stop.** It does
> **not** change the status: the honest answer to "is the docs-rag working?" is still **PARTIAL**, and
> it stays that way until `/api/ask` answers. Check with `./scripts/stack.sh status`, which
reports search and ask separately. **The fix is remote `qwen3.5:9b` on skytracker, gated on the ERAU
VPN — not a local model. No sub-5B, and never pull a generation model on initiative: shared GPU is
operator-gated** ([ADR-0006](docs/decisions/0006-docs-rag-llm-is-operator-gated.md)), and **ResearchHub** for
academic papers — query it with **`./scripts/rh-query.sh "question"`**, never raw curl: it repairs a
stale tunnel itself and distinguishes tunnel-down (exit 3) from ResearchHub-down (exit 4) from
query-failed (exit 5), so an empty result is genuinely empty
([runbook](docs/runbooks/researchhub-tunnel.md)). Order and fail-open rules:
[docs/directives/knowledge-retrieval.md](docs/directives/knowledge-retrieval.md). Re-ingest after
writing docs. Both are conveniences — if either is down, grep and carry on.

**Questions:** foresee them, batch them in one round with a recommendation and a default. Never guess the
mission, the arena, or anything submitted for a grade.
