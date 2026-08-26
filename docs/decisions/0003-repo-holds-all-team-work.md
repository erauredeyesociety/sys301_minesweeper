# ADR-0003 — This repo holds all team work, including graded course deliverables

- **Date:** 2026-08-25
- **Status:** Accepted
- **Deciders:** Operator

## Context

SYS 301's intro project is graded mostly on artifacts that are *not* code: a daily journal (80 pts),
a mid-project survey (20 pts), peer evaluations (50 pts), a full record of team communications, and a
CSER-format Intro Report. The robot itself is demonstrated, not submitted.

The alternative was keeping code here and course write-ups in Word/Google Docs.

## Decision

**Everything lives here** — robot software, systems-engineering artifacts, the hardware/build record,
and the graded course deliverables under `docs/course/`.

## Consequences

- The Intro Report gets written **from** the repo: measurements from `docs/findings/`, rationale from
  `docs/decisions/`, narrative from `docs/session_records/`. No reconstructing three weeks from memory
  on 17 SEP.
- Journal entries are drafted here and transcribed to whatever the class requires; the daily entry is
  handwritten in class per the example provided, so the repo copy is the durable record, not the
  submission itself.
- The report's **submitted artifact is a Word file** on the CSER 2022 template — markdown here is the
  draft, not the deliverable. Don't confuse the two.
- Physical/mechanical design is recorded, not designed, here (operator's call) —
  see [../hardware/INDEX.md](../hardware/INDEX.md).
- Team communications must be collected in full for submission; the repo is where we keep the pointer
  and the policy, but Discord/email remain the system of record.
