# Finding — On-hub telemetry logging + USB retrieval works end to end

**Date:** 2026-09-03 · **Hub:** USB, held still (no shake landed in the window) · **Written to hub:**
yes — `hub_telemetry_log.py` to `/flash/lib`, and a run's CSV to `/flash/tmp/telemetry/`. Firmware
untouched (only `/flash` files). Artifact: `tmp/telemetry/20260903T104407-verbose-0002543799.csv`.

## What was validated

The **"log on hub → retrieve over USB"** pipeline — the primary telemetry architecture, and the one
that needs **no Bluetooth** — runs end to end:

| Step | Tool | Result |
|---|---|---|
| Deploy the logger module | `hub_programmer/upload.py src/hub_telemetry_log.py --apply` | 11 chunks, SHA-256 verified on the hub |
| Run a bounded verbose capture | `hub_programmer/run.py examples/telemetry_verbose_log.py --seconds 45` | 300 rows over 30 s to `/flash/tmp/telemetry/verbose-0002543799.csv` |
| Retrieve over USB | `hub_programmer/download.py --all` | 29,957 B pulled to `tmp/telemetry/`, SHA-256 verified |

**The CSV is well-formed: 30 columns, 300 clean rows**, every channel present — `absA/relA/velA/dutyA/statusA`,
same for B, `yaw/pitch/roll` (decidegrees), `accx/accy/accz` (milli-g), and both colour sensors
`color/refl/rgbi` for C and D. A metadata header (`#verbose-telemetry v1`, period, duration, port map)
precedes the data, so a parser must skip `#` lines.

## What this does NOT yet prove

- **Real motion data.** This run was static (relA span 1°, yaw span 1°) — the operator's shake did not
  land in the window. The *plumbing* is proven; a capture with deliberate shaking / wheel-turning is
  the next run, and the operator drives its timing (self-serve command in the session record).
- **The untethered path.** This ran via the REPL (`run.py`, over the cable). Making it a standalone
  program the robot runs after unplugging needs `hub_programmer/slot_upload.py` (still UNRUN). That is a
  separate milestone; this validates logging + retrieval, which is 90 % of the value.

## Why this matters for the plan

The operator's stated worry was that BLE research would hold up telemetry. **It does not** — this path
is Bluetooth-free and works today. Live BLE streaming (`ConsoleNotification` / `DeviceNotification`)
remains a parallel upgrade, not a prerequisite. There is **no SD-card option** on the hub
([telemetry-offload-paths.md](../research/telemetry-offload-paths.md)); `/flash` + USB retrieval is the
whole story.

**Related:** [../research/telemetry-offload-paths.md](../research/telemetry-offload-paths.md) ·
[../research/telemetry-while-driving.md](../research/telemetry-while-driving.md) ·
`src/hub_telemetry_log.py` · `hub_programmer/download.py`
