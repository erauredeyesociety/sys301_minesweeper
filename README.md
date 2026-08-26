# sys301_minesweeper

ERAU **SYS 301 Systems Engineering — Introductory Project** (Fall 2026). A four-person team designs,
builds, programs, and demonstrates a LEGO Education SPIKE Prime robot, and produces the graded course
deliverables. This repository holds all of it.

> ⚠ **The design challenge is not yet documented here.** It was delivered in an instructor briefing we
> don't hold. See [docs/scope.md § Mission](docs/scope.md#mission--partial-verbal-briefing-captured-2026-08-25). Nothing downstream of that
> is settled.

## Quick start

```bash
./find_spike_prime.py       # is the hub connected and usable?  (Linux, Windows, macOS)
./inventory.py              # current Schrute Buck balance
./inventory.py --verbose    # full budget statement
./scripts/stack.sh status   # is the research/retrieval stack up?
```

## Getting code onto the robot

**You cannot `pip install` anything onto the hub.** It runs LEGO's own MicroPython. A "program" is a
**single file** dropped into one of the hub's **20 slots (0–19)**. You edit on your computer, push the
file into a slot over USB, then **unplug the cable** — the hub runs it standalone.

```
edit src/*.py  →  push into a slot over USB  →  unplug  →  hub runs it on its own
```

**The route** (same on Linux and Windows — one VS Code extension, USB serial at 115200):

```bash
# 1. Is the hub there?
./find_spike_prime.py --verbose        # Windows: python find_spike_prime.py --verbose

# 2. Install the uploader
code --install-extension PeterStaev.lego-spikeprime-mindstorms-vscode

# 3. First line of your program, so it skips the prompts:
#    # LEGO slot:5 autostart
```

**Linux one-time setup** — do this *before* first plugging in, or ModemManager will corrupt the session
and it will look like broken hardware:

```bash
sudo usermod -aG dialout $USER      # then log out and back in
sudo systemctl disable --now ModemManager
```

**Windows:** if Device Manager shows the hub with a warning triangle under *Ports (COM & LPT)*, install
the LEGO SPIKE app once for the driver, then close it — **do not let it update the hub.**

⚠ **Identify the Hub OS read-only first** — the extension version depends on it (v2.x+ is Hub OS 3 only),
and opening the LEGO app on a version mismatch triggers an update prompt that
[ADR-0001](docs/decisions/0001-stock-lego-firmware-only.md) forbids accepting.

Full procedure, fallbacks, and troubleshooting: **[docs/runbooks/upload-to-hub.md](docs/runbooks/upload-to-hub.md)**

Robot code is a deliberate skeleton so far — the mission is only partly known and the hub's API
generation is unidentified. See [docs/todo.md](docs/todo.md).

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
