# Hub Baseline — INDEX

**The hub exactly as we found it, 2026-08-27, before anything was ever written to it.**

Captured by [`probes/capture_baseline.py`](../../../probes/capture_baseline.py), which is read-only on
the hub and writes only to this folder.

> **The point of this folder is not the snapshot — it is the diff.**
>
> If anything on this hub ever changes (by us, by a teammate, by the LEGO app, by a firmware update
> somebody accepted), we need to *prove* what changed rather than argue about it. That is the whole
> reason this exists, and it is why the capture is a re-runnable script and not a screenshot.

```bash
python3 probes/capture_baseline.py --to /tmp/now
diff -ru docs/archives/hub-baseline /tmp/now
```

**A clean diff means the hub is untouched.** Any hunk outside `06-runtime-state.txt` is a real change
and needs an explanation.

---

## Known post-baseline deltas — the diff is no longer expected to be empty

**2026-08-27, later the same day: one module was uploaded** to the hub —
`/flash/lib/config.py`, 13262 bytes, by `hub_programmer/upload.py --apply`
([ADR-0007](../../decisions/0007-deploy-by-writing-modules-to-flash-lib.md)). The capture was re-run to
a temp directory and diffed, and **this is the complete difference**, all of it:

```
04-filesystem.txt
  - ['README.txt','boot.py','config','main.py','program','pybcdc.inf']
  + ['README.txt','boot.py','config','lib','main.py','program','pybcdc.inf']
  - [('README.txt',528),('boot.py',196),('config',196),('main.py',34),('program',34),('pybcdc.inf',2597)]
  + [('README.txt',528),('boot.py',196),('config',196),('lib',196),('main.py',34),('program',34),('pybcdc.inf',2597)]
  - statvfs free blocks 7923
  + statvfs free blocks 7915

06-runtime-state.txt
  - battery 7942 mV,  temperature 247
  + battery 8001 mV,  temperature 251
```

| Hunk | Cause | Expected? |
|---|---|---|
| `lib` appears in the `/flash` listing, nothing removed or renamed | The upload created the directory. It did not exist, but was already on `sys.path` | **Yes** |
| `('lib',196)` in the size table; **every stock size byte-identical** | 196 is what a directory entry reports here, the same as the stock `config` directory | **Yes** |
| `statvfs` free blocks 7923 → 7915 | 8 blocks × 4096 B = **32,768 B** consumed. ⚠ The 13262-byte file needs 4 blocks and the directory at least 1; **3 of the 8 are unaccounted for and `[UNVERIFIED]`** — no cluster geometry has been invented to make the arithmetic close | **Yes**, with a caveat |
| battery 7942 → 8001 mV, temperature 247 → 251 | Charging over USB and self-heating. `06-` is volatile by design | **Yes — means nothing** |

**Files `01-identity.txt`, `02-modules.txt`, `03-api-surface.txt` and `05-stock-files.txt` produced no
diff at all.** That absence is the load-bearing part: a firmware change would show up there or nowhere.

**How to use this section.** Re-run the capture and diff. If what you get is *exactly* the above, the
hub is in its known state. **A hunk that is not in this table — and above all any hunk in `01-`, `02-`,
`03-` or `05-` — is a real change: stop, preserve the temp capture as evidence, and get the operator.**
Do not re-baseline to make the diff clean; that destroys the only thing this folder is for. Full
walk-through: [../../findings/firmware-integrity-proof.md](../../findings/firmware-integrity-proof.md).

| File | What it pins down |
|---|---|
| [01-identity.txt](./01-identity.txt) | `device_uuid`, `hardware_id`, `machine.unique_id()`, `os.uname()`, `sys.implementation`, `sys.path`. **Our hub's permanent identity** — the thing a BLE advertisement gets matched against. |
| [02-modules.txt](./02-modules.txt) | The complete `help('modules')` list. **The evidence that this is SPIKE 3** — `motor`/`motor_pair`/`runloop` present, `spike` absent. If a firmware change ever happened, this file is where it would show first. |
| [03-api-surface.txt](./03-api-surface.txt) | `dir()` of every module we care about: `motor`, `motor_pair`, `runloop`, `color_sensor`, `color`, `device`, `hub.motion_sensor`, `hub.light_matrix`, `bluetooth.BLE`, `machine`, `vfs`. **The API we write mission code against**, measured rather than looked up. |
| [04-filesystem.txt](./04-filesystem.txt) | `/flash` listing, sizes, modes, `os.statvfs`. Records that `/flash/program` was **empty**, `/flash/lib` did **not** exist, and 32.4 MB was free. |
| [05-stock-files.txt](./05-stock-files.txt) | **The pristine contents of `README.txt`, `boot.py`, `main.py`.** The file that matters most: if we ever overwrite `main.py`, this is what it said beforehand, verbatim. |
| [06-runtime-state.txt](./06-runtime-state.txt) | Battery, temperature, free memory. **Volatile by design** — these differ every run and a diff here means nothing on its own. |

## Rules for this folder

- **Never edit these files by hand.** They are a record of what the hardware said. Re-run the capture
  instead.
- **Do not re-capture over the baseline after the hub has been modified.** That destroys the very
  thing it exists for. Capture to a new location and diff.
- If the hub is ever legitimately changed, record *why* as an [ADR](../../decisions/) and capture a
  **second, dated** baseline alongside this one rather than replacing it.

**Related:** [../../findings/hub-first-contact-2026-08-27.md](../../findings/hub-first-contact-2026-08-27.md)
— what these captures mean · [../../decisions/0001-stock-lego-firmware-only.md](../../decisions/0001-stock-lego-firmware-only.md)
— why the firmware is never touched
