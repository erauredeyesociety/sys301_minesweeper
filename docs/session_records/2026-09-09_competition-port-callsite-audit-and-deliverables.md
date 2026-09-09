# Session record — 2026-09-09 · the competition port, a whole bug class closed, and the deliverables started

**Hub:** NOT CONNECTED all session. Everything here is host-side work.
**Demo Day:** 2026-09-10 — tomorrow. **Journal:** 15 SEP. **Intro Report:** 18 SEP.

The theme of the day was **finding faults that no check could see**. Three separate defects would each
have ended the demo, and all three were invisible to a green `check-docs` run. Two claims that would
have reached a graded page were caught and corrected — one of them made by this session.

---

## 1. `src/main.py` ported to the rule that measurement chose

The competition program still ran the **chromaticity** detector that 2026-09-08 measured as failing —
yellow INVISIBLE, blue tape a 100% false positive. Every fix that day had gone into `examples/`.

| Change | Why |
|---|---|
| New pure module [`src/brightness.py`](../../src/brightness.py); `DETECT_MODE = "brightness"` | `reflection >= 30`. Carpet 3–9, tape 7–9, yellow 51–73, pink 97+ — zero overlap, 43-point gap, colour-agnostic |
| `hub_color.read_reflection_pair()` + `brightness.fuse()` | `hub_api.SECOND_COLOR_PORT` was declared and **read nowhere** in `src/` |
| Floor burst is now an **arming gate** | Fixed measured thresholds; the burst confirms the floor is dark and **refuses to arm** otherwise — a gate the chromaticity path structurally never had |
| `TICK_MS` 100 → 50 | Was 9.2 Hz, halving the safe traverse ceiling for no reason |

**Verified end-to-end on the host** with the measured values: a lane containing a yellow note, a blue
tape crossing and a pink note produced **exactly 2 counts, tape ignored, zero false rejections.**

`fuse()` takes the **max** deliberately — one mine crossing either sensor counts once, where two
independent counters would double-count on lane overlap. The honest cost is that two different mines
under both sensors at the same instant read as one; that is rarer, and an undercount is the safer error.

## 2. ⚠ `config` was a shadowed module name — `main.py` would have died at import

Nine `src/` modules did `import config`. MEASURED 2026-09-08: on the hub that resolves to something in
the LEGO firmware, **not** `/flash/lib/config.py`, and the program dies with `AttributeError` — even
though the upload hash-verifies. `main.py` had never run, so nobody had hit it. It was certain.

Renamed to **`mission_config.py`** tree-wide, via `import mission_config as config` so every `config.X`
reference survives — one line per file rather than a rewrite. 9 modules, 48 doc files.

**The hazard reproduced on Linux, independently:** `scripts/decode_telemetry.py` was still doing bare
`import config` and was silently binding to a **ROS 2 namespace package** on this host. Same failure
mode, different platform — which is the strongest possible argument that the rename was right.

## 3. ⚠ `deploy_deps.py --apply` could never have succeeded

The dry run — the thing the operator asked for — exposed it. `--apply` runs 16 × `upload.py` (each
sends Ctrl-C, **killing the Hub OS**) and then `slot_upload.py`, which needs the Hub OS **alive**. It
aborts at the identity check every time.

It now stops after the modules land, explains why, and hands over the exact next command plus the
power-cycle step, rather than failing at the last step looking like a tool bug.

## 4. ⚠ A whole bug class, and the standing check that closes it

`src/hub_color.py` used a **bare `_color`** on three lines — never imported. Every other hub-facing
module correctly writes `hub_api._motor`. On the hub that is a `NameError` on the **first sensor read**,
killing calibration instantly; with no handler, the robot froze on a glyph **with no tone**,
indistinguishable across a room from one that is thinking.

**Why nothing caught it:** `check-docs` verifies modules *import* on the host — but on the host
`hub_api.API == "simulated"`, so the SPIKE 3 branch **never executes** and the name is never looked up.
Every check passed green with the bug present. Nothing in `examples/` exercises `src/hub_*.py` either,
and `main.py` had never run.

**Operator decision:** an undefined-name pass was added to `./scripts/check-docs.py` — static analysis
in the spirit of *"a module that won't import is broken"*, extended to the branches the host never
reaches. Documented as **not** a test suite under ADR-0005. It **skips loudly** if `pyflakes` is
missing: a linter must not block a deploy at 09:00 on demo day.

**It found six more instances immediately:**

| File | Defect |
|---|---|
| `hub_distance.py` | same bare `_distance` |
| `hub_selfcheck.py` | **five** bare reader names, evaluated where the probe tuple is *built*, outside the try — the module could never have returned OK, NOT_OK or UNKNOWN on hardware. It would have thrown. |

All fixed.

## 5. ⚠ The recovery handler could not survive the failures it existed to catch

Found by a stub-based audit that exercised every hub-only call site.

| Defect | Consequence |
|---|---|
| `stop_motors()` not exception-safe | Called from `main.py`'s **outer `finally`** — a raise escaped everything **with a wheel turning**. Verified: left motor failing meant the right was *never commanded* |
| `tone_rising()` outside the try | The **first** hub call in the program sat outside every handler |
| `light_matrix.show` / `sound.beep` unguarded | Both `[UNVERIFIED]` signatures, both reachable from *inside* the recovery handler — a raise there escapes the guard meant to report the failure |
| `hub_drive.turn_by` started the spin before its try | A raise from the second `motor.run` left one wheel spinning; its docstring's "stops on every path" was false |

