# Roadmap and Plans

**Purpose.** The roadmap is the strategic *what*; plans are the tactical *how*. Keep them apart or the
roadmap rots into a spec dump nobody reads.

- **[../roadmap.md](../roadmap.md) is ONE lean file, hard-capped ~40 lines** — milestone bullets plus
  short path refs. NEVER design specs, findings, or inline plans. If a bullet needs a paragraph, it
  belongs in a plan.
- **Plans live in [../plans/](../plans/)**, tagged `ACTIVE-SPEC` or `FORWARD-PLAN` in that folder's
  `INDEX.md`. The roadmap points at one by a single line. **Naming — settled 2026-08-25:**
  a *point-in-time* plan (a sprint plan, a trade study, a one-off proposal) is dated
  `YYYY-MM-DD-<slug>.md`, because when it was written is part of what it means. A **living document**
  that is continuously updated (`known-unknowns.md`, `risk-register.md`, `conops.md`,
  `verification-plan.md`, `requirements-traceability.md`, `questions-for-the-professor.md`) is named by
  **concept only** — a date in the filename of a document that never stops changing is date-noise and
  invites a dated near-duplicate later. This resolves the apparent conflict with
  [documentation-discipline.md](./documentation-discipline.md); both rules stand, applied by lifetime.
- **Milestones here are calendar-anchored** because the course is: Sprint 1 (27 AUG) · Sprint 2 (1–8 SEP)
  · Demo Day (10 SEP) · Journal + peer review (15 SEP) · Report (18 SEP). Sequence by *what Demo Day
  needs*, not by what is most interesting.
- **Delivered plans move to [../archives/plans/](../archives/plans/)**; the outcome is narrated once in
  a session record, not re-narrated in the archive.
- **Promote vetted ideas yourself.** A new idea earns a roadmap slot after a retrieval pass and a plan
  artifact. Don't leave a vetted idea as a loose note; don't wait to be told.
- **Re-sequence most-impactful-first** when a milestone is added — state the reason in one line, never
  silently shuffle.
- Distinct from [plan-first.md](./plan-first.md), which is *execution* discipline.
