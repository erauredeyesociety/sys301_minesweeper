# ADR-0004 — Flat `src/` supersedes the `mission/` + `hub_io/` package split

- **Date:** 2026-08-25
- **Status:** Accepted
- **Supersedes:** [ADR-0002](./0002-split-mission-logic-from-hub-io.md)
- **Deciders:** Operator

## Context

[ADR-0002](./0002-split-mission-logic-from-hub-io.md) put pure logic in `src/` and hub I/O in
`src/`. Its *goal* — mission logic that imports nothing hub-only, so it runs and is tested on the
laptop while the hub sits in the yellow box — was right and is unchanged.

Its *mechanism* was two Python packages. The operator's judgement (2026-08-25): for a project that will
end up with well under a dozen modules, two package directories with `__init__.py` files and relative
imports is ceremony that buys nothing. It also costs something real on this platform — MicroPython
package handling is one more thing to be surprised by on a hub whose API generation we have not yet
identified.

## Decision

**One flat `src/` directory.** No packages, no `__init__.py`, no relative imports — modules import each
other by plain name (`import config`).

**The purity rule survives intact and is what actually mattered:** a module that holds mission logic
imports **nothing hub-only** — not `hub`, `motor`, `motor_pair`, `color_sensor`, `distance_sensor`,
`force_sensor`, `motion_sensor`, or `runloop`. Hub access is confined to modules that exist to do it,
and those are the only ones that cannot run on the host.

| Module | Pure? | Purpose |
|---|---|---|
| `config.py` | yes | Every tunable in one place |
| `calibration.py` | yes | Run-start threshold derivation, polarity detection |
| `detector.py` | yes | Hysteresis edge-counting state machine |
| `sweep.py` | yes | Boustrophedon lane state machine, emits commands |
| `result.py` | yes | Result model and its accounting invariant |
| `odometry.py` | yes | Encoder/gyro pose arithmetic |
| `sensors.py` | **no** | The hub-facing adapter — the only LEGO API caller |

## Consequences

- **Enforcement — amended 2026-08-25.** This ADR originally named a floor test in `tests/persistent/` as
  the boundary guard. The operator then removed `tests/` entirely (see below), so the guard is now a
  **one-line grep** any session can run, and it is the honest replacement rather than a pretence:

  ```bash
  grep -nE '^\s*(import|from)\s+(hub|motor|motor_pair|color_sensor|distance_sensor|force_sensor|motion_sensor|runloop|spike)\b' \
    src/*.py | grep -v '^src/sensors.py'
  ```

  Empty output means the boundary holds. Any line of output is a violation. It costs nothing, needs no
  framework, and — because `python3 -c "import detector"` on the host fails loudly the moment a pure
  module reaches for a hub name — the boundary also breaks visibly during ordinary development.
- Fewer files, no `__init__.py`, no relative-import behaviour to verify on MicroPython.
- Running on the host needs `src/` on the path (`cd src`, or `sys.path.insert`). On the hub, files are
  flat in a slot, which is closer to how the hub actually stores programs.
- **Risk accepted:** a flat namespace makes it easier to accidentally import a hub module into a pure
  one, because there is no directory boundary to notice you crossing. The grep above is the mitigation.
  It is weaker than a test that runs automatically — nobody is forced to run it — and that weakening is
  a deliberate, operator-approved trade against carrying test infrastructure on a project whose real
  verification is a robot moving on a floor. See [ADR-0005](./0005-no-test-suite-verify-on-hardware.md).
