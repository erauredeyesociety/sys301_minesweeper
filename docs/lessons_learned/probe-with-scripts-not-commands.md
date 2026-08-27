# Probe with a Python script, never with a typed command

**Date:** 2026-08-27 · **Source:** the operator, on the day the hub was first connected:
*"if you run manual commands you are going to get hung up, it's just what happens — please probe with
python scripts"* and *"you can use bash commands inside python scripts if you need to make things
easier, I just would rather have a python script get hung up than you."*

**WHEN** you need to interrogate hardware, a serial port, a radio, a socket, or any other resource
that can block,

**DON'T** run the command inline from a tool call — not `screen`, not `cat /dev/ttyACM0`, not
`bluetoothctl scan on`, not a `read()` with no deadline. Write a script in [`probes/`](../../probes/)
that has an explicit timeout, and run that.

**BECAUSE** a blocking read from a tool call hangs the *session*, and there is no way out from the
inside. A script that hangs is a process the operator can kill, that exits on its own deadline, and
that can be re-run tomorrow to get the same answer.

## The distinction that makes this a rule and not a preference

**It is not "bash bad, Python good."** The operator was explicit that bash *inside* a Python script is
fine. The rule is about **who is holding the thing that can block**.

| | Blocks | Consequence |
|---|---|---|
| Tool call → `screen /dev/ttyACM0` | the agent session | Hangs. Unrecoverable from inside. |
| Tool call → `python3 probes/x.py` → `subprocess.run(..., timeout=5)` | the script | Exits. Prints. Re-runnable. |

The second one still runs bash. It just runs it behind a deadline, inside something disposable.

## What this cost before the rule existed

On 2026-08-27 the host Bluetooth stack was checked with inline `rfkill list`, `bluetoothctl show` and
`systemctl is-active`. **None of them hung** — they are fast, non-blocking commands, and it worked.

That is exactly why the operator raised it. **The habit is the hazard, not the individual command.**
`bluetoothctl` one keystroke different (`bluetoothctl scan on`) blocks forever. The commands that are
safe and the commands that hang look identical when you type them, and you find out which is which
after it is too late.

## How to apply

- **Every hub-touching or radio-touching operation gets a file in `probes/`.** One question per
  script, named for the question: `whoami.py`, `filesystem.py`, `ble_scan.py`, `bluetooth_state.py`.
- **Two deadlines, always** — a per-read timeout *inside* (pyserial `timeout=`, `subprocess` `timeout=`)
  and an outer one. Either alone eventually fails to save you.
- **Close the resource in a `finally:`.** A leaked port is how the *next* session concludes the
  hardware is broken.
- **Success means an observation, never the absence of an exception.** `probes/_hubio.py` returns
  success only if a `>>>` was actually seen; "no error" is not evidence the hub answered.
- **A script is re-runnable; a typed command is not.** The next person gets the answer by running the
  file, not by reconstructing a pipeline from a chat log. This is the same reason as
  [../directives/automation-first.md](../directives/automation-first.md): *script the ritual, don't
  re-improvise it inline.*
- **Read-only probes stay read-only.** `probes/` may `dir()`, read getters, list, and read files. A
  probe that writes to the hub, moves a motor, or instantiates a radio is no longer a probe — see
  [../runbooks/hub-identification.md](../runbooks/hub-identification.md) § 0.

**Related:** [../directives/automation-first.md](../directives/automation-first.md) ·
[say-which-kind-of-verified.md](./say-which-kind-of-verified.md) (the operator says when hardware is
connected; a probe never initiates contact) ·
[../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md)
