# Session Records — INDEX

Dated per-session narrative: what was done, decided, discovered, blocked, and what's next.
Immutable and append-only. Stale records move to [../archives/session_records/](../archives/session_records/).

| Date | Record |
|---|---|
| [2026-08-27_hub-first-contact-usb-and-ble.md](./2026-08-27_hub-first-contact-usb-and-ble.md) | 2026-08-27 | **The session the project stopped being a paper design.** Hub connected for the first time: **SPIKE 3** confirmed, deploy route **proven** (13 KB in 3.6 s, hub-computed SHA-256, imports OK — no LEGO app, no compiler, no Windows), firmware **provably untouched** by baseline diff, **Bluetooth connected** from Linux with raw `bleak` and our hub **identified by matching its device UUID across USB and BLE**. IMU units derived from gravity. A fatal `NameError` found in `hub_motors.py` that would have crashed every motor command. **Three of my own claims retracted** — USB-vs-BLE exclusivity, MAC stability, and blind teleoperation. DFU-gesture safety rule added to the blacklist |
| 2026-08-25 | [Project initialization](./2026-08-25_project-initialization.md) |
| 2026-08-26 | [Retrieval stack, code scaffold, SE planning](./2026-08-26_retrieval-stack-code-scaffold-and-se-planning.md) |
| 2026-08-26 | [Implementation, Bluetooth, analysis layer](./2026-08-26_code-implementation-bluetooth-and-analysis-planning.md) |
