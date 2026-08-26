# ADR-0001 — Stock LEGO firmware only; Pybricks permanently blacklisted

- **Date:** 2026-08-25
- **Status:** Accepted
- **Deciders:** Operator

## Context

The hub is a LEGO Education SPIKE Prime Technic Large Hub (45601) belonging to the course. We develop
on native Ubuntu 22.04, which LEGO does not list as a supported desktop platform — its supported
desktop OSes are Windows and macOS, plus ChromeOS/Android/iOS, with a browser-based web app.

Pybricks is the most Linux-friendly route to programming this hub and is genuinely well supported.
It also **flashes its own firmware onto the hub**, replacing LEGO's, with a separate restore procedure.

## Decision

**The hub keeps its factory LEGO firmware. Pybricks and every other third-party firmware are
permanently blacklisted.** No DFU, no bootloader, no filesystem format, no factory reset. A LEGO Hub
OS update — which stays on LEGO firmware — is a *separate* decision that requires an explicit operator
call recorded as a new ADR; it is never accepted as a side effect of opening a tool.

## Consequences

- We are limited to what the stock firmware exposes: the hub's built-in MicroPython, reached over USB
  serial or through LEGO's own app/web app.
- Some community tooling targets older Hub OS generations and may not work. We identify the installed
  Hub OS **read-only, before** using any tool that could prompt for an update
  ([../runbooks/hub-identification.md](../runbooks/hub-identification.md)).
- We accept a rougher Linux developer experience in exchange for returning the hub in factory state.
- Pybricks stays documented as *excluded and why*, so nobody re-proposes it in week two.

## Why not the alternative

Flashing Pybricks would give a better toolchain, and it is reversible on paper. But the hub is shared
course equipment, a failed restore ends the project, and the operator set this constraint explicitly.
The cost of the constraint (developer friction) is bounded; the cost of violating it is not.
