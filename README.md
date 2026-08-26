# sys301_minesweeper

ERAU **SYS 301 Systems Engineering — Introductory Project** (Fall 2026). A four-person team designs,
builds, programs, and demonstrates a LEGO Education SPIKE Prime robot, and produces the graded course
deliverables. This repository holds all of it.

> ⚠ **The design challenge is not yet documented here.** It was delivered in an instructor briefing we
> don't hold. See [docs/scope.md § Mission](docs/scope.md#mission--partial-verbal-briefing-captured-2026-08-25). Nothing downstream of that
> is settled.

## Quick start

```bash
./inventory.py              # current Schrute Buck balance
./inventory.py --verbose    # full budget statement
```

No robot code exists yet — deliberately. The mission is unknown and the hub's API generation is
unidentified. See [docs/todo.md](docs/todo.md) for what happens next.

## Where to look

| | |
|---|---|
| **What to do next** | [docs/todo.md](docs/todo.md) |
| What this project is and is NOT | [docs/scope.md](docs/scope.md) |
| Milestones | [docs/roadmap.md](docs/roadmap.md) |
| How we work here | [docs/directives/INDEX.md](docs/directives/INDEX.md) |
| What's due, when, how it's graded | [docs/course/deliverables.md](docs/course/deliverables.md) |
| Full documentation map | [docs/README.md](docs/README.md) |
| Session context for AI agents | [CLAUDE.md](CLAUDE.md), [MEMORY.md](MEMORY.md) |

## Hardware

LEGO Education SPIKE Prime Technic Large Hub (45601) — 6 ports A–F, 5×5 light matrix, speaker, 6-axis
gyro. Sensors available to the course: Color 45605, Distance 45604, Force 45606, plus motor encoders.
Development on native Ubuntu 22.04.

**The hub runs stock LEGO firmware and always will** — third-party firmware is permanently excluded
([ADR-0001](docs/decisions/0001-stock-lego-firmware-only.md)).

## Key dates

| Date | Event |
|---|---|
| 25 AUG | Sprint 1 begins |
| 1 SEP | Sprint 2 begins · mid-project survey |
| **10 SEP** | **Demo Day** |
| 15 SEP | Peer review + journal due |
| 18 SEP | Intro Report due |

---
Structured to the standards in `~/llm-project-bootstrap/`, distilled into [docs/directives/](docs/directives/).
