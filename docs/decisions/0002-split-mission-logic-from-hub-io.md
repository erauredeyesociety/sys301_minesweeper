# ADR-0002 — Split pure mission logic from hub I/O

- **Date:** 2026-08-25
- **Status:** Accepted
- **Deciders:** Operator (via project standards), Claude
- **Superseded by:** [ADR-0004](./0004-flat-src-supersedes-package-split.md) (2026-08-25) — the
  *mechanism* (two packages) was replaced by a flat `src/`. **The goal below is unchanged and still
  binding:** mission logic imports nothing hub-only and runs on the host. Only the directory layout moved.

## Context

Everything interesting in this robot — deciding a target is present, debouncing the signal, counting
without double-counting, tracking sweep state — is *logic*. Everything hard to test — motors, sensors,
timing, the hub itself — is *I/O*.

If they are interleaved, nothing can be tested without the hub physically connected. The hub is only
available in class, class time is the scarcest resource in the project, and a bug found on the robot
costs an order of magnitude more than the same bug found on a laptop.

## Decision

Two layers, with a hard import boundary:

- **`src/` — pure logic.** Plain Python. **No imports from `hub`, `motor`, `motor_pair`,
  `color_sensor`, `runloop`, or anything else that only exists on the hub.** Takes readings in as
  numbers, returns decisions out. Importable and runnable on Ubuntu with no hardware.
- **`src/` — thin adapter.** The only place that touches the LEGO API. Reads sensors, drives
  motors, shows state on the light matrix, and hands plain numbers to `mission/`. As close to zero
  logic as we can keep it.

The permanent test floor in `tests/persistent/` covers `src/` only, on the host. Anything
requiring the hub is a **diagnostic** in `scripts/`, not a test.

## Consequences

- We can develop and verify the counting logic with the hub in the yellow box.
- The floor tests are fast, deterministic, and survive tuning — they are the must-not-break paths.
- Small cost: passing readings across the boundary instead of reading sensors inline. Worth it.
- A second benefit for the report: the counting algorithm can be described and its behaviour
  demonstrated independently of the hardware.
- **Enforcement:** a floor test asserts that `src/` imports nothing hub-only. If that test
  goes red, the boundary has been breached — fix the code, don't loosen the test.
