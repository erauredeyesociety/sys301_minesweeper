# Budget — the Schrute Buck ledger

**The single source of truth for the team budget.** Everything the Supplier spends, sells back, or is
fined is recorded in the table below, and the Intro Report's §6 *Budget & Resource Management* is written
from it.

> **Only the Supplier may buy, sell, or handle money** (course instructions, p.1). This file records the
> outcome; it does not make the purchasing decisions. Anyone may read it; the Supplier maintains it.

## The ledger

*Last updated 2026-09-08. All figures in Schrute Bucks (SB).*

| Date | Description | Qty | Unit | Amount | Balance |
|---|---|---:|---:|---:|---:|
| | Starting budget | | | | **100** |
| 2026-08-25 | Motors | 2 | 10 | −20 | 80 |
| 2026-08-25 | Wheels | 2 | 7 | −14 | 66 |
| 2026-08-25 | Project budget reallocation | 1 | 10 | −10 | 56 |
| | **Total spent** | | | **−44** | **56** |

**Balance: 56 SB.**

## What the ledger says, in words

- **Two prices have ever been observed in this project:** **motor 10 SB** and **wheel 7 SB**, both on
  2026-08-25. Nothing else has a recorded price, and **there is deliberately no price list in this repo**
  — store prices may change during the project ([../scope.md RR-5](../scope.md#resource-rr)), so each
  entry records the price *actually paid* on that date, never a quoted list price.
- **No sensor has been bought.** The ledger shows 2 motors and 2 wheels and nothing else — no colour
  sensor, no distance sensor, no mounting blocks, no axles.
- **The 10 SB "Project budget reallocation" on 2026-08-25 is unexplained** — 23 % of everything spent.
  It is [KU-T6](../plans/known-unknowns.md) and still `OPEN`. The report's resource section has to
  account for it, and if it turns out to be reversible it is 10 SB back toward a sensor. Ask the
  Supplier; do not guess in writing.

## How to update it

Add a row, work the running balance down the column, update the **Total spent** row and the **Balance**
line, and change the *Last updated* date. Keep the date, quantity, unit price and amount exactly as the
Supplier reports them.

**Sell-back pays 90 % of the *listed* price, rounded down** (course instructions, p.1) — so a wrong
purchase is a permanent ~10 % loss. Compute it as `floor(price * 0.9)` and record the amount actually
received. **Role violations cost −2 SB each**, and face-to-face beyond the daily 5-minute standup costs
**1 SB per person per minute**; both are ledger entries when they happen
([team/roles.md](./team/roles.md), [team/communications.md](./team/communications.md)).

**One ledger only.** Two ledgers disagree the moment one is edited alone, and the disagreement surfaces
when the Supplier tries to buy something
([../directives/honest-instrumentation.md](../directives/honest-instrumentation.md): one accountable
path per concern). Do not copy the amounts into another document — link here instead.

## Provenance

From project start until **2026-09-08** this ledger was a Python script, `inventory.py`, in the repo root
(`./inventory.py`, `--verbose` for a full statement), with the entries in an `ENTRIES` list and a
`sellback()` helper for the 90 % rounding. The operator deleted it on 2026-09-08 — a script is
unnecessary for a four-line ledger — and the table above is its final state, captured immediately before
deletion. **The script and its full history remain recoverable from git history** if the derivation of
any figure is ever questioned.

## Related

- [deliverables.md](./deliverables.md) — the full graded calendar; the budget is not separately scored but funds the robot
- [report/outline.md](./report/outline.md#6-budget-and-resource-management--writable-now) — §6 of the Intro Report, fed by this file
- [../plans/purchasing-strategy.md](../plans/purchasing-strategy.md) — the reserve floor, the spendable amount, and what to buy first
- [../plans/known-unknowns.md](../plans/known-unknowns.md) — KU-T5 (store prices), KU-T6 (the reallocation line)
- [../hardware/build-record.md](../hardware/build-record.md) — what the parts physically are, once someone looks at them
