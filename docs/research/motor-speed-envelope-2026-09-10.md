# Research — "can we not increase motor speed / PWM?" — the 2026-09-10 answer

**Date:** 2026-09-10 (DEMO DAY) · **Status:** RESEARCH, **NO HARDWARE TOUCHED** — every figure is read out of an
existing capture/log or is arithmetic on one · **Owner:** Programmer + Designer · **Answers:** *"can we not increase
motor speed / PWM or something?"* · **Corrects:** [./speed-envelope.md](./speed-envelope.md) (Ø56 wheel
+ `[ASSUMED]` motor — both now MEASURED) · **Grounds:**
[../findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md),
[../plans/speed-and-heading-precision-2026-09-08.md](../plans/speed-and-heading-precision-2026-09-08.md)

---

## 1. TL;DR

**Yes, the motors can go far faster — and no, we must not use it.** The robot commands 80–270 deg/s against a MEASURED
`max_speed` of 930 deg/s (= 515 mm/s on our MEASURED Ø63.5 mm wheels), so the operator is right that the drivetrain is
loafing at roughly **11–15 % duty [COMPUTED]** — but the binding limit was never the motors. It is **detection
sampling**: at the motor ceiling a worst-case crossing yields **0.94 samples [COMPUTED]** against a `MIN_EVENT_SAMPLES
= 2` requirement, so at full motor speed the detector cannot fire at all. Three further facts settle it for today:

- **There is no time pressure.** The 23-lane 914 × 914 mm sweep completes in **168.0 s [COMPUTED]** against `RUN_TIMEBOX_S = 300.0` — 56 % of the box.
- **`TRAVERSE_SPEED_MMS = 150.0` is already legal**, ~1.15× margin, because `src/main.py` keeps no per-tick CSV and so
  escapes the flush spike entirely (§4).
- **`src/main.py` has NEVER RUN on hardware** — demo morning is the worst moment for its first diff.
  **Recommendation: change nothing in the speed path today.**

---

## 2. The motor API — PWM exists, and it is the wrong tool

**Our own hub first.** `dir(motor)` captured off *this* hub
([../archives/hub-baseline/03-api-surface.txt](../archives/hub-baseline/03-api-surface.txt) line 13, [MEASURED]
2026-08-27, re-confirmed 2026-09-01) contains **`set_duty_cycle` and `get_duty_cycle`** — so yes, open-loop PWM exists
on SPIKE 3, on our hub, distinct from velocity control.

| Call | On our hub | Ever called here? |
|---|---|---|
| `motor.run(port, dps)` | present [MEASURED] | yes — delivers commanded dps to within a few % |
| `motor.set_duty_cycle(port, pwm)` | present [MEASURED] | **never** |
| `motor.get_duty_cycle(port)` | present [MEASURED] | yes — **0 on A and B at rest** [MEASURED] |
| `motor.info(port)` | present, `(48, 930)` on **both** motors [MEASURED] | yes |
| `set_max_speed` / `motor.configure` / `limits` | **absent** — zero hits in the capture | n/a |
| `motor_pair.move_tank(...)` | present [MEASURED] | **never run** — no log, no finding |

**The closed loop is nowhere near saturating.** ⚠ [COMPUTED FROM ASSUMED INPUTS — the carpet load comes from
[./speed-envelope.md](./speed-envelope.md), whose header says nothing in it was measured and whose figure assumes a
Ø56 wheel; corrected to our Ø63.5 mm the per-motor load is ~0.543 Ncm. Never quote as measurement.] Required duty
against LEGO's light-load curve, scaled to our MEASURED **8270–8327 mV** pack: **100 dps → ~11 %, 150 → ~15 %, 292 →
~26 %, 930 → ~76 %.** So open-loop PWM buys at most **+33 % top speed (930 → ~1240 dps)** for the loss of velocity
regulation on *both* wheels — asymmetry becomes uncorrected heading error and ground speed becomes battery- and
carpet-dependent. Against a ~162–221 mm/s sampling ceiling that trades what we cannot lose for speed we may not use.
**Do not pursue it.**

**No low-level route either, and looking for one is dangerous.** `dir(machine)` on our hub is exactly `['bootloader',
'idle', 'reset', 'reset_cause', 'soft_reset', 'unique_id']` (same capture, line 67, [MEASURED]) — no PWM, no `Pin`, no
`Timer`. ⚠ **`machine.bootloader()` is in that list and is the software equivalent of the forbidden DFU gesture.**
Anyone rummaging in `machine` for "more power" finds it first. BLACKLIST item 1.

