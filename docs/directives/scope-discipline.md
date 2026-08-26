# Scope Discipline

**Purpose.** Boundaries before building. The exclusion list is what stops a two-week course project
from dying in a dead end.

- **ONE file:** [../scope.md](../scope.md). Do not split it. This project is nowhere near
  policy-heavy enough to earn a `docs/scope/` folder.
- **The BLACKLIST is enforced, not deferred.** Third-party firmware, hub DFU/reset, unattended Hub OS
  updates, git mutations by agents, and fabricated results are permanently out — see
  [../scope.md § PERMANENTLY Out of Scope](../scope.md#permanently-out-of-scope-blacklist--enforced-not-deferred)
  and [hardware-safety.md](./hardware-safety.md). The canonical statement is mirrored in `CLAUDE.md`.
- **The mission is PENDING and that is a scope fact, not a gap to fill.** Do not invent the design
  challenge. Do not build to the working assumption without labelling it `[ASSUMED]`. When the
  briefing lands, rewrite the section and re-derive the requirements — don't bolt the real mission
  onto the guessed one.
- **Current-focus distractions** — in-bounds eventually, a distraction now: target *mapping* (vs
  counting), mechanical redesign, any simulator, and report prose before the robot works.
- Re-read scope before adding a capability. If it isn't in scope, ask the operator — scope is theirs.
