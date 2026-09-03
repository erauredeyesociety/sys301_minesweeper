# Research — why an uploaded SLOT program doesn't run, and whether the host can drive a motor directly

**What this answers.** Two questions raised 2026-09-03 after
[`../../hub_programmer/slot_upload.py`](../../hub_programmer/slot_upload.py) uploaded a program to a
program slot, got a clean **Acknowledged** at every step (ClearSlot `0x46→0x47`, StartFileUpload
`0x0C→0x0D`, TransferChunk `0x10→0x11` with a matching CRC-32, ProgramFlow `0x1E→0x1F`), and yet **the
motor never turned and no `ConsoleNotification (0x21)` output arrived** — while the *identical* program
spins the motor perfectly over the MicroPython REPL paste path
([`../../hub_programmer/run.py`](../../hub_programmer/run.py)).

1. **Why doesn't the uploaded slot program run?** → It is uploaded under the **wrong file name**. LEGO's
   own reference client and the community VS Code extension both upload the program under the fixed name
   **`program.py`** (or `program.mpy` if pre-compiled); our client uploads it under the *source
   basename*. See § 2.
2. **Can the host drive a motor directly, with no user program?** → **No.** LEGO's published protocol
   has **no host→hub actuation message** at all — every motor/sensor "device message" is *read-only
   telemetry* nested inside `DeviceNotification (0x3C)`. See § 4.

> ## STATUS: primary-source (LEGO/spike-prime-docs) + reference-client cross-check, **NOT run on our hub**
>
> The filename fix (§ 2) is taken from **two independent sources that both actually run programs on Hub
> OS 3 hardware**: LEGO's own reference `examples/python/app.py` and PeterStaev's VS Code extension. It
> is the single change that makes our upload byte-identical to LEGO's working example. **But no upload
> has been re-run on our hub with the fix**, so "the program then runs" is `[UNVERIFIED]` on our
> hardware until § 5's bench step is done. The Q2 verdict (no direct actuation message) is a complete
> read of LEGO's message table and is primary-sourced.
>
> Hardware was forbidden for this task. Governing rules:
> [../directives/hardware-safety.md](../directives/hardware-safety.md) ·
> [../decisions/0001-stock-lego-firmware-only.md](../decisions/0001-stock-lego-firmware-only.md).
> Builds on: [program-upload-protocol.md](./program-upload-protocol.md) ·
> [device-notification-telemetry.md](./device-notification-telemetry.md) ·
> [../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md).

---

## 0. Bottom line

| Question | Answer | Confidence |
|---|---|---|
| Why doesn't the slot program run? | **Uploaded under the wrong file name.** The slot's runnable entry point is the file named `program.py` (raw source) or `program.mpy` (compiled). Our client uploads under the source basename, so ProgramFlow(Start, slot) *acknowledges* but finds no `program.py` to execute. | **High** — primary source + reference client agree exactly |
| Does a slot program need to be compiled to `.mpy`? | **No.** LEGO's reference uploads **raw `.py` source** named `program.py` and it runs. `.mpy` is an optional speed optimization. | **High** — LEGO `app.py` |
| Is the ProgramFlow byte layout wrong? | **No.** `1E 00 <slot>` (id 30, `stop=0`, slot) is exactly correct per LEGO docs. | **High** |
| Can the host command a motor directly, no program? | **No such message exists** in LEGO's published protocol. Actuation only happens *inside a running program*. | **High** — full message table read |
| So what is the path to "motors moving + BLE telemetry at once"? | **Fix the filename** so the slot program runs, and subscribe with `DeviceNotificationRequest (0x28)` for zero-hub-code telemetry while it drives. | **High** on mechanism; end-to-end `[UNVERIFIED]` on our hub |

**The exact one-line fix** (spec only — the client is not edited by this task): in `slot_upload.py`,
the file name sent in `StartFileUploadRequest` must be **`program.py`**, not the local basename. Detail
and the supporting `--name`/`--compile` options in § 3.

---

## 1. What we already had right

Cross-checking our client against LEGO's reference [`app.py`][app] and [`messages.py`][msgs] and
PeterStaev's extension [`shared-extension.ts`][pshared] / [`base-client.ts`][pbase], **everything except
the file name is correct**:

