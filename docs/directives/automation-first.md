# Automation First

**Purpose.** Hub rituals get run over and over, in class, under time pressure, with three teammates
waiting. Hand-typing them is slow, drifts between runs, and — with serial devices — can hang a session.

## THE NON-NEGOTIABLE RULE

**Every hub-touching script has an EXPLICIT TIMEOUT and exits. Never open a blocking serial read from a
tool call.** A `cat /dev/ttyACM0`, a `pyserial` read with no timeout, or a wait for a prompt that never
comes does not fail — it *hangs*, taking the session and the rest of the class period with it.

- Two layers: wrap the call (`timeout 15 ./scripts/read-output.sh`) **and** set a read timeout inside.
  The outer one cannot interrupt every blocked syscall.
- Every serial read is bounded — by a timeout, a byte count, or a sentinel line, plus a timeout regardless.
- **A script that times out reports UNKNOWN and exits non-zero. It never reports a pass.** If the hub did
  not answer, we do not know what the hub is doing ([honest-instrumentation.md](./honest-instrumentation.md)).

## The rituals this project will have

| Script | Does | Hub? |
|---|---|---|
| `setup-host.sh` | Ubuntu prep: `dialout`, ModemManager interference on `/dev/ttyACM*`, udev rule, Python deps. **Write this first** | No |
| `identify-hub.sh` | Read-only: hub present? which device node? which Hub OS / API generation? | Yes |
| `deploy.sh` | Put a program on the hub and **verify it landed** | Yes |
| `read-output.sh` | Pull program output back, bounded, then exit | Yes |
| `pre-demo-check.sh` | 60-second Demo Day pass: reachable, battery, ports match the port map, canned move | Yes |

`identify-hub.sh` must be the most careful: read-only by design, and it **never accepts a "Hub update
required" prompt** ([ADR-0001](../decisions/0001-stock-lego-firmware-only.md),
[hardware-safety.md](./hardware-safety.md)).

## Rules

- **Script the ritual the second time you run it.** Before running more than ~2 manual commands, grep
  `scripts/` for an existing helper. A re-improvised ritual is not repeatable, not reviewable, and not
  something you want to be reconstructing from memory on Demo Day.
- **Idempotent, and it says what it did.** Running twice is safe and reaches the same end state, and it
  reports what it *changed* versus what was already in place — "added user to dialout (was not a member)"
  vs "already in dialout, no change". A script printing "OK" for both cases hides that it just changed
  your system. Sharp case: adding a user to a group needs a re-login to take effect, so say so rather
  than leaving the operator with permissions that won't work until they log out.
- **Assert a KNOWN-CORRECT OBSERVATION, not exit code 0.** "The upload succeeded" is consistent with the
  file landing in the wrong slot, the old program still being the one that runs, a truncated transfer, a
  `MemoryError` on import, or the hub rejecting a file for a different API generation. Exit 0 means the
  *tool* didn't crash. So `deploy.sh` reads something back and checks it against a value we know is right
  — a version banner echoed from the hub, the slot listing, a checksum. If the verification itself cannot
  run, the answer is UNKNOWN, never pass.
- **Conventions:** `bash`, `set -euo pipefail`, executable, `.sh`, named `<verb>-<noun>.sh`, run from the
  repo root, one-line header saying what it does, whether it touches the hub, and its timeout.
- **Blacklisted operations never belong in a script** — no DFU, bootloader, firmware flash, filesystem
  format, or factory reset. Not negotiable by a script. **No script runs a git mutation.**
- Operator-facing step-by-step procedures live in [../runbooks/](../runbooks/); the script is the
  executable form of the runbook.
