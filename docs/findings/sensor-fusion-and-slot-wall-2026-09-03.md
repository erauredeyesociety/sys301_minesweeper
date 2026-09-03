# Finding — Sensor fusion works over USB; the slot-program execution wall

**Date:** 2026-09-03 · **Hub:** USB · **Written to hub:** telemetry CSVs to `/flash/tmp/telemetry`
(firmware untouched). Artefacts in `tmp/telemetry/`.

## 1. Sensor fusion is PROVEN, and it caught a real fault

`examples/fusion_capture.py` spins both motors in place and logs the full record — motors A/B
(encoder/velocity/status), IMU (yaw/pitch/roll, accel), and **both** colour sensors — to `/flash`,
run over USB via `hub_programmer/run.py`. Then `hub_programmer/download.py` pulls it and
`scripts/decode_telemetry.py` reconstructs it.

The 2026-09-03 run (`fusion-0001654111.csv`, 275 rows over 30 s):

- **Motors moved:** left wheel encoder −4483°, right +4485° (opposite = in-place spin, net forward
  +0.6 mm). Both climbed ~75°/tick = the commanded 150 dps.
- **The fusion caught a fault:** the encoders imply **1617° of rotation**, but the **gyro yaw moved
  only ~5°** (108.6°→113.7°, no wrap). So the wheels spun 4.5 turns while the body did not rotate —
  **held / blocked / slipping.** `decode_telemetry.py` reports this as the slip-fault case, exactly the
  `turn_slip` signal specified in [../research/odometry-fusion-and-health-2026-09-01.md](../research/odometry-fusion-and-health-2026-09-01.md).
- **All three sensor families logged together and decoded together.** The decoder reuses `src/odometry`
  and `src/motion_tuning` (`unwrap_degrees`, `track_width_from_samples_mm`) — one source of truth for
  the wheel diameter, mirror sign, and heading unwrap.

**So the whole "capture motors+IMU+colour, retrieve, fuse, interpret" loop works, over USB, no
Bluetooth.** This is the path that matters for characterisation and the report.

⚠ **Colour caveat:** during the spin, colour reflection read low/zero at times (`Cr0 Dr0`) — the robot
likely rotated off the surface, or reads dip during motor activity. Re-capture a colour run with the
sensors held over a known surface; do not trust colour from a spin run.

## 2. The slot-program execution WALL

The BLE-while-driving milestone is blocked by a real, specific problem:

**`hub_programmer/slot_upload.py` uploads a program and `ProgramFlowRequest 0x1E` returns "Acknowledged"
— but the program never actually runs.** Measured:

- Every protocol step ACKs: `ClearSlot 0x46→0x47`, `StartFileUpload 0x0C→0x0D`, `TransferChunk
  0x10→0x11` (CRC32 matches), `ProgramFlow Start 0x1E→0x1F`.
- **But the motor does not turn and no `ConsoleNotification 0x21` print output appears** in the BLE
  `DeviceNotification 0x3C` stream.
- **The identical program spins the motor perfectly via the REPL** (`hub_programmer/run.py`): encoders
  climb 75°/tick as commanded. So `motor.run()` and the `runloop.run(main())` structure are correct.

**The "Acknowledged" is misleading — it means the Hub OS accepted the start command, not that the code
executed.** The slot execution is what fails, not the program. Adding the `runloop` async structure did
**not** fix it, so it is not a program-structure issue — it is how the slot is stored or launched.

Under research (`docs/research/slot-execution-and-live-motor-control-2026-09-03.md`, being written now): whether a slot needs `.mpy` bytecode / a project manifest / a different ProgramFlow
sequence, **and** whether a direct live-motor-command message exists (drive motors from the host over
BLE/USB with no user program — the LEGO app's live-control path), which would reach the milestone
without fixing slot execution at all.

**What IS proven, and stands:** motor control (REPL), BLE telemetry streaming (`DeviceNotification`,
MTU **517**), and on-hub logging + USB retrieval. Only their *coexistence via a slot program* is
blocked.

**Related:** [telemetry-pipeline-validated-2026-09-03.md](./telemetry-pipeline-validated-2026-09-03.md) ·
[../research/odometry-fusion-and-health-2026-09-01.md](../research/odometry-fusion-and-health-2026-09-01.md) ·
`scripts/decode_telemetry.py` · `examples/fusion_capture.py`

## UPDATE (2026-09-03, same day): the slot wall is FIXED

**Root cause: the slot's runnable entry point must be named `program.py`.** `slot_upload.py` uploaded
under the source basename (`g4_spin_and_print.py`); `ProgramFlowRequest Start` selects by slot NUMBER,
so it ACKed but the slot had no `program.py` to run. Confirmed against LEGO's own `app.py` and a
community uploader ([../research/slot-execution-and-live-motor-control-2026-09-03.md](../research/slot-execution-and-live-motor-control-2026-09-03.md)).

**One-line fix applied** in `hub_programmer/slot_upload.py`: default the upload name to `program.py`.
**MEASURED WORKING 2026-09-03:** g4 uploaded as `program.py`, `ProgramFlow Start`, and the program
RAN — console output streamed (`[console] G4 1 ... G4 20`), encoders climbed 70 deg/tick (the commanded
150 dps), and yaw spun through full rotations. **Motor driving + telemetry streaming at once, proven.**

So: a program runs on the hub via a slot, drives motors, and streams telemetry — the competition
standalone-run mechanism and the BLE-while-driving milestone are both unblocked. No firmware touched;
raw `.py` runs (no `.mpy` needed). The swap procedure (interchange `program.py`) is the deploy runbook.

