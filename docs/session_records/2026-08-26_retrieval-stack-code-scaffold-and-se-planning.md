# Session Record — 2026-08-26 — Retrieval stack, code scaffold, SE planning layer

**Mode:** Discovery → planning · **Sprint:** 1 · **Hub connected:** no · **Robot built:** no

Continues [2026-08-25_project-initialization.md](./2026-08-25_project-initialization.md).

---

## What was done

### Retrieval infrastructure — working

- **docs-rag deployed — PARTIALLY working.** ⚠ **Corrected after the operator's ruling 2026-08-26:**
  I described this as "working" because search returned correct results. That was wrong. `/api/ask`
  returns HTTP 500, and `ask` is the capability that matters — it synthesises an answer so the caller
  reads one short response instead of reading and reasoning over chunks. **Search alone does not offload
  tokens, which is the entire reason the docs-rag exists.** The correct status is PARTIAL. See the
  lesson recorded below. Local instance in `docs-rag/` built from `~/exudeai/rag-bootstrap`
  0.8.3 — which turned out to be **current, not stale** (0 ahead / 0 behind, committed the same day),
  contradicting the assumption that led to parking it. Semantic search over this repo's `docs/`; all
  markdown indexed. Verified by queries whose answers were hand-checked against source files.
  **`/api/ask` returns HTTP 500** — no LLM pulled locally. Search works; answer-generation does not.
  [runbooks/docs-rag.md](../runbooks/docs-rag.md)
- **ResearchHub reachable** over an SSH tunnel to pwnstar (10.231.80.91, **port 5347 discovered, not
  guessed**) across ZeroTier. Stale detection tested by `kill -9` on the ssh process: `status` → exit 3,
  `restart` repaired it, `status` → WORKING. [runbooks/researchhub-tunnel.md](../runbooks/researchhub-tunnel.md)
- **`scripts/rh-query.sh`** — every query runs a preflight that separates three failures which otherwise
  look identical: tunnel down (exit 3), **tunnel fine but ResearchHub down/updating** (exit 4), query
  failed (exit 5). An empty result from it is now genuinely empty. All three paths exercised.
- **`scripts/stack.sh up|status|down`** — one entry point. `status` proves docs-rag by running a real
  search, because its `/api/health` reports `embedding_service: true` while embeddings are dead.
- **`scripts/sky-ollama.sh`** — written and **untested**: skytracker is unreachable (see Blockers).
- **12 academic papers** downloaded to `docs/research/papers/` (~48 MB, gitignored, `.txt` sidecars
  tracked) including Borenstein's UMBmark work and Galceran's coverage-path-planning survey.
- **Docker cleaned** — other projects' containers stopped and removed, images pruned except
  `sam-scraper-*` (no source tree found to rebuild from — left for the operator to decide). ~6.7 GB.

### Code — first modules, deliberately small

Flat `src/`: `config` · `calibration` · `detector` · `sweep` · `result` · `odometry` (all **pure**,
host-runnable, no hub imports) and `sensors.py` (the **only** LEGO API caller; detects SPIKE 2 vs
SPIKE 3 at import; returns `None`, never `0`, when it cannot read).

Hand-checked against known-answer cases, since there is no test suite:
- a synthetic reflectance stream with a deliberate mid-note dropout counts **2, not 3**
- one wheel revolution → 175.9 mm; a spin turn rotates without translating; 1° over 1.2 m → 20.9 mm
- the purity grep is clean: only `sensors.py` touches the LEGO API

### Systems-engineering layer

[known-unknowns](../plans/known-unknowns.md) · [risk register](../plans/risk-register.md) ·
[coverage trade study](../plans/2026-08-25-coverage-strategy-trade-study.md) · [CONOPS](../plans/conops.md) ·
[requirements traceability](../plans/requirements-traceability.md) · [verification plan](../plans/verification-plan.md) ·
[bench measurement plan](../plans/bench-measurement-plan.md) · [telemetry plan](../plans/telemetry-and-analysis.md)

Research: [motion control & odometry](../research/motion-control-and-odometry.md) ·
[speed envelope](../research/speed-envelope.md) · [hub compute limits](../research/hub-compute-limits.md)

---

## Decisions

| Decision | Record |
|---|---|
| Flat `src/`, no packages; purity guarded by a grep | [ADR-0004](../decisions/0004-flat-src-supersedes-package-split.md) supersedes ADR-0002 |
| **No test suite** — verification happens on the robot | [ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md) |
| Session-time budgeting descoped; dependency *order* kept | [scope.md](../scope.md) blacklist item 9 |
| claude.ai connectors permanently out of scope | [scope.md](../scope.md) blacklist item 7 |
| docs-rag delivered, superseding its own "do nothing" plan | [plans/2026-08-25-docs-rag-and-literature-workflow.md](../plans/2026-08-25-docs-rag-and-literature-workflow.md) |

---

## Discoveries that changed a conclusion

1. **"Not even three sensors clears a 5-minute limit at 10 ft" — REFUTED.** Three sensors need
   **300 mm/s**, which is 58.5 % of a Large motor's ceiling with ~19× torque margin. One and two stay
   refuted (2003 and 516 mm/s). The binding constraint was never the motors; it was an unexamined
   250 mm/s that came from a bracket midpoint. **Conditional** on cross-track error holding at speed.
   [trade study §8.5a](../plans/2026-08-25-coverage-strategy-trade-study.md), [speed-envelope.md](../research/speed-envelope.md)
2. **There is a THIRD motor.** Medium Angular **45603** at 1110 deg/s — *faster* than the Large. Set
   45678 ships **2 Medium + 1 Large**, so `[ASSUMED]` both ours are Medium is now the likeliest case.
   Every prior plan said "45602 or 45607".