**What `max_speed = 930` means.** `motor.info(port)` returns `(device_id, max_speed)`; ours gives **(48, 930)** on
both A and B, byte-identical [MEASURED 2026-09-01 and 2026-09-03], and it is **read-only** — no setter exists anywhere
in the captured surface. **930 is unexplained; say so rather than invent a reason.** LEGO's own 45603 fact sheet (LEGO
CDN PDF, `pdftotext`-extracted, **web**) gives no-load **185 RPM ±15 % at 7.2 V = 1110 deg/s**, and the SPIKE 3
mirrors document a **±1110 deg/s** command range for a medium motor. Our 930 dps = 155 RPM is 16 % low and sits
*below* the bottom of LEGO's own ±15 % band (944–1278 dps). docs-rag called 930 "a firmware-imposed ceiling" but
**cited nothing that says so** — model synthesis, **not** fact (identical values on two units suggest a firmware table
keyed on `device_id` [INFERRED]). **Consequence: none** — the unclaimed 180 dps is 100 mm/s the sampling budget
forbids anyway.

**Acceleration and `motor_pair`.** `motor.run(port, velocity, *, acceleration=1000)`, range 1–10000 deg/s² — on two
independent SPIKE 3 mirrors (**web**), ⚠ **[UNVERIFIED on our hub]** and **never passed by any call site in `src/` or
`examples/`**. Worth **5.6 s over a 23-lane sweep [COMPUTED]** (penalty per accel/decel pair is exactly *v/a* = 0.271
s/leg at the default and 150 mm/s). ⚠ Do **not** pass it today: if our Hub OS rejects the keyword it raises
`TypeError` at the **first drive call** and the mission dies on the floor — and it may not even be a clean exception,
since a different-generation LEGO doc defines `acceleration` as a **percentage 0–100** for `run_at_speed`.
`motor_pair` has **no** duty-cycle call, **no documented cross-motor synchronisation**, and has **never been run on
this hub** (`examples/drive_straight_encoders.py` calls it; no log, no finding); `motor_pair.pair()` also applies its
own [UNVERIFIED] notion of forward against the MEASURED convention `src/hub_drive.py` owns. **Leave it alone.**

---

## 3. The real limiter — the sampling ceiling

mm per motor-degree = π × 63.5 / 360 = **0.5541** [COMPUTED from MEASURED Ø63.5 mm]. Worst-case chord across a 76 mm
note = **36.48 mm** (76 mm square crossed at 45° at the worst lane offset). Samples per crossing = (chord / speed) ×
tick_rate:

| Speed | dps | @ 17.8 Hz | @ 13.3 Hz | @ 9.35 Hz (p95) |
|---|---|---|---|---|
| 150 mm/s (**shipped**) | 271 | 4.33 | 3.23 | 2.27 |
| 221 mm/s | 399 | 2.94 | 2.20 | 1.54 |
| 300 mm/s | 541 | 2.16 | 1.62 | **1.14** |
| **515 mm/s (motor ceiling)** | 930 | 1.26 | **0.94** | **0.66** |

`MIN_DWELL_SAMPLES = 2` is needed to *latch* a state change and `MIN_EVENT_SAMPLES = 2` to *accept* it, so **at the
motor ceiling the detector structurally cannot fire** — "turn the motors up" does not degrade detection, it disables
it. ⚠ **Worse, at 300 mm/s the detector actively discards mines it sees:** `main.py` calls `event_width_gates(tick_hz,
150, 76)`, whose low gate is `lo = max(2, int(0.25 * full))`; at 300 mm/s and 13.3 Hz a *full* crossing is 3.37
samples so `lo = 2`, but a worst-case-offset mine yields 1.62 — below the gate — and is classified **too_narrow and
REJECTED** [COMPUTED]. The robot sees the mine and does not count it, with nothing on the matrix to say why.

**Blind-window exposure** — fraction of swept path inside a tick gap longer than one worst-case crossing [MEASURED, 10
deduplicated driving runs, 163.3 s, 2653 gaps]: **150 mm/s → 2.83 %** (one gap per 13.6 s) · 221 → 2.93 % · 300 → 5.24
% · 515 → **24.80 %** (one per 0.5 s). At full motor speed a quarter of the arena is never sampled. *Caveat:* measured
on programs that log every tick, so an **upper bound** for `main.py` — but the 300–813 ms stalls are UNEXPLAINED (§8)
and cannot be assumed zero.

