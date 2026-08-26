# SYS 301 Minesweeper — Documentation

ERAU **SYS 301 Systems Engineering, Introductory Project** (Fall 2026). A four-person team builds and
programs a LEGO Education SPIKE Prime robot for an instructor-briefed design challenge, and produces
the graded course deliverables. This repo holds all of it.

## Start here

| If you want... | Read |
|---|---|
| What this project is and is NOT | [scope.md](./scope.md) |
| The milestones and where we are | [roadmap.md](./roadmap.md) |
| What to do next | [todo.md](./todo.md) ← single source of truth |
| The rules of working here | [directives/INDEX.md](./directives/INDEX.md) |
| What's due, when, and how it's graded | [course/deliverables.md](./course/deliverables.md) |

> ⚠ **The design challenge is still PENDING** — it came from an instructor briefing we don't hold.
> See [scope.md § Mission](./scope.md#mission--partial-verbal-briefing-captured-2026-08-25). Do not build to the assumption without saying so.

## Folder map

| Folder | One purpose |
|---|---|
| [directives/](./directives/) | Condensed project-local rules — how we work here |
| [plans/](./plans/) | Dated tactical "how" artifacts, referenced from the roadmap by path |
| [findings/](./findings/) | **INTERNAL** — discoveries about our own robot/code, with measurements |
| [research/](./research/) | **EXTERNAL** — study of LEGO APIs, tools, techniques outside this repo |
| [lessons_learned/](./lessons_learned/) | Prescriptive rules distilled from our own mistakes |
| [decisions/](./decisions/) | ADRs — why we chose X over Y (immutable) |
| [features/](./features/) | Specs for shipped-and-stable capabilities |
| [runbooks/](./runbooks/) | Repeatable operator procedures (identify hub, deploy, demo day) |
| [session_records/](./session_records/) | Dated per-session narrative |
| [hardware/](./hardware/) | Port map, build record, budget ledger |
| [course/](./course/) | Graded deliverables — journal, report, team record |
| [archives/](./archives/) | Superseded and historical; archive, never erase |

**Boundary rule:** `research/` studies things OUTSIDE this repo; `findings/` analyses this repo itself.
A finding that hardens into a rule graduates to `lessons_learned/`.

Standards this repo follows: `~/llm-project-bootstrap/` (guides + directives), distilled into
[directives/](./directives/).