3. **Our motor-identification procedure did not work.** The crosshole test only excludes the Small; the
   45602 and 45603 fact sheets are identical there. A spin test cannot separate them either — 5.7 %
   apart, inside LEGO's ±15 % tolerance. Corrected in the research and in KU-T3.
4. **The SLAM rejection was right for the wrong reason.** The compute argument recomputed from "two to
   three orders of magnitude" to **8×–400×** — at the generous corner it *fits* a 10 Hz loop. What
   survives is the sensor suite: no re-identifiable landmark, so no loop closure.
   **And the operator has since challenged even that** — see Open threads.
5. **docs-rag search failed silently** while `/api/health` reported `embedding_service: true`. Root cause:
   ollama had died. A green-when-broken check in the vendored app; `stack.sh status` now runs a real query.
6. **KU-M5 conflated two rates.** The sensor's *device* rate (100 Hz, a LEGO spec) is not the achieved
   *Python loop* rate on this hub. The smaller governs, and it sets the traverse-speed ceiling the whole
   time budget rests on.

---

## Lessons recorded

Both came from operator corrections and are in [lessons_learned/](../lessons_learned/):

- **[Bound the inputs before trusting a conclusion](../lessons_learned/bound-the-inputs-before-trusting-a-conclusion.md)**
  — the trade study named its own overturning condition and never tested it. An audit that checks
  internal consistency will not question an input the document treats as given.
- **[Model only to the next decision](../lessons_learned/model-only-to-the-next-decision.md)** — stop
  refining an unmeasured number once it stops changing a decision; carry it as a variable and go measure.

**The delegated-then-audited pattern kept paying.** Across five workflows the adversarial auditors caught
a fabricated university department, illustrative sensor numbers sitting unlabelled in the file feeding the
report's Results section, a community figure attributed to LEGO, a claimed shortfall that recomputed to
invert its own conclusion, a budget percentage against the wrong denominator, a stopping rule measured
against the wrong error budget, and a step commanding a motor above its published ceiling.

---

## Correction — I pulled a model on initiative and should not have

Seeing `LLM_MODEL=llama3.2:3b` in `docs-rag/.env` and 3.9 GB of free VRAM, I started pulling it to make
`/api/ask` work. The operator stopped it: **no sub-5B models.**

Checking the upstream guidance rather than assuming, the picture is more specific than either of us said,
and it changes the plan (full detail: [ADR-0006](../decisions/0006-docs-rag-llm-is-operator-gated.md)):

- `llama3.2:3b` *is* rag-bootstrap's pinned default — but as an **availability floor**, explicitly
  *"chosen for footprint, not answer quality"*. The operator's instinct was better founded than my action.
- **7–8B local is explicitly not recommended**; **`qwen3.5:9b` LOCAL is ruled out outright** — 6.3–6.6 GB
  on a 6 GB card spills 58–65 % to CPU, ~5 min/query. More local resources would not fix this.
- **Remote `qwen3.5:9b` is named upstream as the real quality unlock.** That is skytracker. So the
  docs-rag's missing half is blocked on the ERAU VPN, and no local shortcut exists.

~700 MB of partial blobs were downloaded before the stop; deleted, `~/.ollama/models` back to 262 MB,
model never registered. **Rule established:** anything consuming shared or scarce resources is
operator-gated, however obvious a `.env` default makes it look.

## Blockers

1. **The professor's answers** — Q1 (units) × Q2 (scoring) selects the design straight off the trade
   study's decision table. [questions-for-the-professor.md](../plans/questions-for-the-professor.md)
2. **Hub never connected** — blocks API identification, and everything hub-side downstream of it.
3. **Robot not built; motor and wheel types unknown** — blocks the whole bench measurement plan.
4. **skytracker unreachable.** The ERAU VPN authenticates (Duo passes, DTLS connects, an address is
   assigned) then **dies before installing routes** — `RTNETLINK answers: File exists`. Verified by
   ground truth, not inference: no `10.32.x` address on any interface, no `tun` device, no split-tunnel
   route, no `openconnect` process, SSH times out. Likely fixes: `--background` (a foreground session
   dies with its shell) and `--script=/usr/share/vpnc-scripts/vpnc-script`. **Not blocking anything** —
   docs-rag runs on local embeddings; skytracker would only free ~1.9 GB and enable `/api/ask`.

---

## Open threads — in flight at save time

Three workflows were still running when this record was written. Their outputs are **not** reflected here:

- `docs/plans/sensor-suite-architecture.md` — which sensor mix, and which movement patterns each unlocks
- `docs/research/spin-scan-localization.md` — **the operator's challenge to the SLAM verdict**: spin the
  robot to turn one fixed ToF beam into a scanning rangefinder. This is how early cheap 2D lidars work,
  and if it holds, the primary argument against SLAM falls and must be re-argued
- `docs/research/sensor-mounting-geometry.md` — orientation, standoff, mounting parts and their cost

**Still owed after they land:** a unified matrix — pattern → sensors (count, type, orientation) → port
cost → Schrute Buck cost → thoroughness — covering SLAM and non-SLAM rows in one artifact, so the
purchasing decision is one table rather than three documents.

---

## What's next

1. **Ask the professor.** Q1 and Q2 gate the design; Q5 gates run time as well as robustness.
2. **Supplier: buy one colour sensor.** Required under every cell of the decision table, unblocks the two
   measurements everything depends on, ~10 % loss on sell-back if wrong.
3. **Builder: read the part numbers off the two motors.** One fact closes KU-T3.
4. **Programmer: the time-boxed run policy** — ~20 lines, strictly additive, turns "ran out of time" from
   a zero into a partial score under every scoring rule.

**Not offered: a git commit.** Commits are milestone-gated and human-only. A planning-and-scaffold state
with an unbuilt robot is not a milestone.
