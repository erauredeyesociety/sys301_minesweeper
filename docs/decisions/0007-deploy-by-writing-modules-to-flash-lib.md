# ADR-0007 — Deploy by writing modules to `/flash/lib` over the USB REPL

**Status:** ACCEPTED · **Date:** 2026-08-27 · **Supersedes:** nothing ·
**Closes:** KU-D1 (partially — module deploy only, not program launch)

## Context

LEGO ships no SPIKE application for Linux desktop, and this project runs on native Ubuntu 22.04. The
deploy route sat between us and *every* hardware result and was the least certain thing in the
project — [known-unknowns.md](../plans/known-unknowns.md) KU-D1 called it exactly that.

Four routes were considered. The constraint that eliminates most of them is
[ADR-0001](./0001-stock-lego-firmware-only.md): **the hub keeps its stock LEGO firmware**, and a
"Hub update required" prompt is never accepted.

| Route | Verdict |
|---|---|
| LEGO SPIKE desktop app | **Not available on Linux.** Also the most likely source of an unattended Hub OS update prompt. |
| Chrome + WebSerial web app | Works in principle, holds `/dev/ttyACM0` **exclusively**, and negotiates Hub OS compatibility on connect — the same update-prompt risk. **Kept as the fallback, not the primary.** |
| BLE upload via LEGO's published COBS protocol | Real and documented, but needs a working radio, a short advertising window, framing, and identity confirmation before a byte moves. Far more machinery than the problem requires. |
| **MicroPython REPL over USB CDC-ACM** | **Chosen.** See below. |

## Decision

**Modules are deployed by writing them into `/flash/lib` as base64 chunks over the hub's MicroPython
REPL on `/dev/spike`, and every upload is verified by a SHA-256 the hub computes on itself.**

Implemented in [`hub_programmer/upload.py`](../../hub_programmer/upload.py); operator procedure in
[../runbooks/deploy-to-hub.md](../runbooks/deploy-to-hub.md).

This works because of what the hub turned out to be, measured on 2026-08-27
([findings](../findings/hub-first-contact-2026-08-27.md)):

- It is a **stock MicroPython board**. `/flash/README.txt` says so in the firmware's own words:
  *"This is a MicroPython board. You can get started right away by writing your Python code in
  `main.py`."*
- **`/flash/lib` is already on `sys.path`** (`['', '.frozen', '/flash', '/flash/lib']`), so a module
  written there is importable with no further configuration.
- There is **32.4 MB free**. Our entire `src/` is a rounding error against it.

**Demonstrated, not proposed:** `src/config.py` (13,262 B, 70 chunks) uploaded in **3.6 s**, the
hub's own SHA-256 matched the local file, and `probes/import_check.py` reported **`OK config`**.

### What this decision does NOT include

**How a *program* is launched is still open** — see KU-M16. Writing a module is proven; whether
`/flash/main.py` autoruns at boot, and how that interacts with the Hub OS started by `boot.py`, is
untested. Do not build a Demo Day procedure on it until it is.

For *running* code now, [`hub_programmer/run.py`](../../hub_programmer/run.py) executes a file in RAM
through paste mode and leaves nothing on the filesystem. That is deliberately separate from upload:
an experiment that turns out wrong should not become litter on shared course equipment.

## Consequences

**Good**

- **No LEGO software anywhere in the loop**, so no path to an accidental Hub OS update prompt.
- **No compiler.** The hub runs MicroPython *source*. `mpy-cross` exists (`sys.implementation._mpy`
  is `7942`) but is a RAM/speed optimisation, not a requirement. No GCC, no Windows VM.
- **Verification is real.** Success means the hub's own hash matched — never merely "no exception".

**Costs and risks**

- **It writes to the hub**, which is why `probes/` is read-only by contract and this lives in
  `hub_programmer/` instead. The boundary is the safety property.
- **A pristine baseline must exist first.** [`probes/capture_baseline.py`](../../probes/capture_baseline.py)
  captured the hub before anything was written, and a diff proves what changed
  ([firmware-integrity-proof.md](../findings/firmware-integrity-proof.md)). Deploying without a
  baseline forfeits the ability to prove the firmware was untouched.
- **Stock files are never overwritten.** `upload.py` refuses `boot.py`, `README.txt` and
  `pybcdc.inf` outright, and requires `--force` for `main.py`. `/flash/program` and `/flash/config`
  are off limits entirely. **`boot.py` is the genuinely dangerous file** — it holds
  `hub.config["hub_os_enable"] = True`, and changing that alters how the hub boots.
- **CPython syntax will not run on the hub.** MicroPython reports `sys.version` `3.4.0`; no
  dataclasses, no `typing`, no `numpy`, no `statistics`. `import_check.py` exists to catch this
  before mission code depends on it.
- **USB and Bluetooth may interact.** Whether opening a REPL session suppresses BLE advertising is
  **UNKNOWN** — an earlier claim that it does was retracted for want of a controlled experiment
  ([ble-bring-up.md](../research/ble-bring-up.md)).

## Alternatives if this route ever fails

1. **Chrome + WebSerial**, accepting the exclusive port lock and watching for update prompts.
2. **BLE upload** via LEGO's published protocol — more machinery, and LEGO confirms the same COBS
   protocol also runs over the USB port we already use, so the cable stays the simpler option.

**Never:** Pybricks, `pybricksdev`, DFU, or any third-party firmware — [ADR-0001](./0001-stock-lego-firmware-only.md).
