# Hardware Safety — READ BEFORE TOUCHING THE HUB

**Purpose.** The SPIKE Prime hub is shared course equipment on stock LEGO firmware. Its software state
is a one-way door. One careless flash ends the project and costs the course a hub.

**PERMANENTLY FORBIDDEN — no exceptions, no "just to test":**

1. **Pybricks or any third-party firmware.** It replaces LEGO firmware. Blacklisted even though it is
   the most Linux-friendly option. If research surfaces it, record *why it is excluded* and move on.
2. **DFU mode, bootloader entry, filesystem format, factory reset.**
3. **Clicking through a "Hub update required" prompt.** If the LEGO app or web app asks to update,
   STOP and ask the operator. A Hub OS change is an operator decision recorded as an ADR — never a
   side effect of opening a tool.
4. **Writing to the hub's filesystem before we know what is on it.** *(Amended 2026-08-27: we now know
   what is on it — a pristine baseline is captured in
   [../archives/hub-baseline/INDEX.md](../archives/hub-baseline/INDEX.md) — so writing is permitted by
   the procedure in [../runbooks/deploy-to-hub.md](../runbooks/deploy-to-hub.md) and
   [ADR-0007](../decisions/0007-deploy-by-writing-modules-to-flash-lib.md). **The stock files remain
   off-limits**, `upload.py` refuses them in code, and every write is followed by a baseline re-capture
   and diff. Writing a `.py` into `/flash` **cannot** touch the firmware — that is the FAT filesystem
   the firmware exposes, not the firmware image — but that is a reason the rule is narrower now, not a
   reason to be casual.)*
5. **Instantiating the hub's own Bluetooth radio from a hub program** — `bluetooth.BLE()` followed by
   `.active(True)`, `.irq()`, `.gatts_register_services()` or `.gap_advertise()`. The `bluetooth`
   module **is** present and is the full MicroPython `ubluetooth` stack, so nothing stops you at the
   API level — but `BLE()` returns a **process-wide singleton**, which means it hands back **LEGO's own
   stack**, and activating it risks a double-init underneath the C-level owner of the radio on shared
   course equipment. It is also **unnecessary**: BLE from the *host* side works and is proven
   ([../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md)), and telemetry
   leaves the hub by `print()` regardless. Reasoning:
   [../research/ble-bring-up.md](../research/ble-bring-up.md) § 4.4. **Operator-gated; treat as
   forbidden.**

**Required order of operations:**

- **Identify before you act.** The first hub session is READ-ONLY: determine the Hub OS / API
  generation without changing anything. Procedure: [../runbooks/hub-identification.md](../runbooks/hub-identification.md).
  *(Done 2026-08-27 — **SPIKE 3, MicroPython 1.24.0**,
  [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md). The rule
  survives in a narrower form: the API generation is known, but its **call sites are still unrun** —
  `dir()` a call or run it before writing mission code that depends on its shape.)* On any **other**
  hub, this rule applies unchanged and from the start.
- **Never run a blocking serial read from an agent tool call.** Opening `/dev/spike` and waiting for
  bytes hangs the session. Wrap every hub interaction in a script with an explicit timeout
  (`scripts/`), invoke the script, and let it exit. This is a hard rule — see
  [automation-first.md](./automation-first.md).
- **Motors move.** Before any motion command, the robot is on a surface where a runaway is harmless,
  and the Builder — the only authorized operator — is present. Start every motion program with a
  short, cancellable, low-velocity move, not a full mission run.
- **Power.** Don't leave the hub connected and running unattended.

Physical build, mounting, and mechanical design belong to the Designer and Builder. This repo
*records* the build ([../hardware/port-map.md](../hardware/port-map.md)); it does not design it.