**Correcting a stale premise:** "MEAN 75 ms = 13.3 Hz" is a **pooled average over two commanded tick periods**
[MEASURED, own binning of `tmp/telemetry/`]: the `TICK_MS=50` family (44 files, 8896 gaps) runs **mean 61.2 ms = 16.34
Hz, median 54, p95 107 ms = 9.35 Hz**, the `TICK_MS=100` family mean 109.2 ms. `src/main.py:49` sets `TICK_MS = 50`,
so 13.3 Hz was never its number. ⚠ `src/mission_config.py` still quotes `TICK_MS=100` and 9.18 Hz / 112 mm/s —
**stale, ~2× pessimistic.**

---

## 4. The tick rate and `flush_every`

Binning inter-tick gaps by `seq % 10` [MEASURED, own analysis], the hot bin exceeds the other nine by **+48.1 to +50.0
ms** across six programs — pooled **+49.7 ms** for the `TICK_MS=50` family. (The repo's "+51 ms" is a
pre-deduplication figure; the honest number is ~48–50 ms.) The non-flush baseline is **56.1 ms** against a commanded
50 ms sleep, so the whole tick body — encoders, IMU, both colour sensors, CSV write — costs ~6 ms. The flush damages
the **tail**, not the mean: removing the hot bin moves the mean only 61.2 → 56.1 ms (8 %) but **p95 from 107 ms to 55
ms (49 %)**.

| `flush_every` | mean period | p95 | safe speed (p95, ÷3) | rows at risk on abnormal exit |
|---|---|---|---|---|
| 10 (**current default**) | 61.1 ms / 16.4 Hz | 107 ms / 9.35 Hz | **114 mm/s** | 10 = 0.6 s |
| 20 | 58.6 ms / 17.1 Hz | 107 ms / 9.35 Hz | 114 mm/s | 20 = 1.2 s |
| **25** | 58.1 ms / 17.2 Hz | **55 ms / 18.18 Hz** | **221 mm/s** | 25 = 1.5 s |
| 100 | 56.6 ms / 17.7 Hz | 55 ms | 221 mm/s | 100 = 5.7 s |
| close-only | 56.1 ms / 17.8 Hz | 55 ms | 221 mm/s | **entire run (~3000 rows)** |

**The step is at 20 → 25 and nowhere else** [COMPUTED]: p95 escapes the flush spike exactly when flush ticks fall
below 5 % of ticks. Beyond 25 you buy ~3 ms of mean, nothing at the tail, and more rows at risk
(`examples/find_corner.py:64` uses 25). Under the blend-corrected divisor 3.86 the pair is 88 → 172 mm/s. **Durability
cost, MEASURED on our own disk:** of 7 distinct `follow_tape` runs (deduplicated by hub-side stamp) **3 ended without
writing their `#end` trailer** — 43 % abnormal termination. They still yielded 598, 174 and 562 rows *only because*
CsvLog flushes every 10, so **`flush_every=0` is not a candidate.**

⚠ **THE BIG ONE: none of this applies to `src/main.py`.** `_log()` fires only on a counted mine and on the lane-end
`finish()` — **the sweep loop never appends**. So main.py's expected tick period is the non-flush baseline already
(**mean 56.1 ms, p95 55 ms = 18.18 Hz**), its tail-safe ceiling is **221 mm/s (÷3)** or **172 mm/s (÷3.86)**, and
`TRAVERSE_SPEED_MMS = 150.0` is legal with ~1.15× margin. **Raising `flush_every` buys the mission program nothing.**
Honest corollary: that margin exists *only because the program keeps no per-tick evidence* — add the telemetry the
Intro Report wants at the current default and the tail ceiling collapses to 88 mm/s, at which point the fix is
`flush_every=25`, not slowing down. *Margin caveat:* p95 = 55 ms is `follow_tape`'s non-flush population and main.py's
body is heavier (two encoder-pair reads per tick); at 10 ms of body the margin is ~1.05×.

---

## 5. Two-speed policy (transit vs search)

