# Operator's Raw Notes — ARCHIVED

The operator's early notes from before the docs tree existed, moved out of the repo root on 2026-08-26.
**Superseded** — kept because they record how the platform understanding was arrived at, and because a
couple of early conclusions in them were later corrected, which is worth being able to trace.

| File | What it was | Superseded by |
|---|---|---|
| [2026-08-25_spike-platform-notes.md](./2026-08-25_spike-platform-notes.md) | A ChatGPT conversation identifying the hub as SPIKE Prime, the Linux/firmware constraint, and a first sketch of sticky-note detection | [../../research/spike-prime-linux-toolchain.md](../../research/spike-prime-linux-toolchain.md), [../../research/detection-and-sweep-techniques.md](../../research/detection-and-sweep-techniques.md), [../../decisions/0001-stock-lego-firmware-only.md](../../decisions/0001-stock-lego-firmware-only.md) |
| [2026-08-25_available-sensors.md](./2026-08-25_available-sensors.md) | The three sensor product links available to the course | [../../research/color-discrimination.md](../../research/color-discrimination.md), [../../plans/known-unknowns.md](../../plans/known-unknowns.md) |

**Corrected since:** the platform notes suggest `sudo screen /dev/ttyACM0` — [the hub-identification
runbook](../../runbooks/hub-identification.md) explains why `sudo` is wrong here (it leaves root-owned
lock files) and why an agent must never open a blocking serial read at all. They also list only two
motor types; there are [three](../../research/speed-envelope.md).
