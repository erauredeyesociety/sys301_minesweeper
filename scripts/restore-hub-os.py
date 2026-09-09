#!/usr/bin/env python3
"""restore-hub-os.py — ask whether the Hub OS is alive, and try to bring it back without a power cycle.

    ./scripts/restore-hub-os.py            # check, and if the Hub OS is down attempt a restore
    ./scripts/restore-hub-os.py --check    # check ONLY -- sends nothing that can change hub state

WHY THIS EXISTS
    hub_programmer/run.py, hub_programmer/download.py and everything in probes/ send **Ctrl-C** to get
    a MicroPython `>>>` prompt. Ctrl-C interrupts whatever MicroPython is running — and what it is
    running is the **Hub OS**, the program that serves LEGO's binary control protocol, the CONNECT
    button and the BLE stack. So after any REPL tool, hub_programmer/slot_upload.py can no longer talk
    to the hub and aborts at its identity check:

        [2] identity: DeviceUuidRequest 0x1A
            no DeviceUuidResponse -- cannot prove this is our hub. ABORT (write nothing).

    That abort is the identity guard working correctly and must never be weakened. The cure is to put
    the Hub OS back; the better cure is to not kill it (scripts/scan-surface.py now defaults to the
    slot+console path). Full write-up: docs/findings/hub-os-vs-repl-2026-09-08.md

WHAT COUNTS AS "ALIVE" — and the false positive this replaces
    ⚠ The 2026-09-08 version of this script declared victory when the REPL stopped answering. That is
    NOT evidence: the Hub OS serves a BINARY protocol, and "no `>>>`" only says the REPL went quiet —
    the hub is equally quiet mid-reset. Measured that day: REPL silent in ~1.2 s, slot_upload.py
    immediately afterwards STILL aborted.

    This version asks the only question that matters, over the control protocol itself:
        InfoRequest 0x00        -> InfoResponse 0x01        (Info first: it opens the session)
        DeviceUuidRequest 0x1A  -> DeviceUuidResponse 0x1B  and the 16 bytes must be OUR uuid
    Both are read-only queries. Nothing is written to the hub on this path at all, and the identity
    comparison is imported from slot_upload.py so there is one definition of "our hub", not two.

WHAT IT SENDS, EXACTLY
    check      : two COBS frames — `00 00 02` (InfoRequest) and `07 19 02` (DeviceUuidRequest).
                 LEGO's XOR-COBS framing cannot emit 0x03 or 0x04, so these bytes cannot interrupt or
                 reset anything even if the hub is sitting at a REPL instead.
    restore    : Ctrl-C (0x03) to confirm a REPL is really there, then two **read-only** expressions
                 (`machine.reset_cause()` and `hub.config`) whose answers are the evidence nobody has
                 yet collected, then Ctrl-D (0x04) — MicroPython's **soft reset**, which re-runs
                 /flash/boot.py, and boot.py is the file that contains
                 `hub.config["hub_os_enable"] = True` (read off our own hub, docs/archives/hub-baseline
                 /05-stock-files.txt). The port is then held open for a few seconds to CAPTURE what the
                 REPL says, before being closed, the device node re-waited, and the protocol check
                 above retried until it answers or the deadline expires.

WHY THE CAPTURE MATTERS (added 2026-09-08)
    The previous version wrote Ctrl-D and closed the port in the very next statement, throwing away
    the single most diagnostic artefact in this whole problem. MicroPython prints `MPY: soft reboot`
    when a soft reset actually happens: its PRESENCE proves the reset occurred (so a failure to come
    back is not "the reset never fired"), and a traceback after it names what went wrong instead.
    The transcript is printed and also written to docs/findings/runs/ so it can be filed, not retyped.
    Every read is deadline-bounded — nothing here can block the session (blacklist item 4).

WHY THIS CANNOT TOUCH FIRMWARE
    A soft reset restarts the MicroPython **interpreter**. The firmware is the MicroPython binary in
    the STM32F413's internal program flash and is not written, erased or re-entered by this — the same
    layer distinction proved in docs/findings/firmware-integrity-proof.md. No DFU, no bootloader, no
    filesystem format, no `machine.reset()`, no `machine.bootloader()`, no baud-rate touch, no
    DTR/RTS games. Four control bytes total, and only in the restore path.

STATUS
    [UNVERIFIED -- written 2026-09-08 with no hardware available.] The check and the retry loop have
    never been run against the hub. The verification procedure is in the finding document; run it
    before trusting a green result here.

Exit codes: 0 Hub OS answering · 1 Hub OS down (restore attempted and failed, or --check)
            · 3 no port · 4 port busy · 5 missing pyserial
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "probes"))
sys.path.insert(0, os.path.join(REPO, "hub_programmer"))
import _cobs                                                 # noqa: E402  framing, do NOT reimplement
import _hubio                                                # noqa: E402  find_port()
import slot_upload                                           # noqa: E402  message builders + identity

BAUD = 115200
INTERRUPT = b"\x03"          # Ctrl-C -- confirm a REPL is what is there
SOFT_RESET = b"\x04"         # Ctrl-D -- soft reset: re-runs boot.py
PROMPT = b">>>"

ASK_S = 2.5                  # per-message wait during a protocol check
NODE_WAIT_S = 15.0           # how long to wait for /dev/spike to come back after the reset
SETTLE_S = 2.0               # let the hub finish enumerating before the first question
RESTORE_WAIT_S = 25.0        # total time the Hub OS is given to answer after the reset
CAPTURE_S = 5.0              # how long to keep reading the REPL after Ctrl-D, before closing
PROBE_S = 1.5                # per-expression wait for a read-only diagnostic

# Read-only expressions typed at the prompt we already have, in the one state where they are
# meaningful: the Hub OS is already dead. Each returns a value and changes nothing.
#   reset_cause -- settles whether hub_os_enable is latched at a HARD reset only, in which case no
#                  amount of soft-resetting can ever work.
#   hub.config  -- settles whether hub_os_enable still reads True after a Ctrl-C, which is the
#                  premise the whole "write the flag back" idea rests on.
# NOT here on purpose: any assignment to hub.config (a persistent settings change on shared course
# equipment), machine.reset() and machine.soft_reset() (operator decisions), and importing a frozen
# _system/* module (an import runs its top-level code -- see the runbook, it is a manual step).
DIAGNOSTICS = (
    ("reset_cause", "import machine\r\nprint('RC=', machine.reset_cause())\r\n"),
    ("hub.config", "import hub\r\nprint('CFG=', hub.config)\r\n"),
)


def ask(ser, payload, want_id, deadline=ASK_S):
    """Send one control-protocol message and wait for a reply with that id. Quiet; read-only."""
    ser.write(_cobs.pack(payload))
    buf = bytearray()
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        ser.timeout = min(0.3, max(0.05, end - time.monotonic()))
        data = ser.read(4096)
        if not data:
            continue
        buf.extend(data)
        frames, buf = _cobs.split_frames(buf)
        for frame in frames:
            try:
                msg = _cobs.unpack(frame)
            except Exception:
                continue
            if msg and msg[0] == want_id:
                return msg
    return None


def hub_os_alive(ser):
    """True only when the Hub OS answers the control protocol AND returns OUR device uuid.

    InfoRequest must go first: measured 2026-09-03, the hub does not answer DeviceUuidRequest over
    USB until an InfoRequest has opened the session."""
    ser.reset_input_buffer()
    if ask(ser, slot_upload.m_info_request(), slot_upload.INFO_RESPONSE) is None:
        return False
    msg = ask(ser, slot_upload.m_device_uuid_request(), slot_upload.DEVICE_UUID_RESPONSE)
    return bool(msg) and len(msg) >= 17 and slot_upload.uuid_matches(msg[1:17])


def open_port(serial_mod, port):
    return serial_mod.Serial(port, BAUD, timeout=0.3, write_timeout=5.0)


def drain(ser, seconds):
    """Read whatever the REPL says for `seconds`, then return it. Deadline-bounded, never blocking."""
    out = bytearray()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ser.timeout = min(0.3, max(0.05, end - time.monotonic()))
        data = ser.read(4096)
        if data:
            out.extend(data)
    return bytes(out)


def as_text(raw):
    return raw.decode("utf8", errors="replace").replace("\r\n", "\n").strip()


def save_transcript(lines):
    """File the transcript next to every other run record. Best effort: never fails the restore."""
    try:
        runs = os.path.join(REPO, "docs", "findings", "runs")
        path = os.path.join(runs, "restore-hub-os-%s.txt" % time.strftime("%Y%m%dT%H%M%S"))
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
    except Exception:
        return None


def wait_for_node(deadline_s):
    """After a soft reset the USB CDC endpoint may re-enumerate. Wait for the node, don't assume."""
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        port = _hubio.find_port()
        if port is not None:
            return port
        time.sleep(0.5)
    return None


