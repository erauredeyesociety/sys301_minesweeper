# Documentation Discipline

**Purpose.** The Intro Report (18 SEP) gets written FROM this repo. Every measurement, decision, and
dead end recorded now is report prose you don't have to reconstruct from memory in three weeks.

**Route by type — the load-bearing split is INTERNAL vs EXTERNAL:**

| Content | Folder |
|---|---|
| Discoveries about OUR OWN code/robot — measurements, root causes, "the carpet reads 22%" | `docs/findings/` |
| Study of things OUTSIDE this repo — LEGO APIs, tools, others' techniques | `docs/research/` |
| Prescriptive rules distilled from our own mistakes (WHEN → DON'T → BECAUSE) | `docs/lessons_learned/` |
| Why we chose X over Y | `docs/decisions/` (ADR, immutable, supersede with a NEW one) |
| Repeatable operator procedures — deploy, identify, demo | `docs/runbooks/` |
| Dated per-session narrative | `docs/session_records/` |
| Graded course artifacts — journal, report, team record | `docs/course/` |
| Build record, port map, budget ledger | `docs/hardware/` |

- **Hard cap: 1200 lines per document** (operator standard, 2026-08-26). Past that, split it into a
  folder with an `INDEX.md` front door. A document nobody can hold in their head stops being read, and a
  docs-rag chunk pulled from a sprawling file is harder to place in context. `./scripts/check-docs.py`
  enforces this. **Closest to the line today:** `docs/research/detection-and-sweep-techniques.md` at
  ~1156 — split it before adding to it, not after.
- **NEVER a `.md` in the repo root** (exception: `tmp*.md`, which are the operator's). The
  "README per subfolder" rule applies to `docs/` subfolders only — do **not** scatter `README.md` into
  `src/`, `tests/`, or `scripts/`. Rules about code live in these directives; code folders hold code.
- **Diagrams are mermaid, never ASCII art.** Use a ```` ```mermaid ```` fenced block — GitHub renders it,
  it stays legible in both light and dark themes, and it survives editing. ASCII boxes and arrow chains
  break the moment a label changes. `flowchart LR/TD` covers almost everything we need; `stateDiagram-v2`
  for the sweep and edge-counting state machines. **Not diagrams, and fine as plain code blocks:**
  real command output, file contents, code, and short fill-in forms.
- **Supersede in place; don't spawn a near-duplicate.** Grep `docs/` for the concept first and update
  the existing file at its existing path. Name files by concept, never by date-noise — except session
  records and ADRs, which are immutable dated records.
- **Cite, don't recopy.** A doc drawing on research cites the source path or URL in a `Sources:` line.
- **Every docs folder has an `INDEX.md`.** Update it when you add a file.
- **During active development: findings and session records only.** No formal feature docs until
  something is actually stable — except the graded deliverables, which are due on the calendar's
  schedule regardless.
- **Record the measurement, not just the conclusion.** "Threshold 45" is useless in the report;
  "floor 20±3%, sticky note 68±4% on classroom carpet under overhead fluorescents, 2026-09-03,
  threshold 45 with 8-point hysteresis" is a results section.
