#!/usr/bin/env python3
"""stop-program.py — stop the program running on the hub, from the host, over USB.

    ./scripts/stop-program.py            # stop slot 0, then sweep 0..19 if that is not confirmed
    ./scripts/stop-program.py 3          # stop slot 3 first

WHY THIS EXISTS
    Until now the only way to stop a running robot was a CENTER press on the hub (the firmware's own
    stop) or picking the robot up. While the USB cable is in — which is exactly the bench and dry-run
    case — the host can ask the Hub OS to stop the slot program itself:

        ProgramFlowRequest 0x1E, action 0x01 = Stop, slot N          (LEGO enums.rst: 0x00 Start,
                                                                      0x01 Stop)

    This is the same message hub_programmer/slot_upload.py already sends with action 0x00 to START a
    slot program, and the same call a shipping Hub-OS-3 client makes to terminate a run
    (PeterStaev's VS Code extension: startStopProgram(slot, true)).

WHAT IT PUTS ON THE WIRE, EXACTLY — three XOR-COBS frames, nothing else
        00 00 02        InfoRequest 0x00        (read-only; opens the control session)
        07 19 02        DeviceUuidRequest 0x1A  (read-only; identity)
        5b 1d 00 00 02  ProgramFlowRequest 0x1E action=Stop slot=0   (slot 3 -> 5b 1d 07 00 02)
    No file is written, no slot is cleared, no firmware message id can be built here at all.

⚠ CORRECTED 2026-09-08 — the framing keeps **0x03** off the wire, NOT 0x04
    An earlier version of this header claimed the framing "cannot emit 0x03 or 0x04". Only the first
    half is true. COBS never emits a byte below 0x03 pre-XOR, so `b ^ 3 == 0x03` is unreachable and
    **Ctrl-C is genuinely impossible**. But `0x04` on the wire only needs a pre-XOR `0x07`, which is
    ordinary encoder output — and it OCCURS: the Stop frame for **slot 7** packs to `5b 1d 07 04 02`,
    a literal Ctrl-D byte (COMPUTED on the host with probes/_cobs.py; the Start frame slot_upload.py
    sends for slot 7 has the same property, `07 1d 07 04 02`). Against a live Hub OS that byte is
    inert frame payload, but the claim must not stand as an absolute, so `wire_safe()` below checks
    every frame immediately before it is written and **skips any slot whose frame carries 0x03/0x04**.
    Consequence, stated plainly: **this tool will not stop slot 7** — press CENTER for that one.

IDENTITY IS PROVEN FIRST, exactly as slot_upload.py does it, and for the same reason: a stop sent to
    another team's hub would abort their run. USB is point-to-point, but the check costs two round
    trips and the rule does not get bent for convenience
    (docs/lessons_learned/prove-identity-before-you-act.md).

STATUS: **[UNVERIFIED — never run against our hub.]** The frame layout is primary-sourced
    (LEGO/spike-prime-docs messages.rst id 30 + enums.rst Program action) and cross-checked against a
    third-party Hub OS 3 client, and the host side is checked by import. Whether OUR hub honours a
    Stop while a program is driving is the thing the operator's first run settles. Until then the
    CENTER button remains the stop of record.

Exit: 0 stop acknowledged · 1 not confirmed (press CENTER) · 2 identity mismatch · 3 no port
      · 4 port busy · 5 missing pyserial · 64 usage
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "probes"))
sys.path.insert(0, os.path.join(REPO, "hub_programmer"))
import _cobs                                              # noqa: E402  framing, do NOT reimplement
import _hubio                                             # noqa: E402  find_port()
import slot_upload                                        # noqa: E402  ids + one definition of "our hub"

BAUD = 115200
ASK_S = 2.0                  # per-message wait; every read here has a deadline and exits
CONFIRM_S = 2.0              # how long to wait for the stop to be acknowledged/notified
NUM_SLOTS = slot_upload.NUM_SLOTS
ACTION_STOP = 0x01           # enums.rst "Program action": 0x00 Start, 0x01 Stop


def m_program_flow_stop(slot):
    """1E 01 <slot> — the Start builder in slot_upload.py with the action byte flipped to Stop."""
    return bytes([slot_upload.PROGRAM_FLOW_REQUEST, ACTION_STOP, slot & 0xFF])


def wire_safe(frame):
    """True when a framed message contains neither 0x03 (Ctrl-C) nor 0x04 (Ctrl-D).

    0x03 is unreachable by construction; 0x04 is not (see the header). Checked, not assumed, and
    checked on the FRAME — the bytes that actually reach the port — not on the payload."""
    return 0x03 not in frame and 0x04 not in frame


def read_frames(ser, buf, deadline):
    """Drain the port until `deadline`, returning every decoded message. Never blocks past it."""
    out = []
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        ser.timeout = min(0.3, max(0.05, end - time.monotonic()))
        data = ser.read(4096)
        if not data:
            continue
        buf.extend(data)
        frames, rest = _cobs.split_frames(buf)
        buf[:] = rest
        for frame in frames:
            try:
                out.append(_cobs.unpack(frame))
            except Exception:
                pass
        if out:
            return out
    return out


def ask(ser, buf, payload, want_id, deadline=ASK_S):
    """Send one message, return the first reply with that id (or None). Read-only helper."""
    frame = _cobs.pack(payload)
    if not wire_safe(frame):                       # cannot happen for 00/1A; checked anyway
        print("  REFUSED to write %s -- it carries a control byte." % frame.hex(" "))
        return None
    ser.write(frame)
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        for msg in read_frames(ser, buf, end - time.monotonic()):
            if msg and msg[0] == want_id:
                return msg
    return None


def stop_slot(ser, buf, slot):
    """Send Stop for one slot. Returns True only on an Acknowledged response or a Stop notification."""
    payload = m_program_flow_stop(slot)
    frame = _cobs.pack(payload)
    print("  slot %-2d  ->  %s   (frame %s)" % (slot, payload.hex(" "), frame.hex(" ")))
    if not wire_safe(frame):
        print("     SKIPPED: this frame carries a control byte (0x03/0x04) and is not written.")
        print("     Press the hub's CENTER button to stop slot %d." % slot)
        return False
    ser.write(frame)
    end = time.monotonic() + CONFIRM_S
    acked = False
    while time.monotonic() < end:
        for msg in read_frames(ser, buf, end - time.monotonic()):
            if not msg:
                continue
            if msg[0] == slot_upload.PROGRAM_FLOW_RESPONSE and len(msg) >= 2:
                acked = msg[1] == slot_upload.ACK
                print("     ProgramFlowResponse 0x1F: %s"
                      % ("Acknowledged" if acked else "NotAcknowledged"))
            elif msg[0] == slot_upload.PROGRAM_FLOW_NOTIFICATION and len(msg) >= 2:
                print("     ProgramFlowNotification 0x20: program %s"
                      % ("STOPPED" if msg[1] else "STARTED"))
                if msg[1]:
                    return True
            elif msg[0] == slot_upload.CONSOLE_NOTIFICATION:
                text = msg[1:].rstrip(b"\x00").decode("utf8", errors="replace").rstrip("\n")
                if text:
                    print("     [console] %s" % text)
        if acked:
            return True
    return acked


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if len(args) > 1 or [a for a in argv[1:] if a.startswith("-")]:
        print("usage: stop-program.py [slot]", file=sys.stderr)
        return 64
    slot = int(args[0]) if args else 0
    if not 0 <= slot < NUM_SLOTS:
        print("slot out of range 0..%d" % (NUM_SLOTS - 1), file=sys.stderr)
        return 64

    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5
    port = _hubio.find_port()
    if port is None:
        print("NO PORT: no /dev/spike -- the hub is not plugged in. Press the hub's CENTER button.")
        return 3
    try:
        ser = serial.Serial(port, BAUD, timeout=0.3, write_timeout=5.0)
    except Exception as exc:
        print("PORT BUSY: %s: %s" % (port, exc))
        print("  Another tool holds the port (a --listen session?). Close it, or press CENTER.")
        return 4

    buf = bytearray()
    try:
        ser.reset_input_buffer()
        # InfoRequest FIRST: measured 2026-09-03, the hub does not answer identity until the session
        # is open. Both this and the uuid request are read-only.
        if ask(ser, buf, slot_upload.m_info_request(), slot_upload.INFO_RESPONSE) is None:
            print("SILENT: no InfoResponse. Either the Hub OS is stopped (a REPL tool killed it) or")
            print("  nothing is running. Nothing was sent past the two read-only queries.")
            print("  PRESS THE HUB'S CENTER BUTTON to stop the robot.")
            return 1
        msg = ask(ser, buf, slot_upload.m_device_uuid_request(), slot_upload.DEVICE_UUID_RESPONSE)
        if not msg or len(msg) < 17 or not slot_upload.uuid_matches(msg[1:17]):
            print("NOT OUR HUB (or no identity reply). ABORT -- sending no stop.")
            return 2
        print("identity proven: our hub. Sending ProgramFlowRequest action=Stop.")

        if stop_slot(ser, buf, slot):
            print("\nSTOPPED: slot %d acknowledged the stop." % slot)
            return 0
        print("\n  slot %d not confirmed -- sweeping every slot (a Stop for an idle slot is a no-op)."
              % slot)
        for other in range(NUM_SLOTS):
            if other == slot:
                continue
            if stop_slot(ser, buf, other):
                print("\nSTOPPED: slot %d acknowledged the stop." % other)
                return 0
        print("\nNOT CONFIRMED. The hub did not acknowledge any stop.")
        print("  PRESS THE HUB'S CENTER BUTTON -- that is the stop of record.")
        return 1
    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main(sys.argv))