`stop_motors()` now attempts each motor independently and **cannot raise**; proven under stubs.
`except Exception` is deliberate *there and only there* — a function whose whole purpose is to run in a
`finally:` cannot be choosy; it reports failure by return value instead.

## 6. Other defects fixed

- **`counter.finish()`** was never called at a lane end — a mine open at the boundary merged with the
  next lane's first mine and **both** were rejected as `too_wide`. Silent double loss.
- **`detector.events`** was unbounded inside the mission loop — plausible `MemoryError` on a heap under
  252 KiB. Now a 64-entry ring; verified over 500 crossings that the **count is unaffected**.
- **Arming gate used `max()`** — one bright fleck, or a mine in the 450 mm calibration creep, refused
  the whole run. Now a 90th percentile plus a median check.
- **Timebox clock started at *program* start** — up to 433 s of operator waiting charged against a
  300 s budget. Now restarts when the sweep does.
- **`COMPLETE` read the plan's index, not lanes driven** — a run with dead encoders reported
  **COMPLETE with 0/75 lanes**. Now COMPLETE means lanes were driven; otherwise DEGRADED.
- **No top-level exception handler** in `main()` — ~30 never-executed call sites each failing as a
  silent freeze. Now stops, sounds a falling tone, holds `x`.
- **`analyse-survey.py` was lying.** The demo-day tool scored the *refuted* rule and told the operator
  his yellow mines were undetectable and he needed a blue veto — the opposite of measured truth. It now
  reports the shipped rule first: tape and carpet **0.0%**, yellow **95.8–100%**.

## 7. Two false claims caught before reaching a graded page

1. **The two-sensor fix did NOT halve coverage** — a claim this session made. `lane_pitch_mm()` is
   `76 − 30 − 5 = 41 mm` and never references the sensors, so `SweepPlan` still plans **75 lanes**.
   The fix buys **REDUNDANCY**, not coverage. Widening the pitch needs the [UNMEASURED] sensor spacing.
   Corrected in `CLAUDE.md` and `known-unknowns.md`.
2. **The `_color` NameError was reported as still open** by a readiness doc that was a stale snapshot
   taken before the fix landed. Its NOT-FIT-TO-RUN verdict must be re-derived, never quoted.

## 8. ResearchHub — the tool was right, the operator was right, this session was wrong

`rh-query.sh` reported DOWN. Investigation showed the tunnel and service were **fine**: the failure was
`{"status":"degraded","reason":"db handle not initialized"}`. The db handle backs the **workspace and
KB**; the **discovery corpus search** — the only endpoint the wrapper calls — does not need it.
Verified in that exact state: **10 real papers with arXiv IDs, PDF URLs and abstracts.**

Both health checks now accept `healthy` **or** `degraded` and say which — a narrowing, not a loosening;
non-200s, timeouts and half-open sockets still fail. ⚠ **Two checks enforced the same fact** (one in
`rh-tunnel.sh`, one in `rh-query.sh`) and fixing one left the wrapper still refusing.

**Honest caveat:** discovery proxies searxng and results are mixed — genuine arXiv papers alongside
ChatGPT landing pages. A supplement to WebSearch, not a replacement.

## 9. Deliverables started

- **[`docs/course/report/draft.md`](../course/report/draft.md)** — 1089 lines, assembled from the
  measured record with gaps marked. The 18 SEP deliverable is substantially started.
- **Journal**: the audit established the graded artifact is a **handwritten page written in class** —
  the markdown copy *"does not earn a single point"*. Drafts were produced for the six class days, but
  the operator has **deferred this thread**; do not spend more effort without his direction.
- **Four report questions added** for Demo Day, all unanswerable from the repo: point value, page
  limit, per-team-vs-per-student, and whether mermaid diagrams may be submitted as exported images —
  **78 files carry mermaid, zero rendered images exist, `mmdc` is not installed.**

## 10. Decisions made

| Decision | Basis |
|---|---|
| Undefined-name check added to `check-docs.py`, documented as not a test suite | Operator decision; it found 6 more instances immediately |
| `config` → `mission_config` tree-wide | Measured shadowing on the hub, reproduced on Linux via ROS 2 |
| Demo sweeps a **declared region**, not the full arena | Full coverage is unreachable; 914 mm is a **placeholder**, recorded as KU-D12 `OPEN — PRIORITY` |
| `deploy_deps --apply` stops before the entry and hands off | The sequence could never have succeeded |
| `degraded` ResearchHub accepted for discovery search | Measured: 10 real papers returned in that state |

## 11. What is next

**Hub-blocked, in order:**
1. **First run of `src/main.py`** — staged: arm → calibrate-only → one lane → full sweep. Still the
   dominant risk.
2. **Sensor spacing** — a 30-second ruler reading. Unblocks widening the lane pitch (KU-M33).
3. **Bias vs noise** in heading wander — needs ~5 full-length runs; a *fatal* bias is still inside the
   confidence interval at n = 4.

**Host-side, open:** KU-D12 (demo scope) needs an operator ruling or the professor's slot length;
`RUN_TIMEBOX_S = 300` is still `[ASSUMED]`. The micro-SLAM literature workflow was in flight at save
time. `examples/find_corner.py` was written by a workflow and has never been reviewed.

**Load `examples/find_note.py` in a second slot regardless** — it has actually run and found real mines
in both colours. If `main.py` fails on the day, that demonstrates detection with code that works.
