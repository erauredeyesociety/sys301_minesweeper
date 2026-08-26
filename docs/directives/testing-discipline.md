# Testing Discipline — SUPERSEDED FOR THIS PROJECT

> **⚠ Read [ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md) first.** The operator
> removed `tests/` on 2026-08-25: this system is verified on the SPIKE itself by observed behaviour, not
> by a host-side suite. **There is no `tests/` directory and no test framework.**
>
> What replaces it: the Python interpreter (a module that will not import is broken, loudly);
> hand-checked known-answer runs recorded in the session record; the `src/` purity grep in ADR-0004; the
> robot on the floor; and — once the hub is connected — telemetry plus offline analysis
> ([../plans/telemetry-and-analysis.md](../plans/telemetry-and-analysis.md)).
>
> The cost is accepted and named in ADR-0005: no silent-regression protection. The text below is the
> upstream standard, kept for the report's process discussion and for any future project. **Do not
> re-introduce a suite here without a new ADR.**

---

# Testing Discipline

**Purpose.** A tiny permanent floor forever; everything else is scaffolding. On a hardware project the
split is sharper than usual: **logic gets tests, hardware gets diagnostics.**

| Tier | Location | Lifetime | Needs the hub? |
|---|---|---|---|
| **Protected floor** | `tests/persistent/` | Permanent | **No** |
| **Throwaway spikes** | `tests/` top level | Deleted once they answer their question | No |
| **Diagnostics** | `scripts/` — *not tests* | Permanent, run by hand | **Yes** |

## 1. The protected floor — `tests/persistent/`

Small, fast, deterministic, host-side, **no hub required**. Covers `src/` only — exactly what
[ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md)'s split buys us. **Target ~3–7 tests:**

| Test | What it pins down |
|---|---|
| Edge-counting state machine | A synthetic reflected-light sequence in → the correct count out; hysteresis and minimum-dwell actually reject the noise they exist to reject |
| Calibration / threshold math | Thresholds derived from a floor sample are sane and ordered (`low < high`); degenerate input (zero contrast) is handled, not turned into a threshold that fires forever |
| Sweep state machine | Lane → turn → next lane, boundary handling, end-of-run; each lane visited exactly once, which is what makes double-counting structurally impossible |
| **Import boundary** | `src/` imports nothing hub-only |

The first three are the **must-not-break paths** tagged in [../roadmap.md](../roadmap.md) § M2.

**The fourth test IS the architecture boundary**, not a style check. It is the only thing standing between
us and a `src/` that quietly stops importing on a laptop — at which point every other floor test
becomes un-runnable without the hub and the whole reason for the split evaporates.

**Prefer invariants over snapshots.** "A target never seen is never counted", "the count never decreases",
"N clean pulses produce exactly N" — these survive threshold tuning. A golden file does not, and one that
must be regenerated after every re-tune tests nothing.

## 2. Throwaway spikes — top level of `tests/`

Scratch tests answering one question ("does this debounce idea reject a double-bounce?"). **Delete once
answered.** Promote at most ONE assertion into the floor, and only for a must-not-break path.

## 3. Anything needing the hub is a DIAGNOSTIC, not a test

It lives in `scripts/`, has an explicit timeout, and asserts a known-correct observation. It cannot be
deterministic and cannot run in the loop — it depends on the hub being present, charged, connected,
correctly wired, on a particular floor, under particular lighting. A "test" whose outcome depends on
whether someone plugged in a USB cable will be skipped-to-pass the first time it is inconvenient, and a
check that can be skipped to pass is worse than no check at all.

**A diagnostic never replaces a floor test, and a floor test never pretends to cover the hardware.** The
floor proves the *algorithm* is right; only the robot on the arena proves the *robot* is right. Neither
claim substitutes for the other, and neither may be reported as the other
([honest-instrumentation.md](./honest-instrumentation.md)).

## Rules

- **NEVER delete, skip, or loosen a floor test to make a change pass.** A red floor test is a code fix or
  an explicit operator sign-off to change the spec. There is no `@skip` that is "temporary".
- **No coverage targets, ever.** A coverage number would push us toward testing `src/` — the code
  we deliberately keep too thin to be worth testing.
- **No load or stress tests.** The robot runs for two minutes on a classroom floor.
- `tests/results/` and `tests/outputs/` are gitignored; `tests/persistent/` stays tracked.
- Run the impacted subset in the loop (`pytest -k`); run the whole floor — it's tiny — at feature boundaries.
- **The floor gets written WITH the first mission logic.** Not before (nothing to test, mission PENDING),
  not "after the sprint" (that is how it never gets written). Nothing in it needs the hub, so **the floor
  is writable and green before the hub is ever connected.** That is the point.