| Element | Our client | LEGO / PeterStaev reference | Verdict |
|---|---|---|---|
| Message IDs (Info 0x00, Uuid 0x1A/26, ClearSlot 0x46/70, StartFileUpload 0x0C/12, TransferChunk 0x10/16, ProgramFlow 0x1E/30, Console 0x21/33) | as listed | [messages.rst][msgsrst] ids in decimal — all match | ✅ |
| `ProgramFlowRequest` layout | `struct.pack("<BBB", 0x1E, 0x00, slot)` → `1E 00 slot` | `<BBB` = (id, **stop**, slot); `stop=0` = *don't stop* = **Start** ([msgs][msgs] `serialize`, [app][app] `ProgramFlowRequest(stop=False, slot=…)`) | ✅ correct |
| `StartFileUploadRequest` layout | `<B{n+1}sBI` = (id, name+NUL, slot, whole-file CRC) | identical ([msgs][msgs], [pupload][pupload]) | ✅ correct |
| `TransferChunkRequest` layout | `<BIH{size}s` = (id, running_crc, size, payload) | identical ([msgs][msgs]) | ✅ correct |
| CRC-32, seed 0, zero-padded to /4 | `binascii.crc32` with LEGO's align-4 padding | LEGO `crc.py` — identical | ✅ correct |
| Sequence order | Info → Uuid → Clear → StartUpload → chunks → ProgramFlow | LEGO: Info → **DeviceNotif** → Clear → StartUpload → chunks → ProgramFlow ([app][app]) | ✅ (LEGO's extra step is optional telemetry — see § 5) |
| **File name in `StartFileUploadRequest`** | **source basename** (`name = name_override or os.path.basename(local)`) | **fixed `program.py`** / `program.mpy` ([app][app], [pupload][pupload]) | ❌ **this is the bug** |

> **Byte-value sanity note.** The launching brief quoted our ProgramFlow payload as `1d 00 00`. `0x1d` =
> 29; the correct id is **`0x1e` = 30**, and the code emits `0x1E` (`PROGRAM_FLOW_REQUEST = 0x1E`). Treat
> `1d` as a transcription slip in the brief — but when the fix is bench-tested, **confirm the captured
> ProgramFlow bytes read `1e 00 <slot>`**; a genuine `0x1d` on the wire would be a *second*, unrelated
> bug (`0x1d`/29 is unassigned in [messages.rst][msgsrst]). `[UNVERIFIED]` which byte was actually
> captured.

---

## 2. Why the program does not run — the file name

### 2.1 The primary source: LEGO uploads `program.py`

LEGO's own reference client [`examples/python/app.py`][app] does exactly the upload+start sequence we
do, and it names the file **`program.py`**, uploading **raw Python source** (no `.mpy`, no mpy-cross):

```python
EXAMPLE_PROGRAM = """import runloop
from hub import light_matrix
print("Console message from hub.")
async def main():
    await light_matrix.write("Hello, world!")
runloop.run(main())""".encode("utf8")
...
start_upload_response = await send_request(
    StartFileUploadRequest("program.py", EXAMPLE_SLOT, program_crc),   # <-- fixed name
    StartFileUploadResponse,
)
...
start_program_response = await send_request(
    ProgramFlowRequest(stop=False, slot=EXAMPLE_SLOT), ProgramFlowResponse
)
```

Source: [LEGO/spike-prime-docs `examples/python/app.py`][app]. The docstring states its purpose is
"Transfer and start a new program", and LEGO ships it as a *working* example against Hub OS 3.

### 2.2 The reference client agrees, and reveals *why* the name is load-bearing

PeterStaev's VS Code extension (its 2.x line "works ONLY with HubOS3"
[[issue #55]](https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode/issues/55)) uploads with
the **same fixed stem**, and chooses the *extension* by whether it pre-compiled ([pupload][pupload]):

```ts
await client!.startFileUpload(`program.${isCompiledIn ? "mpy" : "py"}`, slotId, crc32WithAlignment(data));
```

That the client switches the name between `program.py` and `program.mpy` by compile state tells us the
hub **keys the slot's runnable file on that name**: the `.py`/`.mpy` **extension is the signal for how
to load it** (interpret source vs. load bytecode), and both independent clients pin the **stem to
`program`**. A file uploaded under any other name is stored bytes the slot runner does not treat as the
entry point.

### 2.3 The symptom matches exactly

`ProgramFlowRequest` selects the program by **slot number**, not by file name ([msgsrst][msgsrst] id 30:
`uint8 Program action`, `uint8 Program slot`). So `ProgramFlowResponse` **Acknowledges** — the message
was well-formed and the "start slot N" command was accepted — but slot N has no `program.py` entry point
to execute, so **nothing runs, no `print()` is emitted, and the motor stays still.** This is precisely
the reported behaviour: every step Acks, and neither `ConsoleNotification (0x21)` nor a
`ProgramFlowNotification (0x20)` follows.

The same program running over the REPL paste path succeeds because that path never uses a slot at all —
it pastes source straight into the live MicroPython VM ([`run.py`](../../hub_programmer/run.py)), so the
file-name/slot machinery is bypassed. That is why "the code is correct" and "the slot doesn't run" are
both true.

### 2.4 Sub-questions from the brief, answered

- **Does `StartFileUploadRequest` + `TransferChunk` upload to a runnable slot, or a staging area?** It
  uploads to the slot named in the request (`StartFileUploadRequest` carries `slot`); the file becomes
  the slot's program **only if named `program.py`/`program.mpy`**. There is no separate "commit"/"staging"
  step — no message between the last chunk and `ProgramFlow` in either reference client
  ([app][app], [pbase][pbase]). `[ASSUMED]` from the two clients that the name (not just any `.py`) is
  what the runner opens; the residual is closed by § 5's bench test.
- **Must a SPIKE 3 slot program be compiled to `.mpy`?** **No.** LEGO's `app.py` uploads raw `.py` source
  and runs it ([app][app]); PeterStaev makes compilation an *optional* "Compile Before Upload" setting
  for faster start, not a requirement
  [[extension README]](https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode). (Older claims
  that "the hub only stores `.mpy`" and uses `/projects/<id>/__init__.mpy` describe **Hub OS 2 / SPIKE
  Legacy** JSON-RPC storage, a different stack — do not apply them to our measured SPIKE 3 hub.)
  `[UNVERIFIED]` whether the hub transparently compiles the received `.py` to `.mpy` on its own
  filesystem; irrelevant to the client, which just sends `program.py` + raw bytes.
- **Required name / header / metadata / manifest?** The **name** `program.py` is the only requirement
  established by the references. There is **no manifest and no metadata message** in the upload path
  ([app][app] sends none). PeterStaev's `# LEGO slot:N autostart` first-line comment is an **editor-side
  convention** parsed by the *extension* to pick the slot, **not** anything the hub reads
  ([pshared][pshared] `getProgramInfo`) — do not add it to the payload.
- **Does `ProgramFlow` Start need a preceding step or different action/slot encoding?** No preceding step
  beyond having uploaded `program.py` to that slot. `action` is a `stop` boolean: `0x00` = Start, `0x01`
  = Stop ([msgs][msgs], [enumsrst][enumsrst]). `1E 00 <slot>` is correct.
- **What does `ProgramFlowNotification (0x20)` report, and would a crash show there?** Only a single
  `uint8 stop` byte ([msgsrst][msgsrst] id 32) — `0` on start, `1` on stop. It carries **no reason, no
  slot, no traceback**: a clean exit, an operator Stop, and a crash all surface as `stop=1`. To learn
  *why*, read the `ConsoleNotification (0x21)` text — whether an uncaught-exception traceback is
  forwarded there is `[UNVERIFIED]` on our hub (KU carried from
  [program-upload-protocol.md](./program-upload-protocol.md) § 6). In our failure, **no `0x20` arrived
  at all**, consistent with "the runner found nothing to start" rather than "the program started and
  crashed".

---

## 3. The exact fix (spec for `slot_upload.py` — not applied by this task)

Change **one thing**: the file name sent in `StartFileUploadRequest` must be `program.py` (raw source)
or `program.mpy` (only if the bytes are genuinely mpy-cross output). Concretely:

1. **Default the upload name to `program.py`.** Today `main()` sets
   `name = name_override or os.path.basename(local)`. It should instead default to **`program.py`** (and
   `program.mpy` when a `--compile`/`--mpy` path is used), regardless of the local file's name. Keep
   `--name` as an override for experiments, but the *default* must be `program.py`.
2. **Keep sending raw `.py` bytes** — no mpy-cross needed (§ 2.4). The blacklist forbids toolchain
   flashing but says nothing against mpy-cross; still, raw `.py` is the proven-by-reference path and
   needs no extra tool, so **stay on `.py`**.
3. **The name's extension must match the payload.** If a future change pre-compiles, send the `.mpy`
   bytes **and** name it `program.mpy`; never send raw source named `.mpy` or bytecode named `.py`.
4. **Everything else stays** — ClearSlot, the whole-file/running CRC pair, chunk size ≤ `max_chunk_size`
   (4096, a multiple of 4), and `ProgramFlow 1E 00 <slot>` are all already correct (§ 1).

Pseudo-diff (illustrative — do **not** treat as applied):

```text
# in main():
- name = name_override or os.path.basename(local)
+ name = name_override or "program.py"   # slot entry point MUST be program.py / program.mpy
+                                         # (LEGO app.py, PeterStaev extension) — not the source basename
```

### Corrected sequence

```mermaid
sequenceDiagram
    participant H as Host (slot_upload.py)
    participant K as Hub (Hub OS 3)

    Note over H,K: USB /dev/spike (no Ctrl-C) or BLE (scan our address, connect)
    H->>K: InfoRequest 0x00
    K-->>H: InfoResponse 0x01 (max_chunk_size 4096, max_packet_size 509)
    H->>K: DeviceUuidRequest 0x1A
    K-->>H: DeviceUuidResponse 0x1B + 16-byte UUID
    Note over H: compare to our UUID — MISMATCH ⇒ write nothing
    opt telemetry-while-driving (§5)
        H->>K: DeviceNotificationRequest 0x28 (interval_ms)
        K-->>H: DeviceNotificationResponse 0x29 (Ack)
    end
    H->>K: ClearSlotRequest 0x46 (slot)
    K-->>H: ClearSlotResponse 0x47 (Ack, or Nak = was empty)
    Note over H: file_crc = crc(whole_file, seed=0)
    H->>K: StartFileUploadRequest 0x0C ("program.py", slot, file_crc)
    K-->>H: StartFileUploadResponse 0x0D (Ack)
    loop each chunk ≤ 4096 (running = crc(chunk, running))
        H->>K: TransferChunkRequest 0x10 (running_crc, size, payload)
        K-->>H: TransferChunkResponse 0x11 (Ack)
    end
    H->>K: ProgramFlowRequest 0x1E (stop=0, slot)
    K-->>H: ProgramFlowResponse 0x1F (Ack)
    K-->>H: ProgramFlowNotification 0x20 (stop=0 — STARTED)
    K-->>H: ConsoleNotification 0x21 "print() output…"
    K-->>H: DeviceNotification 0x3C (motor pos/speed/power, IMU, sensors)
    Note over K: motor turns; telemetry streams with no hub-side telemetry code
```

The **only** difference from what we already send is the `"program.py"` literal in the
`StartFileUploadRequest` box (and the optional `DeviceNotificationRequest` for telemetry).

---

## 4. Q2 — can the host drive a motor directly, with no user program?

**No.** The complete top-level message table in LEGO's [messages.rst][msgsrst] is:

| ID (dec / hex) | Message | Direction | Purpose |
|---|---|---|---|
| 0 / 0x00, 1 / 0x01 | InfoRequest / Response | H↔K | capabilities (chunk/packet sizes) |
| 10 / 0x0A, 11 / 0x0B | StartFirmwareUpload… | H→K | **FIRMWARE — blacklisted, refused in code** |
| 12 / 0x0C, 13 / 0x0D | StartFileUpload… | H→K | begin a slot file upload |
| 16 / 0x10, 17 / 0x11 | TransferChunk… | H→K | upload bytes |
| 20 / 0x14, 21 / 0x15 | BeginFirmwareUpdate… | H→K | **FIRMWARE — blacklisted, refused in code** |
| 22 / 0x16, 23 / 0x17 | SetHubName… | H→K | rename the hub |
| 24 / 0x18, 25 / 0x19 | GetHubName… | H↔K | read the hub name |
| 26 / 0x1A, 27 / 0x1B | DeviceUuid… | H↔K | identity (our hub gate) |
| 30 / 0x1E, 31 / 0x1F | ProgramFlow… | H→K | **start/stop a stored slot program** |
| 32 / 0x20 | ProgramFlowNotification | K→H | program started/stopped |
| 33 / 0x21 | ConsoleNotification | K→H | `print()` / stdout text |
| 40 / 0x28, 41 / 0x29 | DeviceNotification**Request**/Response | H→K | **subscribe** to telemetry (interval ms) |
| 50 / 0x32 | TunnelMessage | H↔K | opaque byte pipe to/from a running program |
| 60 / 0x3C | DeviceNotification | K→H | **telemetry snapshot** (battery, IMU, motors, sensors) |
| 70 / 0x46, 71 / 0x47 | ClearSlot… | H→K | erase a slot |

Every one of these is either **firmware** (refused), **program-lifecycle** (upload/start/stop a slot),
**config/identity** (name, UUID, info), **telemetry subscription/stream**, or the **tunnel**. **None is
a device/port actuation command.** In particular:

- **`DeviceMotor` and friends are telemetry, not commands.** The nested "device messages"
  (`DeviceMotor` id 10, `DeviceColorSensor` id 12, `DeviceDistanceSensor` id 13, `DeviceImuValues` id 1,
  …) exist **only inside `DeviceNotification (0x3C)`**, which is **hub→host** ([msgsrst][msgsrst] lines
  199–292). `DeviceMotor` reports *port, motor type, absolute position, power, speed, cumulative
  position* — it **reads** the motor, it cannot **drive** it. There is no `DeviceNotification`
  counterpart in the host→hub direction, and no `PortOutput` / `DeviceWrite` / `MotorCommand` message
  anywhere in the table.
- **`TunnelMessage (0x32)` is not an actuation shortcut.** It is a raw `uint16 size` + `uint8[size]`
  byte pipe ([msgsrst][msgsrst] id 50). The firmware only **relays** those bytes to/from the **running
  program**; a program must be running *and* reading the tunnel and calling `motor.run()` itself.
  Without a user program there is nothing on the hub end to act on tunnel bytes. So the tunnel still
  requires the slot program to run — it does not bypass it. `[UNVERIFIED]` exactly which MicroPython API
  the running program reads the tunnel through on our build (carried from
  [telemetry-offload-paths.md](./telemetry-offload-paths.md)).

**Consequence.** The premise "the LEGO app drives motors in real-time without uploading a program" is
**not supported by LEGO's published protocol** — there is no message that would let it. If the SPIKE app
appears to do live motor control, it is doing it by running a resident program on the hub that listens
(via the tunnel or its own loop) and actuates, **not** by a firmware-level motor command. `[UNVERIFIED]`
/ `[ASSUMED]` — we could not source any live-control-without-a-program mechanism; the burden of proof is
on the claim, and the message table refutes the simple reading of it.

**Therefore fixing slot execution (§ 2–3) is not just *a* path to "motors + telemetry", it is the
*only* stock-firmware path.** There is no simpler direct-command alternative to fall back to.

---

## 5. The recommended path to "motors moving + BLE telemetry at once"

Both halves are already sourced and need no hub-side telemetry code:

1. **Make the slot program run** — apply the § 3 filename fix, then bench-test over **USB first**
   (point-to-point, cannot hit another team's hub). Upload the known-good spin-and-print program named
   `program.py`, `ProgramFlow(Start)`, and confirm (a) the motor turns and (b) `ConsoleNotification
   (0x21)` carries the prints. File the raw transcript under [../findings/runs/](../findings/runs/).
2. **Stream telemetry with zero hub code** — after identity and before/after start, send
   **`DeviceNotificationRequest (0x28)`** with an interval (LEGO's `app.py` uses 5000 ms; we'd pick
   faster). The hub then pushes **`DeviceNotification (0x3C)`** snapshots of every motor's
   position/speed/power plus IMU and sensors **while the slot program drives** — the untethered witness
   described in [device-notification-telemetry.md](./device-notification-telemetry.md) and
   [telemetry-while-driving.md](./telemetry-while-driving.md). This is an **off-VM** channel: it does
   not depend on the program's `print()` and sidesteps the `print()`-stall unknowns.

This is exactly the sequence in LEGO's `app.py` (which subscribes to `DeviceNotification` *and* starts a
program in one session), so it is a known-good composition, not a novel one. End-to-end on **our** hub it
is `[UNVERIFIED]` until step 1 is run.

### Firmware safety is unchanged

Storing `program.py` in a slot is a **filesystem write**, the same class as ADR-0007's `/flash/lib`
write — it cannot alter the MicroPython firmware image
([../findings/firmware-integrity-proof.md](../findings/firmware-integrity-proof.md)). The dangerous ids
`0x0A/0x0B/0x14/0x15` are firmware and remain refused in the client's `send()` allowlist-by-exclusion.
The filename fix does not touch any of that.

---

## 6. `[UNVERIFIED]` register — what a bench run must still close

| # | Open item | What settles it |
|---|---|---|
| 1 | The filename fix makes the program actually run on **our** hub. | Upload `program.py` to slot 0 over USB, `ProgramFlow(Start)`, watch the motor turn and `0x21` prints arrive. |
| 2 | Whether the hub keys on the exact stem `program`, or on the `.py` **extension** alone (i.e. would the old basename have run if it ended in `.py`?). | Upload once as `program.py` (expect run) and once as `notprogram.py` to a throwaway slot (expect no run); compare. |
| 3 | Does a natural exit emit `ProgramFlowNotification stop=1`, and is an uncaught traceback forwarded to `0x21`? | Upload a program that returns, and one that raises; watch `0x20`/`0x21`. |
| 4 | Does the hub compile the received `.py` to `.mpy` on its own FS, and under what path? | After a successful run, list `/flash` over a separate REPL session and diff. |
| 5 | `DeviceNotification (0x3C)` actually streams while a slot program drives a motor (no starvation). | Subscribe `0x28`, run the spin program, confirm `0x3C` motor records advance. |
| 6 | The captured `ProgramFlow` bytes are `1e 00 <slot>`, not `1d …`. | Re-read the raw frame the client prints. |
| 7 | BLE behaves the same as USB for the fixed-name upload (bonding, MTU). | Repeat step 1 over `--ble` after USB passes. |

---

## 7. Sources

Primary — **LEGO/spike-prime-docs** (`main`), read at source this session:

- Reference upload+start client, showing `StartFileUploadRequest("program.py", …)` and
  `ProgramFlowRequest(stop=False, …)` with a **raw-`.py`** program body: [`examples/python/app.py`][app].
- Message layouts/serialize code (`StartFileUploadRequest` name+NUL+slot+crc; `ProgramFlowRequest`
  `<BBB` id/stop/slot; `ProgramFlowNotification` single `stop` byte; `DeviceNotificationRequest`/
  `DeviceNotification`): [`examples/python/messages.py`][msgs].
- Full message-id table and the device-message list under `DeviceNotification` (id 60), confirming no
  host→hub actuation message and that `DeviceMotor` (id 10) is read-only telemetry:
  [`docs/source/messages.rst`][msgsrst].
- Program action (Start=0/Stop=1) and response-status enums: [`docs/source/enums.rst`][enumsrst].

Reference client that runs programs on Hub OS 3 hardware — **PeterStaev/lego-spikeprime-mindstorms-vscode** (`master`):

- `uploadProgramToHub` naming the file `program.${isCompiledIn ? "mpy" : "py"}`: [`src/shared-extension.ts`][pupload].
- `startFileUpload` / `transferChunk` / `startStopProgram` sequence (no manifest step):
  [`src/clients/base-client.ts`][pbase].
- Editor-side `# LEGO slot:N autostart` header parsing (hub does **not** read it):
  [`shared-extension.ts` `getProgramInfo`][pshared].
- Hub OS 3-only note: [issue #55](https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode/issues/55).

Our own prior research this builds on and refines:
[program-upload-protocol.md](./program-upload-protocol.md) (had the sequence right but carried the
basename bug in the client), [device-notification-telemetry.md](./device-notification-telemetry.md),
[telemetry-while-driving.md](./telemetry-while-driving.md),
[telemetry-offload-paths.md](./telemetry-offload-paths.md);
measured ground truth [../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md),
[../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md).

[app]: https://github.com/LEGO/spike-prime-docs/blob/main/examples/python/app.py
[msgs]: https://github.com/LEGO/spike-prime-docs/blob/main/examples/python/messages.py
[msgsrst]: https://github.com/LEGO/spike-prime-docs/blob/main/docs/source/messages.rst
[enumsrst]: https://github.com/LEGO/spike-prime-docs/blob/main/docs/source/enums.rst
[pupload]: https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode/blob/master/src/shared-extension.ts
[pbase]: https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode/blob/master/src/clients/base-client.ts
[pshared]: https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode/blob/master/src/shared-extension.ts
