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
4. **Writing to the hub's filesystem before we know what is on it.**

**Required order of operations:**

- **Identify before you act.** The first hub session is READ-ONLY: determine the Hub OS / API
  generation without changing anything. Procedure: [../runbooks/hub-identification.md](../runbooks/hub-identification.md).
  Until that lands, treat the API generation as **UNKNOWN** and do not write mission code against a
  guessed API.
- **Never run a blocking serial read from an agent tool call.** Opening `/dev/ttyACM0` and waiting for
  bytes hangs the session. Wrap every hub interaction in a script with an explicit timeout
  (`scripts/`), invoke the script, and let it exit. This is a hard rule — see
  [automation-first.md](./automation-first.md).
- **Motors move.** Before any motion command, the robot is on a surface where a runaway is harmless,
  and the Builder — the only authorized operator — is present. Start every motion program with a
  short, cancellable, low-velocity move, not a full mission run.
- **Power.** Don't leave the hub connected and running unattended.

Physical build, mounting, and mechanical design belong to the Designer and Builder. This repo
*records* the build ([../hardware/port-map.md](../hardware/port-map.md)); it does not design it.
