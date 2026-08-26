# Say which kind of "verified" — and never touch hardware unasked

**Date:** 2026-08-26 · **Source:** the operator, alarmed: *"how the hell are you doing real world tests
without the SPIKE connected? I hope you did not connect to a bluetooth device and start working."*

**WHEN** reporting that something was checked,

**DON'T** use *measured*, *tested*, or *verified* without saying **against what**.

**BECAUSE** in this project those words carry a specific meaning — *on the real robot, on the real
floor, with the conditions written down* — and using them for a host-side arithmetic check makes the
operator believe hardware was touched.

## What happened

Nothing was connected. No serial device existed, `bleak` was not even installed, and the code reported
`api_generation() == "simulated"` throughout. Every check was pure Python on the laptop.

But I wrote *"I measured the actual formatted record: 89 B typical."* I measured **the length of a
Python string**. That is a legitimate, hardware-free thing to do — and *measured* was the wrong word for
it in a repo where the whole vocabulary had been built around the opposite meaning. I built that
vocabulary and then broke it.

The operator's alarm was the correct response to what I wrote.

## The three kinds, and the words for them

| Kind | Say | Example |
|---|---|---|
| Arithmetic or a pure function on the host | **"computed"** / **"checked on the host"** | The formatted record is 89 bytes · a 1.4 Hz rate makes the width gates invert |
| A claim traced to a document | **"confirmed against \<source\>"** | LEGO's techspec gives the colour standoff as 16 mm |
| A reading taken off real hardware | **"measured"** — and *only* this | Nothing in this project qualifies yet. **Nothing.** |

If a sentence would read the same whether or not hardware existed, it is not a measurement.

## The hardware rule, which is not negotiable

**The operator says when hardware is connected. Until then it is absent.**

Never initiate a connection, a pairing, a scan, or a hub-touching script on your own — not to check
something, not to be helpful, not because a device might be there. This extends the existing blacklist
([ADR-0001](../decisions/0001-stock-lego-firmware-only.md)): the hub is identified read-only, on the
operator's say-so, following [../runbooks/hub-identification.md](../runbooks/hub-identification.md).

The cost of being wrong is asymmetric. Waiting costs a few minutes. An unattended tool that triggers a
"Hub update required" prompt on shared course equipment can end the project.

## How to apply

- Before writing *measured*, ask: **could this sentence be true with the hardware in a box?** If yes,
  the word is *computed* or *confirmed*.
- **Label the sample**, not just the result: "on a synthetic stream" and "on the arena floor" are
  different claims and must read differently.
- When the operator asks whether you touched something, **show the evidence rather than asserting it** —
  the device list, the API generation, the missing package. An assurance is worth less than a check they
  can read.

**Related:** [a-tool-works-when-it-does-its-job.md](./a-tool-works-when-it-does-its-job.md) (report
against the purpose, not the component) · [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md)
