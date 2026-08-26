# Intro Report — Section Outline and Source Mapping

Section order is **fixed by the template** (`../source-material/cser_template_cser2022 (7).pdf` §1.1):
*Title, Authors, Affiliations, Abstract, Keywords, Main text (including figures and tables),
Acknowledgements, References, Appendix.* Numbering starts at the Introduction.

**The point of this file is the middle column: which repo artifact feeds each section.** The report is
written FROM the repo ([ADR-0003](../../decisions/0003-repo-holds-all-team-work.md)), not from memory on
17 SEP. If a section's source column says "does not exist yet", that is a gap in the record, not just a
gap in the paper — fix it in the repo first.

Legend: 🔒 **gated on the mission statement** — the verbal briefing is captured but **PARTIAL**, with
open questions still to ask ([../../scope.md § Mission](../../scope.md#mission--partial-verbal-briefing-captured-2026-08-25)) ·
⏳ waiting on work that hasn't happened yet.

---

## Master map

| # | Section | Style | Fed by | Status |
|---|---|---|---|---|
| — | Title | `Els-Title` | The mission statement | 🔒 |
| — | Authors | `Els-Author` | [../team/roles.md](../team/roles.md) | ⏳ names TBD |
| — | Affiliations | `Els-Affiliation` | Embry-Riddle Aeronautical University — department, campus, postcode all **[ASSUMED/UNCONFIRMED]** | ⏳ confirm |
| — | Abstract | `Els-Abstract-text` | Written **last**, from §1 + §5 | 🔒 |
| — | Keywords | `Els-keywords` | — | 🔒 |
| 1 | Introduction | `Els-1storder-head` | [../../scope.md](../../scope.md) §Overview, §Objectives, §Constraints · [deliverables.md § Calendar](../deliverables.md#calendar) | 🔒 partial |
| 2 | Problem Statement & Requirements | ″ | [../../scope.md](../../scope.md) §Mission, §Requirements (FR/TR/RR) | 🔒 |
| 3 | Systems Engineering Approach | ″ | [../team/roles.md](../team/roles.md) · [../team/communications.md](../team/communications.md) · `docs/plans/2026-08-25-sprint-1-walking-skeleton.md` · `docs/session_records/` | writable now |
| 4 | Design & Implementation | ″ | `docs/decisions/` (ADR 0001–0003) · `docs/hardware/port-map.md` · `docs/hardware/build-record.md` · `src/` | 🔒 partial |
| 5 | Verification & Results | ″ | `docs/findings/` · `tests/persistent/` · Demo Day observations | ⏳ 🔒 |
| 6 | Budget & Resource Management | ″ | `inventory.py` · `docs/hardware/build-record.md` | writable now |
| 7 | Discussion — what did not work | ″ | `docs/findings/` (failed approaches) · `docs/lessons_learned/` · journal entries | ⏳ |
| 8 | Lessons Learned & Conclusions | ″ | `docs/lessons_learned/` · `docs/course/journal/*.md` | ⏳ |
| — | Acknowledgements | `Els-acknowledgement` | Manual. Unnumbered, bold heading. | ready |
| — | Appendix A… | `Els-appendixhead` | `docs/hardware/port-map.md` · `inventory.py --verbose` · `src/` listings | ⏳ |
| — | References | `Els-reference-head` | `docs/research/*.md` `Sources:` lines | writable now |

---

## Section by section

### Title · Authors · Affiliations

- **Title** 🔒 — must name the actual design challenge. Placeholder until the mission wording settles
  (scope.md § Mission is PARTIAL: arena units and what "finds" delivers are still open).
- **Authors** — four team members. From [../team/roles.md](../team/roles.md), which currently has
  **TBD** in the name column. Corresponding author needs a phone and email per the template's footnote.
- **Affiliations** ⏳ — Embry-Riddle Aeronautical University. **[ASSUMED/UNCONFIRMED]**: "Department of
  Systems Engineering" is inferred from the course code SYS 301, not from any document we hold; the
  campus, address, and postcode are unknown. Confirm all four before submission. One affiliation is
  assumed, so a single superscript `a`.

### Abstract 🔒 · Keywords 🔒

`Els-Abstract-text`, 9 pt. Write it **last**: one sentence of context, one of problem, two of method,
two of result, one of conclusion. Cannot be written before there is a result to state.
Keywords are semicolon-separated (template: "separated by semicolons ;"). Candidates, pending the
mission: `systems engineering; LEGO SPIKE Prime; autonomous robotics; role-based teaming; Scrum`.

### 1. Introduction 🔒 (partial)

**Fed by:** [../../scope.md](../../scope.md) §Overview / §Objectives / §Constraints ·
[../deliverables.md § Calendar](../deliverables.md#calendar).

The course context, the four-role constraint, the 100 Schrute Buck economy, the three-week calendar,
and a one-paragraph statement of the design challenge. Everything **except** the challenge statement
is writable today — scope.md §Overview is already the first draft of it. Ends with a paragraph mapping
the rest of the paper.

### 2. Problem Statement and Requirements 🔒

**Fed by:** [../../scope.md](../../scope.md) §Mission and §Requirements.

scope.md already carries **FR-1…FR-6**, **TR-1…TR-5**, **RR-1…RR-5** as numbered, checkable
requirements — they lift into a table here almost verbatim. But scope.md marks them *provisional,
derived from an unconfirmed assumption about the mission*. **Do not publish them as requirements until
the briefing confirms or replaces them.** A requirements section derived from a guess is the single
worst thing this paper could contain.

Include the derivation: briefing → objectives → FR/TR/RR → verification method. That traceability *is*
the systems engineering content of the course.

### 3. Systems Engineering Approach — writable now

**Fed by:** [../team/roles.md](../team/roles.md) · [../team/communications.md](../team/communications.md) ·
`docs/plans/2026-08-25-sprint-1-walking-skeleton.md` · `docs/session_records/` ·
[../deliverables.md § Calendar](../deliverables.md#calendar).

The role separation and its enforcement, the Scrum structure (two sprints, 20-min planning, 5-min
standups, an AI Scrum Master), the written-communication-first policy and *why* it is written-first
(1 SB/person/minute makes it literally cheaper), and how the team handled the information bottlenecks
the roles create. **This is the section the course is actually about** and it needs no hardware,
so draft it first.

### 4. Design and Implementation 🔒 (partial)

**Fed by:** `docs/decisions/` · `docs/hardware/port-map.md` · `docs/hardware/build-record.md` · `src/`.

- **Architecture rationale** — [ADR-0002](../../decisions/0002-split-mission-logic-from-hub-io.md):
  pure `src/` logic vs thin `src/` adapter, and why that split is what made host-side
  testing possible without hardware. Writable now.
- **Platform constraint** — [ADR-0001](../../decisions/0001-stock-lego-firmware-only.md): stock LEGO
  firmware, third-party firmware excluded, and the consequences for tooling on Linux. Writable now.
- **Mechanical build** — from `docs/hardware/build-record.md`; the Designer's sketches are the figures.
  🔒 and not ours to author — the Designer owns the physical design
  ([../../scope.md § Boundaries](../../scope.md#boundaries)).
- **Port map** — `docs/hardware/port-map.md` becomes a small table. ⏳
- **Detection / sweep algorithm** — 🔒, gated on the mission.

**Figures:** captions **below**, 8 pt, 300 DPI, PNG/JPEG/GIF, embedded (template §2).

### 5. Verification and Results ⏳ 🔒

**Fed by:** `docs/findings/` · `tests/persistent/` · Demo Day (10 SEP) observations.

This is the section [documentation-discipline](../../directives/documentation-discipline.md) exists to
supply: **record the measurement with its units and conditions, not the conclusion.** A finding that
reads "floor 20±3%, sticky note 68±4% on classroom carpet under overhead fluorescents, 2026-09-03,
threshold 45 with 8-point hysteresis" *is* a results paragraph. "We tuned the threshold" is not.
⚠ Those numbers are an **illustration of the required shape, not data** — nothing has been measured and
the hub has never been connected. Never let a shape-example survive into the paper as a result.

`docs/findings/host-environment.md` already exists and belongs here as a setup-verification result.

**Everything in this section must be observed.** No projected numbers, no "should be around", no
reporting a run that did not happen — [honest-instrumentation](../../directives/honest-instrumentation.md),
and it is blacklist-level in [scope.md](../../scope.md#permanently-out-of-scope-blacklist--enforced-not-deferred).
Demo Day is the primary data point: **assign someone to record the actual numbers on 10 SEP** — attempts,
successes, run time, failures and their causes. It is unrepeatable.

**Tables:** captions **above**, horizontal rules only, embedded (template §1.2).

### 6. Budget and Resource Management — writable now

**Fed by:** `inventory.py` (run `./inventory.py --verbose` and paste the statement as Table N) ·
`docs/hardware/build-record.md`.

As of 2026-08-25: 100 SB start, motors ×2 @10 = 20, wheels ×2 @7 = 14, project budget reallocation 10 →
**56 SB remaining**. Also discuss the economy as a *systems* constraint: sell-back at 90% rounded down
makes a wrong purchase cost ~10% permanently; meeting time is a priced resource; role violations cost
2 SB each. A tidy, quantitative section that is free to write and easy to do well.

### 7. Discussion — what did not work ⏳

**Fed by:** `docs/findings/` (specifically the failed approaches) · `docs/lessons_learned/` ·
`docs/course/journal/*.md` ("What didn't go well? What unforeseen problems arose?").

The journal's own prompts are this section's outline. Dead ends are worth as much as successes here
([knowledge-retrieval](../../directives/knowledge-retrieval.md)) — write them down as they happen or
they are gone by 18 SEP.

### 8. Lessons Learned and Conclusions ⏳

**Fed by:** `docs/lessons_learned/` (WHEN → DON'T → BECAUSE rules) · the six journal entries.

Tie back to the §1 objectives: which were met, which were not, what would be done differently. Six
handwritten reflections, transcribed, are the raw material — another reason the repo copy exists.

### Acknowledgements

Unnumbered, bold, left-justified, `Els-acknowledgement`, at the end of the article — the template
explicitly forbids putting them on the title page or in a title footnote (§1.1). Dr. Watson, the TA,
and disclosure of AI assistance (the Scrum Master agent is course-provided; state it).

### References

Numbered **in order of appearance**, cited in text as superscript. Sources to expect:
`docs/research/spike-prime-linux-toolchain.md` and `docs/research/detection-and-sweep-techniques.md`
each carry a `Sources:` line — those URLs are the reference list. LEGO Education official documentation,
the course instructions PDF, and any SE textbook the course assigns.
Every in-text citation must appear in the list and vice versa (§1.3).

### Appendix A…

Candidates: full port map · full `./inventory.py --verbose` statement · key source listings from
`src/` · the Designer's sketches if not already figures.

⚠ **The template contradicts itself on placement.** Its §1.1 ordering sentence lists the Appendix
**last** ("…Acknowledgements, References, Appendix"), but the template document's own body puts
`Appendix A` **before** References, and the Appendix section text says: "Authors including an appendix
section should do so before References section." **Follow the body — Appendix before References** — and
note the discrepancy if asked.

---

## Writing order (does not match reading order)

1. **§3 Systems Engineering Approach** — no hardware, no mission needed. Start here.
2. **§6 Budget** — `inventory.py` already has the data.
3. **§1 Introduction** minus the challenge statement.
4. **§4 Design** — architecture rationale from the ADRs.
5. *(the open mission questions are answered)* → **§2 Requirements**, then §4's algorithm content.
6. *(Demo Day, 10 SEP)* → **§5 Results** — same day, while it is accurate.
7. **§7, §8** from the journal.
8. **Abstract and Keywords last.**
