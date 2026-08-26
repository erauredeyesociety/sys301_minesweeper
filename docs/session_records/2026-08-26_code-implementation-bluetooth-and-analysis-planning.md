# Session Record — 2026-08-26 — Implementation, Bluetooth, and the analysis layer

**Mode:** Development (host-side) · **Sprint:** 1 · **Hub connected:** **no — never, at any point**
· **Robot built:** no

Continues [2026-08-26_retrieval-stack-code-scaffold-and-se-planning.md](./2026-08-26_retrieval-stack-code-scaffold-and-se-planning.md).

> **Nothing in this session touched hardware.** No serial device existed, `bleak` was never installed,
> and every module reported `api_generation() == "simulated"` throughout. Every check described below
> was pure Python on the host. See the correction section — the *wording* caused real alarm, and the
> rule that came out of it is now blacklist-level.

---

## What was done

### The code is written

`src/` is now fifteen modules. **The filename is the boundary rule**: `hub_*.py` may touch the LEGO API,
nothing else may, and `./scripts/check-docs.py` enforces it.

| Pure (host-runnable) | Hub-facing (`hub_*.py`, one per device) |
|---|---|
| `config` `calibration` `detector` `sweep` | `hub_api` (detection, port map, clock) |
| `result` `odometry` `classify` `telemetry` | `hub_color` `hub_distance` `hub_motors` `hub_imu` `hub_ui` `hub_selfcheck` |

`src/main.py` is **deliberately unwritten** — it is where every open unknown converges (arena size,
boundary type, whether classification is needed, the achieved loop rate), so writing it now means
writing it twice.

Implemented against [mission-algorithm.md](../plans/mission-algorithm.md) by four parallel agents on
disjoint files, each independently audited. That parallelism was only safe because the spec was already
audited and gave exact signatures — there was nothing for the agents to negotiate.

### Bluetooth answered

- **LEGO publishes the BLE protocol themselves** — message definitions, COBS framing, and a working
  `bleak` example. Not blog reconstruction. [bluetooth-control-plane.md](../research/bluetooth-control-plane.md)
- **A file can reach a slot over BLE**, and be started, with no cable.
- **Linux works** — `bleak` via `bluetoothd`, no root, BlueZ ≥ 5.55 (this host: 5.64). **Raw Python, no
  SPIKE app**, which also means no chance of the non-dismissible Hub OS update prompt.
- **The caveat that shaped the design:** a program *on the hub* almost certainly cannot open its own BLE
  socket. Telemetry leaves as `print()` and the firmware wraps it — **so the hub side is identical under
  every transport**, which is what made `src/telemetry.py` safe to write before any transport was proven.

### Telemetry widened, and it changed a recommendation

The first schema logged **yaw only**, throwing away five of the IMU's six axes. Now **21 columns**:
pitch/roll (the only confirmation the robot was *flat*, which every odometry assumption depends on),
accelerometer (impacts and stalls — **a wall collision is a spike here and nothing at all in the
encoders**), commanded-vs-achieved motor percent, raw RGB, lane and detector state.

Recomputing throughput against the wider record **overturned the earlier 20 Hz live recommendation**:
89 B typical / 119 B worst, so 20 Hz is 89 % of the modelled BLE ceiling with no allowance for
retransmission. 10 Hz is 45 %. Log-on-hub with a low-rate heartbeat is now the safer default.

### Analysis layer planned, not built

[analysis-detection-quality.md](../plans/analysis-detection-quality.md) and
[analysis-motion-quality.md](../plans/analysis-motion-quality.md) — what to compute, deliberately not
implemented, **because no transport is proven**. Each ends with a small ranked contract for a future
`./data_analysis/`.

---

## Decisions

| Decision | Record |
|---|---|
| One file per device; `hub_*.py` naming **is** the boundary rule | [code-discipline.md](../directives/code-discipline.md) |
| No test suite; no debugger — **minimalism is what replaces both** | [ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md), [../../test_methodology.md](../../test_methodology.md) |
| LibreOffice MCP / `libre_mcp` child project — **deferred and blacklisted** | [scope.md](../scope.md) — the problem it would solve is already solved |
| Report the conclusion, not the transcript | [CLAUDE.md](../../CLAUDE.md) |
| Docs capped at 1200 lines | [documentation-discipline.md](../directives/documentation-discipline.md) |
| Partial-run policy (stop on clock vs finish) — **DEFERRED** with a re-raise trigger | [KU-D9](../plans/known-unknowns.md) |

---

## Defects found and fixed — the audits kept earning their cost

1. **`display_pages()` emitted glyph names that do not exist**, and `show_glyph()` raises on a miss by
   design. **Pages 2 and 3 of the report would have crashed on every single run** — the Builder hears
   the beeps, then the matrix goes dark.
2. **`MAX_FLOOR_MAD` and `MIN_CONTRAST` jointly armed runs at 2.7 σ** when the project's own research
   demands 6 σ — the MAD-vs-stdev confusion, for the third time. Both tightened, **and the structural
   fix added**: `calibrate()` now checks the contrast-to-noise *ratio* directly (`MIN_SNR_MAD = 8.90`),
   so a hand-edit of either absolute constant can no longer silently re-open the gap.
