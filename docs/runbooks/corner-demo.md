# Runbook — The corner demo (`examples/find_corner.py`)

**Owner:** **Builder** operates the robot (roles are enforced, −2 SB per violation) ·
**Programmer** at the laptop, may plug/unplug only.
**Time:** ~6 min setup, ~50–90 s per attempt, ~2 min to pull and decode the log.
**Status: [UNVERIFIED] — this program has never been run.** Every step below is written from the two
programs it is copied from, both of which HAVE run untethered on battery
([`drive_to_tape.py`](../../examples/drive_to_tape.py), [`motor_poc.py`](../../examples/motor_poc.py)).
Design: [../plans/border-trace-and-corners-2026-09-08.md](../plans/border-trace-and-corners-2026-09-08.md)

## What this demonstrates

The robot drives out, finds the taped boundary using a threshold **measured on this exact carpet and
this exact tape** (2026-09-08), walks along the boundary by repeated touches, and tells you whether it
is standing at a **corner** or on a **straight stretch** — with every distance, heading and bearing
written to a CSV on the hub. It is **not** a perimeter lap and must not be described as one.

## 1. Physical setup

| Item | Value |
|---|---|
| Tape | The real blue painters tape, laid as a corner on the real carpet |
| Two legs of the corner | **≥ 900 mm each** — the program walks up to ~1.2 m of edge |
| Robot start position | **300–600 mm from one leg**, on carpet, **facing that leg** roughly square |
| Clear floor around the start | **≥ 1.5 m** in every direction |
| Battery | Charged. ⚠ No discharge curve exists (KU-M11); the longest untethered run on record is 45 s |
| Two mines (optional) | Place a yellow and a pink note nearby — they can never trip the tape rule (measured blue fraction 0.291–0.300 vs the 0.44 threshold), so they are a free negative control |

**Set `SIDE` before uploading.** In [`find_corner.py`](../../examples/find_corner.py), `SIDE = 1` turns
**right** off the first touch, `SIDE = -1` turns **left**. It decides which way along the edge the robot
walks, so it must point *toward* the corner you want it to find. The program will not guess.

Also run a control attempt with the robot facing the **middle of a straight stretch**, at least 900 mm
from either corner. The expected result there is `EDGE_STRAIGHT`, and it is what shows the corner
verdict means something.

## 2. Steps

> ⚠ **POWER-CYCLE THE HUB before step 2.** `run.py` and anything in `probes/` send Ctrl-C, which kills
> the Hub OS; `slot_upload.py` needs it alive. If any REPL or probe work happened this session, unplug
> the hub, hold nothing, wait for it to shut down, and power it back on before uploading.

1. **Programmer** — confirm `SIDE` and that the hub is on `/dev/spike`.
2. **Programmer** — upload:
   ```
   ./hub_programmer/slot_upload.py examples/find_corner.py --apply
   ```
   Expect the hub to show **`S`** (armed) when it starts.
3. **Programmer** — **unplug the USB cable.** From here the robot runs on battery.
4. **Builder** — place the robot per § 1 and stand clear of the arena.
5. **Builder** — **tap LEFT or RIGHT once.** A 5 s countdown flashes (alternating full / box). Do not
   press and hold anything, and never press CONNECT while USB is being plugged in (blacklist item 2).
6. **Watch.** The run ends when the matrix shows one of the four glyphs in § 3. To abort at any time,
   **tap LEFT or RIGHT again** — the run stops, the motors are cut in a `finally`, and the log is still
   written and closed.
7. **Programmer** — replug USB once the robot has stopped, then:
   ```
   python3 hub_programmer/download.py --all
   ./scripts/decode_telemetry.py
   ```
   The CSV header is byte-identical to `motor_poc.py`, so the decoder needs no change.
8. **Programmer** — read the `#end` trailer line first. It carries everything the demo claims.
9. File the raw CSV under `docs/findings/runs/` before it is lost — `tmp/` is scratch, not a record.

## 3. What success looks like

The matrix glyph is the primary signal and is **PROVEN**; the beep is a bonus and is wrapped in
`try/except` because `hub.sound.beep`'s signature is **[UNVERIFIED]** on SPIKE 3 — silence is not a
failure.

