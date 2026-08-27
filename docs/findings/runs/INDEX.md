# Findings / runs — INDEX (RAW OUTPUT)

**Raw captured output from programs run on the hub.** These are transcripts, not findings: no
interpretation, no conclusions, nothing edited. A finding that cites one of these files links to it as
its evidence, and the conclusion lives in the finding — never here.

Each file carries a `# ran:` header naming the program that produced it, so it is re-runnable.

| File | Produced by | What it captures |
|---|---|---|
| `gyro-drift-2026-08-27.txt` | `examples/gyro_drift.py` | Hub stationary on a flat surface for 30 s: yaw reading, accumulated drift, and an accelerometer disturbance check per sample — so a drift number cannot be quoted from a run where the hub was nudged |
| `imu-units-and-rate-2026-08-27.txt` | `examples/imu_units_and_rate.py` | Whether `tilt_angles()` returns degrees or decidegrees (derived against the gravity vector rather than assumed from a datasheet), and the achieved sample rate. ⚠ **Contains one DISCARDED number — see below** |

---

## ⚠ One number in this folder is DISCARDED and must never be quoted

`imu-units-and-rate-2026-08-27.txt` § 3 reports a **30 s yaw drift of ~98.7°, i.e. 3.29 °/s**. It is
**not a measurement of anything** and it must not reach the report, a finding, or `config.py`.

**Why it was thrown out:** the drift reversed direction — **+7.6°, then −22.2°, then +96.6°**. Steady
drift does not change sign. The operator was plugging in motors and handling the robot during the run,
so the input was contaminated; the arithmetic on top of it was fine, which is exactly what makes a
number like this dangerous.

**What replaced it:** `examples/gyro_drift.py` was written to watch the **accelerometer** alongside the
gyro, so a disturbed run can refuse to report. It caught the same disturbance independently — flagged
`CONTAMINATED` at t=14106 ms with the gravity vector deviating by up to **2534 milli-g** — and printed
no drift figure at all. *(That contaminated transcript is **not** filed here; only the clean re-run is.)*

**The figure that IS quotable** is in `gyro-drift-2026-08-27.txt`: net 1 ddeg over 30 s =
**0.0033 °/s**, worst accelerometer deviation 2.2 mg against a 25 mg threshold — **hub stationary, on
USB power, with no motors attached, n=1**. Drift while *driving* remains unmeasured (KU-M9 is
`PARTIAL`, not closed).

A discarded number sitting unlabelled in a folder is how it ends up in a report. It is labelled here.
The lesson is
[../../lessons_learned/bound-the-inputs-before-trusting-a-conclusion.md](../../lessons_learned/bound-the-inputs-before-trusting-a-conclusion.md).

**Rules for this folder**

- **Never edit a file here.** If a run was bad, run it again and keep both.
- Name files `<what>-<YYYY-MM-DD>.txt`. If a measurement is repeated the same day, add a suffix.
- A number only leaves this folder by being quoted in a finding **with its conditions** — surface,
  lighting, battery state, date. See [../INDEX.md](../INDEX.md).
- These are raw output. Anything not in one of these files, or measured elsewhere and recorded with its
  conditions, is **not a measurement** — [../../lessons_learned/say-which-kind-of-verified.md](../../lessons_learned/say-which-kind-of-verified.md).
