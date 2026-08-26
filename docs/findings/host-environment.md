# Finding — Ubuntu host readiness for SPIKE Prime USB serial

**Date:** 2026-08-25 · **Hub connected:** no · **Status:** open — two blockers to clear before first hub contact

What was actually measured on the development machine, and what has to change before the hub is plugged
in. Everything below was observed by running the command shown. Nothing here is inferred.

## Measured

| Check | Command | Result | Verdict |
|---|---|---|---|
| Python | `python3 --version` | `3.10.12` | OK |
| pyserial | `python3 -c "import serial; print(serial.__version__)"` | `3.5` | OK — already installed |
| Serial group membership | `id -nG` | includes `dialout` | OK — no udev change needed for permissions |
| Serial device present | `ls -l /dev/ttyACM*` | none | Expected — hub not connected |
| **ModemManager** | `systemctl is-active ModemManager` | **`active`**, `enabled` | ⚠ **BLOCKER** |
| Serial terminal | `which tio picocom screen` | only `/usr/bin/screen` | ⚠ `tio` not installed |
| Browser | `which google-chrome` | `/usr/bin/google-chrome` | OK — WebSerial route available if needed |
| RAM / swap at init | `free -g` | 15 GB total, ~3 GB available; swap 9 GB | Constrains parallel agent spawning |
| earlyoom | `systemctl is-active earlyoom` | `inactive` | Host not hardened; self-throttle |

## The two blockers

**1. ModemManager is running and will corrupt the first hub session.** It probes newly-appearing
`/dev/ttyACM*` devices with AT commands. On a SPIKE Prime hub that injects garbage into the serial
stream and can make a working connection look broken — which is exactly the kind of failure that gets
misdiagnosed as "Linux doesn't work with LEGO" and sends the team down a dead end. See
[../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md) for the
recommended fix (a udev rule tagging the hub's VID/PID with `ID_MM_DEVICE_IGNORE`, and/or disabling
ModemManager). Clear this **before** the hub is ever plugged in, not after a confusing first session.

**2. No `tio`.** `screen` is present and workable, but the toolchain research recommends `tio`. Either
is fine; the choice belongs in `scripts/setup-host.sh`.

## What this means

- `scripts/setup-host.sh` has a concrete job now: neutralize ModemManager for this device, install a
  serial terminal, and verify `dialout` membership. It should be **idempotent** and report what it
  changed versus what was already in place.
- The permissions half of the usual Linux serial headache is already solved — `dialout` is in place.
- **UNVERIFIED:** none of this has been tested against an actual hub. Every row above describes the
  *host*, not the hub. First hub contact follows
  [../runbooks/hub-identification.md](../runbooks/hub-identification.md), read-only.

## Host capacity — where the memory actually goes

`earlyoom` is inactive and free RAM was ~3 GB at init, so parallel agents and workflows are gated on a
resource check. But the obvious suspects are not the cause. Measured 2026-08-25:

| | |
|---|---|
| **ResearchHub running locally** | **No** — no process, no container, nothing to stop |
| All 5 Docker containers, combined | **~82 MB** (0.5% of RAM) |
| Chrome (main + ~8 renderers) | **~4.3 GB** |
| VS Code + its extension hosts (incl. Claude, Kilo) | **~2.0 GB** |

The containers belong to **other projects** — `adsb_analytics` (TimescaleDB) and `cars_demo_13`
(`rag_qdrant`, `rag_pg`, `cars_redis`, `cars_simulation_api`). None of them belong to this project and
none of them are worth stopping for memory: shutting down all five would recover about 82 MB. **Closing
Chrome tabs is worth ~50× more than stopping every container on the machine.**

`rag_qdrant` and `rag_pg` are part of the `cars_demo_13` compose project, **not** a docs-rag for this
repo — see [../plans/2026-08-25-docs-rag-and-literature-workflow.md](../plans/2026-08-25-docs-rag-and-literature-workflow.md).

Swap is in use (3.4 GB of 9.9 GB), which is the real signal that the desktop session is oversubscribed.