def main(argv):
    transcript = []                       # filed under docs/findings/runs/ if the restore path runs
    soft_reboot_seen = False
    check_only = "--check" in argv
    if [a for a in argv[1:] if a not in ("--check",)]:
        print("usage: restore-hub-os.py [--check]", file=sys.stderr)
        return 64

    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5

    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 -- hub not enumerated.")
        return 3

    try:
        ser = open_port(serial, port)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        print("  Something holds the port. Check: fuser -v %s" % port)
        return 4

    try:
        # 1. Ask the Hub OS directly, before doing anything that could disturb it. If it is up,
        #    sending Ctrl-C here would be the very bug this script exists to undo.
        if hub_os_alive(ser):
            print("Hub OS ALIVE on %s -- it answered DeviceUuidRequest with our uuid." % port)
            print("nothing to restore.")
            return 0

        print("Hub OS DOWN on %s -- no DeviceUuidResponse over the control protocol." % port)
        if check_only:
            print("  (--check: changing nothing. Re-run without --check to attempt a restore.)")
            return 1

        # 2. Confirm what is actually there. A REPL prompt means a Ctrl-C killed the Hub OS, which is
        #    the case a soft reset might fix. No prompt AND no protocol is a different fault.
        ser.reset_input_buffer()
        ser.write(INTERRUPT)
        time.sleep(0.3)
        ser.write(b"\r\n")
        time.sleep(0.3)
        if PROMPT not in ser.read(4096):
            print("  ...and no '>>>' either. The hub answers neither the protocol nor the REPL.")
            print("  That is not the interrupted-Hub-OS case. POWER-CYCLE: single press the centre")
            print("  button off, then on. Single presses only.")
            return 1

        print("  a '>>>' prompt is there, so a Ctrl-C stopped it.")

        # 2a. READ-ONLY diagnostics, taken at the prompt we already have. These change nothing and
        #     they are the evidence the next decision needs -- see DIAGNOSTICS above.
        transcript.append("# restore-hub-os.py  %s  port=%s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), port))
        for name, expr in DIAGNOSTICS:
            ser.reset_input_buffer()
            ser.write(expr.encode("ascii"))
            answer = as_text(drain(ser, PROBE_S))
            print("  %-12s %s" % (name + ":", answer.replace("\n", " | ") or "(no answer)"))
            transcript.append("--- %s ---\n%s" % (name, answer))

        # 2b. The soft reset -- and this time, LISTEN to it. 'MPY: soft reboot' proves the reset
        #     happened at all; a traceback names why the Hub OS did not come back.
        print("  Sending Ctrl-D (soft reset) and capturing %.0f s of REPL output." % CAPTURE_S)
        ser.write(SOFT_RESET)
        ser.flush()
        try:
            after = as_text(drain(ser, CAPTURE_S))
        except Exception as exc:              # the port may vanish mid-capture; that is itself data
            after = "(port went away during capture: %s)" % exc
        transcript.append("--- after Ctrl-D (%.0f s) ---\n%s" % (CAPTURE_S, after or "(silence)"))
        print("  --- REPL after Ctrl-D " + "-" * 40)
        for line in (after or "(silence -- the REPL said nothing at all)").split("\n"):
            print("  | %s" % line)
        print("  " + "-" * 62)
        soft_reboot_seen = "soft reboot" in after
        print("  'MPY: soft reboot' %s" % ("SEEN -- the soft reset did fire." if soft_reboot_seen
                                           else "NOT seen -- [UNVERIFIED] whether the reset fired."))
    finally:
        try:
            ser.close()                       # release the port: the reset may re-enumerate it
        except Exception:
            pass
        saved = save_transcript(transcript) if len(transcript) > 1 else None
        if saved:
            print("  transcript: %s" % os.path.relpath(saved, REPO))

    if check_only:
        return 1

    # 3. Wait for the port to come back, then ask the Hub OS again -- repeatedly. slot_upload sends
    #    each request exactly once, so one request lost into a still-booting hub looks identical to a
    #    dead Hub OS. Retrying here is what separates "not back yet" from "not coming back".
    port = wait_for_node(NODE_WAIT_S)
    if port is None:
        print("the serial node did not come back within %.0f s. POWER-CYCLE." % NODE_WAIT_S)
        return 1
    time.sleep(SETTLE_S)

    end = time.monotonic() + RESTORE_WAIT_S
    attempt = 0
    while time.monotonic() < end:
        attempt += 1
        try:
            ser = open_port(serial, port)
        except Exception:
            time.sleep(1.0)
            continue
        try:
            if hub_os_alive(ser):
                print("Hub OS RESTORED after %.1f s (%d attempt(s)) -- it returned our uuid over the"
                      % (RESTORE_WAIT_S - (end - time.monotonic()), attempt))
                print("control protocol, which is the same question slot_upload.py asks.")
                return 0
        finally:
            try:
                ser.close()
            except Exception:
                pass
        time.sleep(1.0)

    print("Hub OS did NOT answer within %.0f s of the soft reset." % RESTORE_WAIT_S)
    if soft_reboot_seen:
        print("  The reset DID fire ('MPY: soft reboot' was captured), so this is not a timing")
        print("  artefact: re-running /flash/boot.py does not re-LAUNCH the Hub OS.")
    else:
        print("  No 'MPY: soft reboot' was captured, so it is [UNVERIFIED] whether the reset even")
        print("  fired. Read the transcript above before concluding anything.")
    print("  See docs/findings/stopping-and-restarting-the-hub-2026-09-08.md.")
    print("  Known-good recovery: POWER-CYCLE. Single press the centre button off, then on.")
    print("  Single presses only -- never press-and-hold CONNECT while USB is plugged in.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
