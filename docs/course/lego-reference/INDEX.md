# LEGO Reference — INDEX

LEGO's own documents, supplied by the operator 2026-08-26. **Read-only originals.** Each has a
`.txt` sidecar (`pdftotext -layout`) so `grep` and the docs-rag can reach the content.

| File | What it is | Why it matters |
|---|---|---|
| `LegoTechnicalSpecifications.pdf` / `.txt` | The combined element spec sheet — hub, all three sensors, all three motors, in one document | **The authority.** Confirms figures we had been citing from separate per-element PDFs |
| `LegoRulerV1.1.pdf` / `.txt` | A printable ruler for measuring beams, axles and pins in LEGO units | Practical: lets the Builder identify part lengths without counting holes. The `.txt` is near-useless (it is a graphic) — **use the PDF** |

## What these confirmed

- **5×5 LED matrix, 25 white LEDs, each individually programmable and dimmable in 10 steps.**
  Not an OLED — the operator's own correction was right. This is what `src/hub_ui.py` targets, and the
  10-step dimming is more than the report pages need.
- Hub is **88.0 × 56.0 × 32.0 mm**, six LPF2 ports A–F, six-axis gyro, speaker, three buttons.
- Colour sensor **optimal reading distance 16 mm** — confirms the standoff the mounting design assumes.
- All sensor wires are **250 mm, fixed to the sensor**, which is what constrains sensor placement.
- Motor absolute position is **0–360° in Scratch but ±180° in Python** — a real trap for anything
  reading absolute position; our odometry uses *relative* position, so it is unaffected.

## ⚠ One genuine conflict between two LEGO-official sources

| Source | Distance sensor minimum range |
|---|---|
| This techspec sheet | *"Distance Sensing from **50** to 2000 mm"*, *"Range total: 50-2000 mm ±20 mm"* |
| LEGO's BLE protocol reference (`messages.rst`, cited in [../../research/bluetooth-control-plane.md](../../research/bluetooth-control-plane.md)) | **40**–2000 mm |

Both are LEGO's own. **Use 50 mm** — the larger minimum is the safe reading, because the failure mode is
asymmetric: below the minimum the sensor returns **`-1` (nothing detected), not "very close"**. Assuming
40 mm when the true floor is 50 mm means a wall at 45 mm reads as open space and the robot does not stop.
Assuming 50 mm when it is really 40 mm merely wastes a centimetre of standoff.

**Neither figure is measured on our hardware.** Both are UNVERIFIED here until the sensor is bought and
tested against a wall at known distances.
