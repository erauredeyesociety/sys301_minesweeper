# ADR-0005 — No test suite; verification happens on the robot

- **Date:** 2026-08-25
- **Status:** Accepted
- **Deciders:** Operator
- **Amends:** [ADR-0004](./0004-flat-src-supersedes-package-split.md) · supersedes the testing tier in
  [directives/testing-discipline.md](../directives/testing-discipline.md)

## Context

The project standards carried from `~/llm-project-bootstrap/` prescribe a small protected regression
floor in `tests/persistent/`. That floor was planned and never written.

The operator's judgement (2026-08-25): *"the system will be tested on the SPIKE itself and we will look
at visual performance in the real world… this is such a simple system that we don't need any test
scripts."*

That is a defensible read of this specific project:

- The deliverable is a robot demonstrated on 10 SEP. Nobody grades the test suite.
- The failure modes that will actually bite — heading drift, a note missed at a lane edge, a threshold
  wrong for the real carpet, a motor slipping — are **all physical**. No host-side test reaches any of them.
- The pure logic is about 500 lines of arithmetic and one state machine, most of it already exercised by
  hand against known-answer cases during development.
- Test infrastructure has a carrying cost — writing, running, maintaining — paid out of five class
  sessions.

## Decision

**No `tests/` directory and no test framework.** `tests/` is deleted.

Verification is:

1. **The Python interpreter itself** — a module that does not import is broken, loudly and immediately.
2. **Hand-checked known-answer runs during development** — e.g. a synthetic reflectance stream with a
   deliberate mid-note dropout must count 2, not 3. Recorded in the session record when run, so the
   claim is traceable.
3. **The robot on the floor**, which is the only thing that can verify the parts that matter.
4. **The verification plan** ([../plans/verification-plan.md](../plans/verification-plan.md)) remains the
   requirement-by-requirement record. Its "host-side" column now means *hand-checked*, not *automated*.

## Consequences

- **What is genuinely lost:** silent-regression protection. A change that quietly breaks the edge counter
  will not announce itself; it will show up as a wrong count on the floor, where debugging costs a class
  period instead of a second. **This is the real cost and it should not be glossed over** — it is
  accepted because the alternative spends scarce class time on a project this small.
- The `src/` purity boundary is now guarded by a grep, not a test — see ADR-0004's amended enforcement.
- The bootstrap testing directive no longer applies to this project. Its rule *"never delete a floor test
  to make a change pass"* is moot: there is no floor. Recorded here rather than silently ignored.
- **Telemetry becomes the substitute for observability.** If we can stream encoder, gyro, and sensor
  samples off the hub, offline analysis of a real run replaces what a test would have told us — and it
  tells us about the physical world, which a test never could.
  See [../plans/telemetry-and-analysis.md](../plans/telemetry-and-analysis.md).

## What would reverse this

A regression we actually pay for twice. If the same logic bug reaches the floor a second time, one small
host-side check for that specific behaviour is worth its cost — and that is a new ADR, not a quiet
re-introduction of a suite.