| Glyph | Beep | `reason=` | Meaning |
|---|---|---|---|
| **X** | rising, two tones | `CORNER` | ✅ The bearing between boundary touches swung ≥ 45° consistently. `corner_deg` in the trailer is the measured turn |
| **–** (dash) | one mid tone | `EDGE_STRAIGHT` | ✅ **Also a success.** It walked its whole 7-touch budget along a straight stretch and correctly refused to invent a corner. This is the control case |
| **?** | falling | `LOST_EDGE` | The edge fell away — an approach ran its 277 mm cap with no tape. Honest, not a crash: see § 4 |
| **?** | falling | `NO_TAPE` | The initial seek ran ~1100 mm without finding tape. Placement or aim problem |
| **□** (box) | — | `STOP_button` / `time_cap` / `gyro_none` | Aborted. The log is still complete up to the abort |

A good `CORNER` run looks like this in the trailer (illustrative shape, **not** a measured result):

```
#end reason=CORNER touches=4 corner_deg=-83 turnsum_deg=-83 x_mm=310 y_mm=-105 rows=~380
```

Cross-checks to run on the decoded CSV, in order:

1. `touches` ≥ 3. Fewer than three touch points cannot produce a bearing change at all.
2. `corner_deg` between 45 and 150. A real box corner is ~90°; anything at exactly 45 is on the
   threshold and should be treated as unconfirmed.
3. The `approach*` phases each ended on tape, not on their cap — check the last `bC`/`bD` of each.
4. Yaw between consecutive `touch*` settles moves smoothly; a jump of >20° between settles inside one
   edge means a wheel slipped.

## 4. Failure modes and what each one means

| Symptom | What it means | What to do |
|---|---|---|
| `NO_TAPE` on the seek | Robot not aimed at the tape, or started further than ~1100 mm away | Re-place per § 1. Do **not** raise `SEEK_CAP_DEG` before checking the aim |
| `LOST_EDGE` on approach 1 or 2 | Almost always **`SIDE` is set the wrong way** — the robot turned away from the boundary and walked into open carpet | Flip `SIDE`, re-upload, retry. This is the single most likely first-run failure |
| `LOST_EDGE` later, after 3+ good touches | Either a real gap in the tape, or the boundary turned *away* from the robot — which happens if the robot is **outside** the box | Note the pose in the trailer. If the robot was outside the tape, no software fix exists in a wall-less arena: carpet resumes on both sides. It is a placement requirement |
| `EDGE_STRAIGHT` at a real corner | The corner is further than ~1.2 m of walking, or the bearing swing did not reach 45° | Start closer to the corner, or raise `MAX_TOUCH`. Do **not** lower `CORNER_MIN_DEG` below 45 without reading the bearing spread out of the log first — 45 is 13–16× the measured 2.6° yaw wander, and lowering it is how a wandering hand-laid edge becomes a phantom corner |
| `CORNER` on a straight stretch | A phantom. Read the per-touch bearings: if they alternate sign, the sign-consistency reset is not doing its job and `STITCH_DEG` is probably too large for this edge | Report it. Do not tune it away on demo day |
| Robot drives **backward** | The `DIRECTION` constant. ⚠ It is **1**, and that has been confirmed twice (2026-09-01, and again 2026-09-08 when a flipped run drove backward and the operator confirmed the original) | Do not flip it. Check the motor cables are on ports A and B as expected first |
| Robot armed sitting on the tape | Handled: the program samples once, and reverses off the tape before seeking | Nothing. Check the `clear` phase rows appear in the log |
| No rows / no file after download | The run never reached the logger, or the hub was Ctrl-C'd between upload and run | Power-cycle and re-upload. Do not chase it on the hub |
| Beeps silent, glyphs correct | Expected. `hub.sound.beep` is [UNVERIFIED] on SPIKE 3 and is deliberately swallowed | Nothing — record it as one more data point on KU |

## 5. Hard rules that apply to this run

- **Stock LEGO firmware only.** No DFU, no Hub OS update prompt accepted, no factory reset.
- **Never press-and-hold CONNECT while USB is being plugged in.** Any three-colour LED cycle
  (pink-green-blue-off) means stop and unplug — see [../research/ble-bring-up.md](../research/ble-bring-up.md).
- **Single button presses only.**
- **The Builder is the only person who touches the robot** once it is on the floor.
- **Report the glyph with the number, never the number alone.** "Corner, minus eighty-three degrees,
  four touches" — not "eighty-three".
