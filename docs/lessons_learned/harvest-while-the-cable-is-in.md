# Harvest everything while the cable is in — access is scarcer than you think

**Date:** 2026-09-01 · **Source:** the operator, after unplugging the robot mid-session:
*"you were supposed to have gotten information from the robot while you had it… when the robot is
plugged in, get as much information as possible first because we know that we will have to unplug it
very soon."*

**WHEN** hardware becomes available — a cable goes in, a rig is free, a lab is unlocked —

**DON'T** probe one narrow question at a time, thinking about the next question only after the last
one answered.

**BECAUSE** access to a robot that has to **drive** is not a steady state. It is a series of short,
interrupted windows that close without warning, for physical reasons that have nothing to do with what
you were measuring. **A question you did not ask costs a whole session, not a minute.**

## What happened

The hub was connected over USB and probed **serially, one question at a time**: identity, then the
filesystem, then Bluetooth state, then ports, then devices, then colour, then a heartbeat test. Each
probe was small and well-formed, and each was written *after* seeing the previous result.

Then the robot was unplugged — because it is a robot, and it needed to move.

**What we never took while we had the chance:** wheel encoder counts per revolution, a colour reading
over an actual sticky note, the achieved loop rate with sensors in the loop, the `rgbi()` range over a
bright and a dark surface. Every one was cheap. Every one now waits for a window that may not come
before the next class.

The serial approach felt rigorous — each probe informed by the last. **It was rigorous about the wrong
axis.** It optimised the *quality of each question* while ignoring the *number of questions the window
could hold*.

## The rule

**Harvest first, think afterwards.** When the cable goes in, run the broadest read-only sweep you have
before running a single targeted probe. Targeted probes are for the *second* window, when you know
which detail you are chasing.

`probes/harvest.py` exists for exactly this: one script, one window, everything readable in a single
pass, saved to `docs/findings/runs/`.

```bash
python3 probes/harvest.py          # the FIRST thing to run when the cable goes in
```

## Ordering matters inside the window too

Some questions **destroy the conditions** other questions need. Order the harvest so the fragile
questions come first:

1. **Anything needing the LEGO Hub OS alive** — the control protocol, BLE state. Every probe in
   `probes/` opens with `Ctrl-C` to force a REPL, and that interrupts the Hub OS. Once you have sent
   `0x03`, you can no longer ask what the Hub OS would have said.
2. **Everything else**, on the REPL, in any order.

Getting this backwards does not fail loudly. It quietly answers a different question than the one you
asked.

## How to apply

- **The broad sweep is the first command, always.** Not the interesting probe. The sweep.
- **Add to the sweep, not to your intentions.** When you notice something you wish you had captured,
  put it in `harvest.py` that day, so the next window takes it automatically.
- **Save raw output to a file every time.** A window you cannot re-open is a transcript you cannot
  re-take. `docs/findings/runs/` is where they live.
- **Assume every window is the last one.** It sometimes is.

**Related:** [probe-with-scripts-not-commands.md](./probe-with-scripts-not-commands.md) ·
[../directives/automation-first.md](../directives/automation-first.md) ·
[prove-identity-before-you-act.md](./prove-identity-before-you-act.md)
