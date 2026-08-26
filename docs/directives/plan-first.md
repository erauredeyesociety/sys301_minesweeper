# Plan First

**Purpose.** "Try something → see what happens → try the next thing" is how a two-week hardware
project burns its only two sprints. Plan the wave, then execute it.

- **Plan before you build or dispatch.** Write the numbered plan into a `docs/plans/` artifact first;
  every action maps to a numbered item. No agent runs without a line in the plan it advances.
- **Build the walking skeleton first.** Thin end-to-end slice through the REAL components —
  Ubuntu editor → hub → motor turns → output read back — before any mission logic. On a hardware
  project the integration unknowns are the whole risk, and they only surface on real hardware.
  See [../plans/2026-08-25-sprint-1-walking-skeleton.md](../plans/2026-08-25-sprint-1-walking-skeleton.md).
- **Ground the plan in retrieval.** Check `docs/research/` and `docs/findings/` before planning from
  assumption. Cite by path; don't recopy prose.
- **Give every delegated brief four things:** objective, output format, tool/source guidance, exclusive
  write paths. Overlapping write zones get rewritten before dispatch, not after.
- **"Act first, maximum speed" applies only AFTER the plan and question phases** — keep the autonomy,
  gate it.
- **Hardware plans include what happens when it doesn't work.** A plan step that can only be verified
  on the hub names the observable that proves it (a specific reading, a specific motion), not "check
  that it works".