Geometry from `sweep.SweepPlan` at 914 mm, pitch 41 mm: **23 lanes × 914 mm with `detect=True` = 21 022 mm (95.9 % of
driven distance)**; 22 sideways steps × 41 mm with `detect=False` = 902 mm (4.1 %); 44 × 90° turns, `detect=False`.
Turn time from the MEASURED 95 mm track (spin rate = 1.2062 × v deg/s). *Calibration:* the same arithmetic on the 3048
mm / 75-lane arena reproduces the 1618 s figure `mission_config.py` already carries.

| Scenario | search | transit | lanes | steps | turns | **total** |
|---|---|---|---|---|---|---|
| (a) **today, untouched** | 150 | 150 | 140.1 s | 6.0 s | 21.9 s | **168.0 s** |
| (a') forced to 114 mm/s (per-tick log @ flush 10) | 114 | 114 | 184.4 | 7.9 | 28.8 | 221.1 s |
| (b) one speed at the flush-free ceiling | 221 | 221 | 95.1 | 4.1 | 14.9 | 114.1 s |
| (c) **two-speed** | 150 | 309 | 140.1 | 2.9 | 10.6 | **153.7 s** |
| (d) both | 221 | 309 | 95.1 | 2.9 | 10.6 | 108.7 s |

**The two-speed policy is worth 14.4 s of 168.0 s = 8.5 %; raising the *search* speed is worth 54.0 s = 32.1 % — 3.7×
more.** Structural reason: 95.9 % of driven distance is under the sampling constraint, so the whole two-speed prize is
902 mm of stepping plus 44 turns. The 3.1 s step saving is largely illusory (a 41 mm step at 309 mm/s lasts 133 ms ≈
2.4 ticks, dominated by an unmeasured ramp and `drive_distance_mm`'s one-tick termination granularity). **11.3 s of
the 14.4 s is turn time.** (`_traverse_pct()` clamps transit to 60 % of 930 dps = 309 mm/s.)

⚠ **And the turn saving is the dangerous part, not the safe part.** `main.py.turn_degrees` is its own inline loop —
**`main.py` does not import `hub_drive` at all** — so the MEASURED `TURN_LEAD_DDEG = 28` (loop-latency compensation,
calibrated at ~48 deg/s) is **never applied by the mission program**, and `CMD_RESQUARE` is a no-op under
`BOUNDARY_MODE="odometry"`. Turn speed = drive speed = `_traverse_pct()`, and one 50 ms tick of spin is **9.0° at 150
mm/s, 13.3° at 221, 18.6° at 309** [COMPUTED]. Two same-direction turns per lane change, uncorrected, can leave the
return lane 10–20° off parallel — **160 to 310 mm of cross-track over a 914 mm lane**, against the
`CROSS_TRACK_ERROR_MM = 15.0` `[ASSUMED]` that *sets the lane pitch*. Doubling the sweep's largest uncorrected error
term to buy 11 s is absurd on demo morning.

---

## 6. Safe today vs after-demo

### ✅ SAFE TO TRY TODAY

1. **Do nothing to `TRAVERSE_SPEED_MMS`, `TICK_MS`, lane pitch, `flush_every` or any motor call.** The sweep finishes
   in 168 s against a 300 s box and `src/main.py` has never run.
2. **Builder: charge the pack.** [COMPUTED] sag cannot reach the motors (§8); what it *does* dim is the colour-sensor
   LED, and even there the rule has a 43-point gap (carpet 3–9, threshold 30, yellow 51–73, pink 97+).
3. **Builder: watch the turns and say what you see.** No lead compensation, no re-squaring (§5). If lanes visibly fan
   out, that is the mechanism, and an eyewitness account beats any log.
4. **Optional, only if `main.py` is being re-uploaded anyway:** add `flush_every=1` to the `CsvLog` in
   `_open_event_log()`. It appends ~once per mine, so at the default 10 a run finding fewer than 10 mines **never
   flushes**, and `close()` sits in a `finally` whose execution under a CENTER stop is ⚠ [UNVERIFIED]. Costs +50 ms
   after the edge has latched and cannot change the count — but **ranked below doing nothing**: the graded count comes
   from the matrix and the beep.
5. **Do not act on `mission_config.py`'s `TICK_MS=100` / 9.18 Hz / 112 mm/s comments** — stale (§3).

### 🔧 AFTER-DEMO, ranked

1. **Run `examples/straight_line_test.py`** (§7). Everything else here is worth seconds; this is worth the arena.
2. **One bounded slot program logging `dutyA_pct`/`dutyB_pct` and `hub.battery_voltage()` while driving at 100 / 150 /
   270 dps.** Duty under power has **never been observed on this robot** — the only captures read 0.0 in every row,
   the wheels having been turned by hand. Converts §2's H-bridge argument into measurement and leaves a permanent
   saturation detector.
3. **Explain the 300–813 ms stalls before raising any speed.** Test: the identical loop with logging disabled. If they
   vanish it is a telemetry artefact and `main.py` is clean; if not, the cause is likely GC and §3's blind-window
   table applies directly.
4. **Fix the turns** — the largest uncorrected error term. A *slower* turn speed, a shorter turn-loop tick, or the
   lead scaled to turn rate; re-measure `TURN_LEAD_DDEG` at two or three rates first.
5. **`src/hub_telemetry_log.py` default `flush_every` 10 → 25, plus fixed-phase scheduling** — copy
   `examples/telemetry_verbose_log.py`, which logs every tick at `flush_every=10` yet holds **p95 == median == 100.0
   ms, flush-bin delta +0.3 ms** across 25 logs / 7475 gaps [MEASURED] by advancing `next_t` and sleeping only the
   remainder. Benefits `examples/` only. **Never close-only.**
6. **Wire `ctx.tick_hz` into `config.max_safe_speed_mms()`** and clamp `TRAVERSE_SPEED_MMS` at DERIVE — the program
   measures the rate for `event_width_gates` but never feeds the function whose docstring says *"Call it with the rate
   the loop MEASURED"*. Use a **tail** estimate, discounted for the floor burst being a cheaper loop body.
7. **Decide the `max_safe_speed_mms` divisor — 3 as shipped, or the blend-corrected 3.86 — as an ADR** (29 % apart:
   221 vs 172 mm/s). Then **`acceleration=`** behind a start-up `try/except` fallback. **Leave `motor_pair` alone; do
   not pursue open-loop PWM** (§2).

---

## 7. The bench test that would measure the real envelope

**`examples/straight_line_test.py` is already written and has NEVER BEEN RUN.** It sets `SPEED_DPS = 270` with the
comment *"~150 mm/s, the configured traverse speed — measure the drift AT THE SPEED"* and logs with
`prefix="straight"`. There is **no `*-straight-*.csv` anywhere in `tmp/telemetry/`** and no mention of the file
anywhere in `docs/` [MEASURED by inspection]. One run closes three things: **straightness above 120 dps** (the longest
clean straight ever driven is ~305 mm at 120 dps and the highest sustained command in *any* retrieved telemetry is
**150 dps for 29.2 s** — ⚠ the often-cited "250 dps 1.5 s fragment" **is not in `tmp/telemetry/`**; the *programs*
exist, the *runs* do not); **`CROSS_TRACK_ERROR_MM`** `[ASSUMED] 15.0`, which *sets* lane pitch at 41 mm and so stands
between 75 lanes and 38; and **whether heading wander is bias or zero-mean noise** (bias costs 85 mm over 3048 mm,
noise almost nothing).

**Procedure.** Power-cycle the hub first (REPL work kills the Hub OS, and a slot upload then aborts). Upload via
`hub_programmer/slot_upload.py --apply`, entry named `program.py`. Mark a start line, a 2 m straight and the
**intended centreline**. Three passes at `SPEED_DPS = 270`, then — if clean — three at 150 and three at 400, same
distance each, tape-measuring the **signed lateral offset from the centreline at the stop point** (left positive).
Consistent sign is bias, alternating signs are noise, magnitude *is* `CROSS_TRACK_ERROR_MM`. Batch every `download.py`
retrieve into one call at end of session. Push to the fastest speed that still tracks straight, to find the *control*
ceiling — it may sit below the sampling ceiling, closing the speed question permanently.

---

## 8. Open questions

- **Battery sag — closed by arithmetic, open to measurement.** The closed loop holds commanded dps *exactly* until
  required duty exceeds 100 %, then silently under-delivers. [COMPUTED] full-duty loaded speed on carpet: **~1239 dps
  at 8.30 V, 1069 at 7.2 V, 961 at 6.5 V, 884 at 6.0 V** — against a fastest-ever-permitted 292 dps, a 3–4× margin, so
  **sag cannot reach the motors**. MEASURED pack: **8270–8327 mV over 412 samples on battery, USB unplugged**
  (2026-09-03). No *driving* log carries voltage, so this stays [COMPUTED]. Limit detectors: `get_duty_cycle()` pinned
  near ±10000 (**never observed under power**), commanded-minus-achieved dps persistently negative, `motor.status() ==
  STALLED`.
- **Why is `max_speed` 930 and not 1110?** No source — repo, docs-rag, ResearchHub or web — explains it. Curiosity,
  not a blocker. Likewise **is `set_duty_cycle` clamped by `max_speed`?** [UNVERIFIED], untestable without hardware.
- **Does `motor.run(..., acceleration=N)` accept the keyword on OUR Hub OS, and in what units?** A start-up
  `try/except` settles the first; the percent-vs-deg/s² clash (§2) means the second needs a measured ramp. **And the
  firmware's default acceleration?** Unresolvable from existing logs — 53 ms sampling with 1° encoder quantisation
  gives ±19 dps per interval; all that can honestly be said is the ramp completes within ~100–150 ms,
  indistinguishable across ~600–2000 deg/s².
- **What causes the 300–813 ms stalls?** [MEASURED, deduplicated] 6 gaps ≥ 300 ms in 163.3 s of `TICK_MS=50` driving
  (813, 628, 594, 398, 358, 313 ms); 5 of 6 sit in one `seq%10` bin adjacent to the flush bin, consistent with a FAT
  sector-erase cost — but MicroPython publishes no flush-latency figures, so that stays a hypothesis. ⚠ *Exclusion
  declared:* `calibrate_directions` adds 5 more (including 1884 ms), excluded as deliberate inter-primitive pauses;
  the raw figure across all driving families is **11 gaps ≥ 300 ms in 230.2 s**.
- **Does `main.py`'s `finally` — and so `CsvLog.close()` — run under a CENTER stop?** [UNVERIFIED, never observed].
  60-second test: start a slot program, let it write 15 rows, press CENTER, download, look for `#end`.
- **Does `motor_pair.move_tank` drive straighter than two `motor.run` calls?** Never run here, no source claims
  synchronisation. A/B on the bench, after `calibrate_directions.py` is re-run.

---

## Sources and which tool found what

**Our own repo was authoritative and outranked everything external:**
[../archives/hub-baseline/03-api-surface.txt](../archives/hub-baseline/03-api-surface.txt),
[../findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md),
[./speed-envelope.md](./speed-envelope.md),
[../plans/speed-and-heading-precision-2026-09-08.md](../plans/speed-and-heading-precision-2026-09-08.md),
[../plans/competition-program-readiness-2026-09-09.md](../plans/competition-program-readiness-2026-09-09.md),
[../findings/stopping-and-restarting-the-hub-2026-09-08.md](../findings/stopping-and-restarting-the-hub-2026-09-08.md),
plus `src/main.py`, `src/mission_config.py`, `src/sweep.py`, `src/hub_drive.py`, `src/hub_telemetry_log.py`,
`examples/{straight_line_test,telemetry_verbose_log,find_corner}.py`, and own re-analysis of the 106 CSVs in
`tmp/telemetry/`.

- **docs-rag** — near-zero and partly broken today: several `/api/ask` calls returned *"The embedding backend could
  not process this query"*, `/api/search` an empty body. Its one synthesis — 930 as "a firmware-imposed ceiling" —
  cited **no sources** and is **rejected** above. Plain `grep` over `docs/plans/` found the two load-bearing documents
  it did not.
- **ResearchHub** (`./scripts/rh-query.sh`, ran, DEGRADED as expected, exit 0) — **no value here:** LEGO Shop,
  Wikipedia, Target and Amazon pages, one irrelevant arXiv paper (*LEGO: Leveled Language Gaussian Splatting*), and,
  for a PID query, *"Pelvic inflammatory disease — Mayo Clinic"*.
- **Web (WebFetch/WebSearch)** — decisive for the three things the repo lacked: LEGO's own Medium Angular 45603 fact
  sheet, `pdftotext`-extracted from the LEGO CDN PDF (no-load 185 RPM ±15 % @ 7.2 V, max efficiency 3.5 Ncm/135 RPM,
  stall 18 Ncm, 360 counts/rev); `motor.info()` defined as `(device_id, max_speed)`; and the `acceleration` / `±10000`
  ranges, on two independent SPIKE 3 mirrors (tuftsceeo, jvolkening). ⚠ **Neither mirror states its firmware
  generation** — only the URL slug says v3, and our `dir(motor)` corroborates the *names* only, so the `acceleration`
  kwarg and the ±10000 range stay [UNVERIFIED on our hub].