3. **Borenstein's Type A / Type B were stated backwards in three documents.** A sign reversal between
   CW and CCW means *unequal wheel diameters*, not a wrong track width. The runbook would have sent the
   Builder to adjust the one number that was not wrong, fitting one direction and worsening the other.
4. **`Event.width()` was off by one against its own gate** — anyone reading it to work out why an event
   was rejected got a number that did not match the rule rejecting it.
5. **`event_width_gates()` could return an impossible gate** (min > max below ~2 Hz) — the robot would
   sweep the whole arena counting zero with nothing on the matrix to say why. It now raises at DERIVE.
6. **The distance sensor's minimum range conflicts between two LEGO-official sources** — techspec says
   50 mm, the BLE protocol reference says 40 mm. **Use 50**: below the minimum the sensor returns `-1`
   (*nothing detected*), so assuming 40 when it is really 50 means a wall at 45 mm reads as open floor.

---

## The correction that matters most

The operator asked, with alarm, whether I had connected to hardware. **I had not** — and I showed the
evidence rather than asserting it. But I had written *"I measured the actual formatted record"* when I
had measured **the length of a Python string**.

In this project *measured* had come to mean *on the real robot, on the real floor, with conditions
recorded*. I built that vocabulary across two sessions and then broke it in one sentence. The alarm was
the correct response to what I wrote.

Two rules came out of it, both now blacklist-level in [CLAUDE.md](../../CLAUDE.md):

- **"Measured" means real hardware.** Otherwise say *computed* or *confirmed against \<source\>*.
- **Never initiate a hardware connection.** The operator says when something is connected; until then it
  is absent.

[say-which-kind-of-verified.md](../lessons_learned/say-which-kind-of-verified.md)

---

## Late finding — autonomy was never a requirement

The operator asked whether the project requires autonomy. **It does not — and we had been assuming it
did.** "Autonomous" appears **nowhere** in the course instructions (full text checked), and the verbal
briefing says only *"build a mine sweeper robot that finds all the mines."*

`scope.md` § Mission had honestly flagged autonomy as an *inference*. But **FR-1 stated it as a
requirement without the `[ASSUMED]` marker** — an inference hardening into a requirement between two
sections of the same document. That is the same failure class the audits keep catching, found this time
by the operator asking a question none of us had thought to ask.

Corrected: FR-1 now carries the marker, and **Q0 leads the professor list** — ahead of the units question,
because it can remove more of the project than any other answer. If teleoperation is allowed, sweep
planning, odometry accuracy, heading hold and the entire coverage-time problem become optional. Detection
and counting survive either way, and that is the actual engineering problem.

Recorded as [KU-P0](../plans/known-unknowns.md). **A "yes, autonomous" answer costs nothing** — everything
built so far assumes it.

## Telemetry and BLE latency — already handled, one addition

`t_ms` is stamped **on the hub inside the tick**, before the line is queued or framed, so link delay
cannot corrupt it. `seq` preserves transmission order regardless of delivery, and the trailer's `sum_seq`
detects loss including at the very end. The operator's condition — *all telemetry, in transmitted
sequence* — is already met.

Added: **`rx_ms` at the receiver**. `rx_ms − t_ms` measures actual BLE latency for free during a real run,
and separates a transport stall (gap in `rx_ms`, none in `t_ms`) from a robot pause — which are otherwise
indistinguishable. Both clocks recorded, reconciled offline; never corrected live.

## Blockers — unchanged, and both external

1. **The professor's answers.** Q1 (units) × Q2 (scoring) selects the design straight off the trade
   study's decision table; Q3 (boundary) picks which sensor to buy.
2. **Hardware.** Hub never connected, robot not built, motor and wheel types unknown. `config.py` is
   full of `[ASSUMED]` values that one class session replaces.

Also open: the ERAU VPN fails after authenticating (`RTNETLINK answers: File exists` — a route conflict,
not an auth problem), so skytracker has never been reached and docs-rag `/api/ask` stays broken. **Search
works; this blocks nothing.**

---

## What's next

**[first-hardware-session.md](../plans/first-hardware-session.md) is the plan for the moment the hub is
plugged in** — host prep → is it seen → **Hub OS identification (the gate)** → Bluetooth → walking
skeleton → telemetry → measurements, ordered by what blocks what.

Not waiting on hardware, and worth doing first:

1. **Ask the professor** — free, and Q1×Q2 picks the design.
2. **Supplier: buy one colour sensor** — needed under every branch of the decision matrix.
3. **Colour separability go/no-go** — needs the sensor and the real note pack, **not the robot**. If the
   colours do not separate, classification is off the table and the plan changes that day.
4. **Builder: read the part numbers off the two motors** — one fact closes KU-T3.

**Not offered: a git commit.** Milestone-gated and human-only; ask when you want the commands.
