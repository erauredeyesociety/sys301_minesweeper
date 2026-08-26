# Hardware — INDEX

The **record** of the physical robot: which device is on which hub port, what the team actually built,
and what it cost. Written down so the code, the report, and the next class session all agree.

> ⚠ **This folder is a RECORD, not a design space.** The **Designer** designs the solution and the
> **Builder** assembles it; the operator explicitly deprioritized mechanical design in this repo
> ([../scope.md § Out of Scope](../scope.md#out-of-scope-deliberate-exclusions--may-revisit)).
> **Do not start designing a chassis, a gearbox, or a sensor bracket here.** We describe what exists,
> in enough detail that the code is correct and the Intro Report is writable. Nothing more.

## Files

| File | Purpose |
|---|---|
| [port-map.md](./port-map.md) | **Single source of truth** for hub port assignments. Scope [TR-5](../scope.md#technical-tr): the code reads this, it does not scatter port literals. |
| [design-description.md](./design-description.md) | **Start here.** The design in plain sentences — proposed vs resulting, side by side. No brick inventory: *"the colour sensor is mounted flat, facing down, near the front"* is the right altitude |
| [build-record.md](./build-record.md) | Skeleton the operator fills in by describing the build: drive configuration, sensor mounting, wheel geometry, photos. |

## Budget — the ledger is a script, not a document

The live Schrute Buck ledger is **[`inventory.py`](../../inventory.py) in the repo root**, and it is the
single source of truth for the budget.

```bash
./inventory.py            # current balance, one line
./inventory.py --verbose  # full statement: every entry, running balance, total spent
```

Purchases, sell-backs, meeting charges, and role-violation fines are recorded by editing the `ENTRIES`
list at the top of that file. Sell-backs pay 90 % of listed price rounded down — use the `sellback()`
helper so the rounding is done the same way every time.

**There is deliberately no markdown budget table in this folder.** Two ledgers disagree the moment one
of them is edited alone, and the disagreement surfaces when the Supplier tries to buy something
([../directives/honest-instrumentation.md](../directives/honest-instrumentation.md): one accountable
path per concern). If you need a budget table in the Intro Report, generate it from
`./inventory.py --verbose` at the time of writing.

**Only the Supplier may buy, sell, or handle money** (course instructions, p.1). This repo records the
outcome; it does not make the purchasing decisions.

## Parts owned as of 2026-08-25

**2 x motor** and **2 x wheel**, plus a project budget reallocation paid to the professor. Run
`./inventory.py --verbose` for the amounts and the running balance — per the rule above they are
deliberately not copied into this folder. Exact part numbers, wheel diameter, and motor size are
**NOT YET RECORDED** — the operator supplies them into [build-record.md](./build-record.md).

No sensor has been purchased. The three the course offers are Color 45605, Distance 45604, and
Force 45606 ([../scope.md RR-3](../scope.md#resource-rr)); their published specifications are already
researched in [../research/detection-and-sweep-techniques.md](../research/detection-and-sweep-techniques.md).

## Related

- Why the port map has to be authoritative: [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md), [../directives/code-discipline.md](../directives/code-discipline.md) ("no magic numbers")
- Hub firmware constraints: [../decisions/0001-stock-lego-firmware-only.md](../decisions/0001-stock-lego-firmware-only.md), [../directives/hardware-safety.md](../directives/hardware-safety.md)
- Measured values (reflectance on the real floor, gyro drift, wheel slip) do **not** go here — they go in [../findings/](../findings/) with their units and conditions.
