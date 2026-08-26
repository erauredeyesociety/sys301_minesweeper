# Session Record — 2026-08-25 — Project Initialization

**Mode:** Discovery · **Sprint:** 1 (day 1) · **Hub connected:** no

---

## What was done

Ran the `Initialize` prompt from `~/llm-project-bootstrap/PROMPTS.md` against an empty repo (one commit,
a stub README). Read the operative guides — `PROJECT_SETUP`, `SESSION_CONDUCT`, `ASKING_QUESTIONS`,
`AUTONOMOUS_OPERATION`, `PROJECT_SCRIPTS` — and the hub directives, then built the project to standard.

**Course material read** (`../course/source-material/`, supplied by the operator mid-session):

- `Introduction Project Student Instructions.pdf` — roles, economy, communication rules, grading, calendar
- `journal_about.html` — the Canvas journal rubric
- `Example Journal Entry.pdf` — a scanned **handwritten** entry (DATE / NAME / QOD / Answer / Summary)
- `cser_template_cser2022 (7).docx` + `.pdf` — the Intro Report template (Elsevier Procedia, MS Word)

**Created:**

- Full `docs/` tree per the OS-folder model, every folder with an `INDEX.md`, plus `docs/course/` and
  `docs/hardware/` for this project's two extra concerns
- [scope.md](../scope.md) — objectives, provisional requirements, constraints, and an enforced blacklist
- [roadmap.md](../roadmap.md) — lean, calendar-anchored milestones M0–M4 + a parked FRONTIER item
- [todo.md](../todo.md) — SSOT with current state, next action, and what is blocked
- 15 project-local [directives](../directives/INDEX.md), including two written specifically for this
  project: `course-compliance.md` and `hardware-safety.md`
- Three ADRs: [stock firmware only](../decisions/0001-stock-lego-firmware-only.md) ·
  [split mission logic from hub I/O](../decisions/0002-split-mission-logic-from-hub-io.md) ·
  [repo holds all team work](../decisions/0003-repo-holds-all-team-work.md)
- `CLAUDE.md`, `MEMORY.md`, a real `README.md`, `.gitignore`
- `inventory.py` — the Schrute Buck ledger (see below)

**Delegated in parallel** (disjoint write zones): two background research agents on
`docs/research/spike-prime-linux-toolchain.md` and `docs/research/detection-and-sweep-techniques.md`;
one workflow fanning out four authors + four independent auditors across `docs/course/`,
`docs/runbooks/`, `docs/hardware/` + the code-scaffold READMEs, and the Sprint 1 plan.

---

## Decisions made

| Decision | Rationale |
|---|---|
| Repo holds **all** team work, not just code | The report gets written from the repo; reconstructing three weeks from memory on 17 SEP is the failure mode — [ADR-0003](../decisions/0003-repo-holds-all-team-work.md) |
| Stock LEGO firmware, Pybricks blacklisted | Shared equipment; operator constraint — [ADR-0001](../decisions/0001-stock-lego-firmware-only.md) |
| Hub OS treated as frozen until identified **read-only** | Opening the LEGO app can prompt an update; identify before acting — [ADR-0001](../decisions/0001-stock-lego-firmware-only.md) |
| `src/` pure logic, `src/` thin adapter | The hub is only available in class. This is the one decision that makes a test floor possible — [ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md) |
| Budget as an editable Python script, not a spreadsheet | Operator's call: live calculation, no Excel, teammates edit a list. `./inventory.py` / `--verbose` |
| Mechanical design **recorded**, not designed here | Operator deprioritized it; it belongs to the Designer and Builder |
| No code written this session | The mission is unknown and the hub's API generation is unidentified. Writing against a guess would be waste at best |

---

## Discoveries

- **The design challenge is not in any document we hold.** The instructions say only *"Your design
  challenge is per the Instructor's briefing."* This is the single largest open item, and it blocks
  every technical task. Recorded as PENDING rather than guessed.
- **"You MAY NOT work on the project outside of class"** (instructions p.1) is in direct tension with
  using this repo out of class. Flagged in [scope.md § Critical Notes](../scope.md#critical-notes) as
  the operator's call to make with the instructor — not something this repo should quietly resolve.
- **The journal is worth 80 points and loses 5 per missing day** — more than the peer evaluation, and
  the only score in the project that is fully within one person's control. It is also *handwritten in
  class*, so the repo copy is a durable record and drafting aid, not the submission.
- **The report template is MS Word with macros.** Whether its styles survive a LibreOffice round-trip on
  Ubuntu is unverified and worth testing early rather than on 17 SEP.
- **Wall-clock is the binding constraint, not difficulty.** Roughly five class sessions before Demo Day,
  with no permitted work between them, and role separation slows every physical iteration.
- Host: `earlyoom` inactive, ~3 GB RAM free at init — parallel spawning was kept modest and gated.

---

## Blockers

1. **The instructor's design briefing** — blocks the mission, the requirements, and all code. Operator to supply.
2. **Hub not physically connected** — blocks Hub OS / API identification, which blocks writing any hub code.
3. **Out-of-class-work ruling** — operator decision, possibly needs the instructor.
4. Team names and role assignments unknown; the operator's role is `[ASSUMED]` Programmer.

---

## What's next

Per [todo.md](../todo.md): the operator writes the briefing into
[scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25), and Sprint 1 executes the walking skeleton plan —
identify the hub read-only, prove the Ubuntu → hub → run → read-back loop, record the port map. Nothing
else is worth starting first.

**Not offered:** a git commit. Per the standards, commits are milestone-gated and human-only; a docs
scaffold with no working robot is not a milestone.

---

## Later the same session — blockers cleared, and one significant finding

The first three sections above describe the state at initialization. What changed after:

**Both blockers resolved by the operator:**

- **The out-of-class-work rule is not a blocker.** It governs team *collaboration*, not individual
  programming and design. Recorded in [scope.md § Critical Notes](../scope.md#critical-notes).
- **The design briefing was verbal and there is no document to find.** In full: *"Build a mine sweeper
  robot that finds all the mines (I think yellow sticky notes) in a 10×10 area."* Captured in
  [scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25) with the seven
  things it leaves open, and turned into a ranked ask-list at
  [plans/questions-for-the-professor.md](../plans/questions-for-the-professor.md).

**The finding that matters most.** A downward color sensor traces a line, not a swath, so lanes must be
spaced under a sticky note's width (~76 mm, or ~46 mm allowing for realistic heading drift). If "10×10"
means **feet**, exhaustive coverage is **125–204 m of driving — 8 to 23 minutes**. That is a design
problem, not a tuning problem. [findings/coverage-time-budget.md](../findings/coverage-time-budget.md).
It makes "10×10 in what units?" the highest-leverage question in the project.

**Research delivered** (three background agents): the Linux toolchain (USB MicroPython REPL survives on
current firmware; ModemManager on this host will corrupt the first session), detection and sweep
technique (use `reflection()`, never `color()` — color mode spatially averages at target edges, which is
fatal for edge counting; boustrophedon with a per-lane wall re-square), and color discrimination.

**Corrections made to this session's own work:**

- `src/README.md`, `tests/README.md`, `scripts/README.md` were created and then **removed** — the
  operator correctly pointed out that all `.md` belongs in `docs/`, and the README-per-subfolder rule
  covers `docs/` subfolders only. Their substance was folded into the three directives that already own
  those concerns. My briefing to the delegated writer caused this.
- Rewriting `scope.md § Mission` broke the `#mission--pending` anchor in 12 files. All repointed.
- ASCII diagrams replaced with mermaid, and the rule added to
  [directives/documentation-discipline.md](../directives/documentation-discipline.md).

**The delegated-then-audited pass earned its keep.** Independent auditors found 12 real defects in the
authored docs, including an invented university department presented as ready, illustrative sensor
numbers sitting unlabelled in the file that feeds the report's Results section, a miscounted observation
of a source document, and a trim-size arithmetic error on a row marked `[verified]`. All fixed.

**Tooling deliberately parked.** ResearchHub is **not running locally** — no process, no container,
nothing to stop. The five running Docker containers belong to other projects and total ~82 MB; stopping
them all would recover less memory than closing a few Chrome tabs. docs-rag is parked with the pwnstar
lead recorded but **untried**: [plans/2026-08-25-docs-rag-and-literature-workflow.md](../plans/2026-08-25-docs-rag-and-literature-workflow.md).

**Next:** ask the professor Q1 and Q2, and write `src/` plus its test floor — which needs no hub
and is not blocked by the open questions, provided it is parameterized.

---

## Later still — retrieval infrastructure and the SE planning layer

**Retrieval, both verified end-to-end by the orchestrator rather than trusted from agent reports:**

- **docs-rag deployed** — a local instance in `docs-rag/` built from `~/exudeai/rag-bootstrap` 0.8.3
  (which turned out to be *current*, not stale: 0 ahead / 0 behind, committed the same day). Semantic
  search over this repo's `docs/`, 65 of 65 files indexed. Verified with a query whose answer was
  hand-checked against the source file. **`/api/ask` returns HTTP 500** — no LLM pulled; search works,
  answer-generation does not. [runbooks/docs-rag.md](../runbooks/docs-rag.md).
- **ResearchHub tunnel working** — pwnstar (10.231.80.91) is reachable over ZeroTier with `~/.ssh/id_git`;
  port **5347 discovered, not guessed**. Stale detection was tested by killing the ssh process behind the
  script's back: `status` → exit 3, `restart` repaired it, `status` → WORKING. A live search returned 29
  real coverage-path-planning papers. [runbooks/researchhub-tunnel.md](../runbooks/researchhub-tunnel.md).
- **Cost ~1.9 GB**, almost entirely ollama's embedding-model runner; the four containers are ~143 MB.
  First thing to stop when memory is tight.
- **Docker cleaned** — all other projects' containers stopped and removed, all images except
  `sam-scraper-*` deleted (~6.7 GB). Volumes untouched. Held sam-scraper because no source tree was found
  to rebuild from; that is the operator's call, not ours.

**The SE planning layer landed** — [known-unknowns](../plans/known-unknowns.md) ·
[risk register](../plans/risk-register.md) · [coverage trade study](../plans/2026-08-25-coverage-strategy-trade-study.md) ·
[CONOPS](../plans/conops.md) · [requirements traceability](../plans/requirements-traceability.md) ·
[verification plan](../plans/verification-plan.md) · [motion control research](../research/motion-control-and-odometry.md).

**The trade study is the session's most valuable artifact.** It crosses Q1 (units) with Q2 (scoring)
into a decision table the team reads one cell from, and it produced two recommendations that hold
*before* any answer arrives: the Supplier should buy **one** colour sensor now (needed under every cell,
unblocks the two measurements everything depends on, ~10% sell-back if wrong), and the Programmer should
build the time-boxed run-time policy regardless of which option wins (~20 lines, converts "ran out of
time" from a zero into a partial score). It also establishes a harder truth: **at 10 ft with a hard
3–5 minute limit, nothing clears the bar — not even three sensors.**

**The audits again earned their cost.** Across four tracks they caught a misattributed "measured" value
that was actually an assumption, a materially wrong sensitivity claim (a stated overturning condition
that recomputation refuted), several arithmetic errors including a budget percentage taken against the
wrong denominator, a mitigation described as in place when the script does not exist, and a contingency
that quietly routed around the Hub-OS-update blacklist. All fixed.

**One standards conflict settled** (operator-derivable, so decided rather than asked): dated
`YYYY-MM-DD-<slug>.md` naming applies to point-in-time plans; living registers are named by concept
only. Recorded in [directives/roadmap-and-plans.md](../directives/roadmap-and-plans.md).

**Still true:** no git mutation has been made this session, and none is offered — a docs-and-planning
scaffold with an unbuilt robot is not a milestone.
