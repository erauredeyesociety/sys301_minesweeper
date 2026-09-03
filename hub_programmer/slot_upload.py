#!/usr/bin/env python3
"""slot_upload.py -- upload a .py to a Hub OS program SLOT, start it, read its output.

This is the SECOND write path to the hub. The first, ADR-0007
(hub_programmer/upload.py), writes a MODULE into /flash/lib over the REPL and is
PROVEN on our hardware. This one drives LEGO's binary control protocol to store a
program in a numbered SLOT and RUN it -- the capability /flash/main.py does not
give us, because it does not autorun (measured after a real power cycle).

    ./hub_programmer/slot_upload.py prog.py                 # DRY RUN over USB, writes nothing
    ./hub_programmer/slot_upload.py prog.py --apply         # actually upload to slot 0 and start it
    ./hub_programmer/slot_upload.py prog.py --slot 3 --apply
    ./hub_programmer/slot_upload.py prog.py --ble --apply   # over Bluetooth (untethered path)
    ./hub_programmer/slot_upload.py prog.py --apply --listen 20   # watch console 20 s after start

STATUS: **UNTESTED on our hub.** The message layouts come from LEGO/spike-prime-docs
(a primary source) and are cross-checked on the host, but the whole sequence has
never been run against our hardware. Everything the hub would tell us is
[UNVERIFIED]. See docs/research/program-upload-protocol.md.

WHY THIS IS SAFE
  * Stock firmware is never touched. This path writes a FILE into a program slot
    (a filesystem write), exactly like ADR-0007 writes into /flash/lib. It is NOT
    a firmware flash. As an extra guard, send() REFUSES the firmware message ids
    (0x0A/0x0B StartFirmwareUpload, 0x14/0x15 BeginFirmwareUpdate); this client
    physically cannot emit them.
  * DRY RUN by default. Without --apply it opens no port and no radio; it only
    computes and prints every frame it WOULD put on the wire.
  * Identity is proven before anything is written. Over BLE we filter on our
    address AND then read the 16-byte device UUID and compare it; over USB we read
    and compare the UUID too. A mismatch aborts before a single upload byte.
    (docs/lessons_learned/prove-identity-before-you-act.md)
  * Every wait has a deadline. Nothing here can block the session.
  * Raw bytes of every frame are printed both directions, because the layouts are
    [UNVERIFIED] and the raw bytes are the result worth keeping even if a decode
    is wrong.

USB vs the REPL tools -- IMPORTANT
  The probes/ and hub_programmer/upload.py tools send Ctrl-C to get a '>>>' REPL.
  This client does the OPPOSITE: it never sends Ctrl-C. The binary control
  protocol is driven by the Hub OS, and Ctrl-C would kill the Hub OS. Measured
  2026-08-27: DeviceUuidRequest answered over /dev/spike at 115200 WITHOUT any
  Ctrl-C. Develop over USB (point-to-point, cannot hit another team's hub); use
  --ble only for the untethered robot.

Exit codes: 0 ok/dry-run · 1 upload or start failed · 2 identity mismatch (aborted)
            · 3 no port / hub not found · 4 port busy · 5 missing pyserial/bleak · 64 usage
"""

import os
import struct
import sys
import time
from binascii import crc32 as _crc32

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes"))
import _cobs                                                   # noqa: E402  framing, do NOT reimplement
import _hubio                                                  # noqa: E402  find_port()

# --- our hub's identity (measured 2026-08-27, USB and BLE) ------------------
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"
OUR_UUID_BYTES = bytes.fromhex(OUR_DEVICE_UUID.replace("-", ""))
OUR_BLE_ADDRESS = "64:8C:BB:0A:1C:8C"

# --- BLE transport (discovered by examples/ble_connect.py) ------------------
TX_CHAR = "0000fd02-0001-1000-8000-00805f9b34fb"     # host -> hub, write-without-response
RX_CHAR = "0000fd02-0002-1000-8000-00805f9b34fb"     # hub  -> host, notify

BAUD = 115200

# --- message ids (all confirmed against LEGO/spike-prime-docs) --------------
INFO_REQUEST = 0x00
INFO_RESPONSE = 0x01
DEVICE_UUID_REQUEST = 0x1A
DEVICE_UUID_RESPONSE = 0x1B
CLEAR_SLOT_REQUEST = 0x46
CLEAR_SLOT_RESPONSE = 0x47
START_FILE_UPLOAD_REQUEST = 0x0C
START_FILE_UPLOAD_RESPONSE = 0x0D
TRANSFER_CHUNK_REQUEST = 0x10
TRANSFER_CHUNK_RESPONSE = 0x11
PROGRAM_FLOW_REQUEST = 0x1E
PROGRAM_FLOW_RESPONSE = 0x1F
PROGRAM_FLOW_NOTIFICATION = 0x20
CONSOLE_NOTIFICATION = 0x21

ACK = 0x00                       # Response Status: 0x00 Acknowledged, 0x01 NotAcknowledged
ACTION_START = 0x00              # Program Action: 0x00 Start, 0x01 Stop
NUM_SLOTS = 20                   # slots 0..19 (glossary.rst)

# The one thing this client must never send: a firmware upload/flash. Kept as an
# allowlist-by-exclusion so the refusal is in code, not just in prose.
FIRMWARE_IDS = frozenset({0x0A, 0x0B, 0x14, 0x15})

DEFAULT_CHUNK = 4096             # max_chunk_size when an InfoResponse reports it
# Our hub answers InfoRequest but NOT with a parseable InfoResponse over USB (measured 2026-09-03), so
# a >4096-byte program fell back to a 4096-byte TransferChunk that the hub does NOT ACK. 512 is small
# enough that the hub accepts it and is a multiple of 4, so the running CRC still chains to the
# whole-file CRC -- multi-chunk uploads (any program over one chunk) then just work. Override: --chunk.
SAFE_CHUNK = 512


# --- checksum: standard reflected CRC-32 (binascii.crc32), LEGO's crc.py ----
# LEGO RULE (glossary.rst): the CRC is always computed over a multiple of 4
# bytes; pad with 0x00 up to a multiple of 4 first. This is why a chunk size that
# is NOT a multiple of 4 makes the running CRC diverge from the whole-file CRC --
# 4096 is a multiple of 4, so it holds for every non-final chunk.
def crc(data, seed=0, align=4):
    r = len(data) % align
    if r:
        data = data + b"\x00" * (align - r)
    return _crc32(data, seed) & 0xFFFFFFFF


# --- message builders (little-endian; see program-upload-protocol.md) -------
def m_info_request():
    return bytes([INFO_REQUEST])


def m_device_uuid_request():
    return bytes([DEVICE_UUID_REQUEST])


def m_clear_slot(slot):
    return struct.pack("<BB", CLEAR_SLOT_REQUEST, slot)


def m_start_file_upload(name, slot, file_crc):
    enc = name.encode("utf8")
    if len(enc) > 31:
        raise ValueError("program name > 31 bytes (32 incl. NUL)")
    # variable-width name + exactly one NUL, then slot, then whole-file CRC32.
    return struct.pack("<B%dsBI" % (len(enc) + 1), START_FILE_UPLOAD_REQUEST, enc, slot, file_crc)


def m_transfer_chunk(running_crc, chunk):
    return struct.pack("<BIH%ds" % len(chunk), TRANSFER_CHUNK_REQUEST, running_crc, len(chunk), chunk)


def m_program_flow_start(slot):
    return struct.pack("<BBB", PROGRAM_FLOW_REQUEST, ACTION_START, slot)


def is_ack(msg):
    return len(msg) >= 2 and msg[1] == ACK


def uuid_matches(uuid16):
    """True if a 16-byte UUID is ours, testing both byte orders (order [UNVERIFIED])."""
    return uuid16 == OUR_UUID_BYTES or uuid16 == OUR_UUID_BYTES[::-1]


# --- printing: raw bytes both ways ------------------------------------------
def show_out(payload, frame):
    print("  >> id 0x%02X  payload %s" % (payload[0], payload.hex(" ")))
    print("     frame %2d B: %s" % (len(frame), frame.hex(" ")))


def show_in(frame, msg):
    print("  << frame %2d B: %s" % (len(frame), frame.hex(" ")))
    if msg:
        print("     decode id 0x%02X: %s" % (msg[0], msg.hex(" ")))
    else:
        print("     decode: (empty)")


def note_notification(msg):
    """Print an unsolicited console / program-flow message inline."""
    if not msg:
        return
    if msg[0] == CONSOLE_NOTIFICATION:
        text = msg[1:].rstrip(b"\x00").decode("utf8", errors="replace")
        print("     [console] %s" % text.rstrip("\n"))
    elif msg[0] == PROGRAM_FLOW_NOTIFICATION and len(msg) >= 2:
        print("     [program %s]" % ("STOPPED" if msg[1] else "STARTED"))


# --- transports: both expose send(payload) and recv(deadline)->frame|None ---
class UsbTransport(object):
    """Binary control protocol over /dev/spike. No Ctrl-C -- ever (see header)."""

    def __init__(self, serial_mod, port):
        self.ser = serial_mod.Serial(port, BAUD, timeout=0.3, write_timeout=5.0)
        self._buf = bytearray()
        self._frames = []
        # Do NOT send Ctrl-C or \r\n. Just clear stale bytes and speak frames.
        self.ser.reset_input_buffer()

    def send(self, payload):
        if payload[0] in FIRMWARE_IDS:
            raise RuntimeError("REFUSED: firmware message id 0x%02X" % payload[0])
        frame = _cobs.pack(payload)
        show_out(payload, frame)
        self.ser.write(frame)

    def recv(self, deadline):
        end = time.monotonic() + deadline
        while True:
            if self._frames:
                return self._frames.pop(0)
            remaining = end - time.monotonic()
            if remaining <= 0:
                return None
            self.ser.timeout = min(0.3, remaining)
            data = self.ser.read(4096)
            if data:
                self._buf.extend(data)
                frames, self._buf = _cobs.split_frames(self._buf)
                self._frames.extend(frames)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class BleTransport(object):
    """Binary control protocol over BLE. bleak runs on a background asyncio loop
    so the upload sequence stays one synchronous body shared with USB."""

    def __init__(self, address, wait_s):
        import asyncio
        import queue
        import threading
        self._asyncio = asyncio
        self._q = queue.Queue()
        self._loop = asyncio.new_event_loop()
        self._client = None
        self._buf = bytearray()
        self._packet_size = 20              # conservative until MTU is known
        self._ready = threading.Event()
        self._err = None
        self._addr = address
        self._wait_s = wait_s
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _submit(self, coro, timeout):
        fut = self._asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def open(self):
        """Scan for OUR address, connect, subscribe, read the MTU. Read-only so far."""
        from bleak import BleakScanner, BleakClient

        async def _open():
            print("scanning for %s (up to %.0f s) -- press CONNECT on the hub" % (self._addr, self._wait_s))
            dev = await BleakScanner.find_device_by_address(self._addr, timeout=self._wait_s)
            if dev is None:
                raise RuntimeError("hub %s did not advertise in the window" % self._addr)
            client = BleakClient(dev, timeout=20.0)
            await client.connect()
            self._client = client
            # MTU: BlueZ negotiates it at connect; bleak reports 23 until we read it.
            try:
                if hasattr(client, "_backend") and hasattr(client._backend, "_acquire_mtu"):
                    await client._backend._acquire_mtu()
            except Exception as exc:
                print("  (could not force MTU read: %s)" % type(exc).__name__)
            mtu = getattr(client, "mtu_size", None)
            usable = None
            try:
                ch = client.services.get_characteristic(TX_CHAR)
                usable = getattr(ch, "max_write_without_response_size", None)
            except Exception:
                pass
            hub_cap = getattr(self, "_hub_max_packet", None)
            eff = usable or (mtu - 3 if mtu else 20) or 20
            self._packet_size = eff if not hub_cap else min(eff, hub_cap)
            print("  connected. MTU %s, usable write %s -> packet_size %d"
                  % (mtu, usable, self._packet_size))

            def on_notify(_h, data):
                self._buf.extend(data)
                frames, self._buf = _cobs.split_frames(self._buf)
                for f in frames:
                    self._q.put(f)

            await client.start_notify(RX_CHAR, on_notify)

        self._submit(_open(), timeout=self._wait_s + 30)

    def send(self, payload):
        if payload[0] in FIRMWARE_IDS:
            raise RuntimeError("REFUSED: firmware message id 0x%02X" % payload[0])
        frame = _cobs.pack(payload)
        show_out(payload, frame)

        async def _write():
            for i in range(0, len(frame), self._packet_size):
                await self._client.write_gatt_char(TX_CHAR, frame[i:i + self._packet_size], response=False)

        self._submit(_write(), timeout=10)

    def recv(self, deadline):
        import queue
        try:
            return self._q.get(timeout=max(0.0, deadline))
        except queue.Empty:
            return None

    def close(self):
        try:
            if self._client is not None:
                self._submit(self._client.disconnect(), timeout=10)
        except Exception:
            pass
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


# --- request/response over any transport ------------------------------------
def request(tx, payload, want_id, deadline):
    """Send one message, return the first reply whose id == want_id (or None).
    Prints every frame both ways; forwards unsolicited notifications to the log."""
    tx.send(payload)
    end = time.monotonic() + deadline
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return None
        frame = tx.recv(remaining)
        if frame is None:
            return None
        try:
            msg = _cobs.unpack(frame)
        except Exception as exc:
            print("  << frame %d B: %s" % (len(frame), frame.hex(" ")))
            print("     decode FAILED: %s (raw bytes above are the result)" % type(exc).__name__)
            continue
        show_in(frame, msg)
        if msg and msg[0] == want_id:
            return msg
        note_notification(msg)


# --- the upload+start sequence, run once against either transport -----------
def run_sequence(tx, name, slot, data, listen_s, chunk_override=None):
    # 1. InfoRequest FIRST -- it OPENS the control session. MEASURED 2026-09-03:
    #    the hub does NOT answer DeviceUuidRequest over USB until an InfoRequest has
    #    been sent (usb_protocol.py sends Info first and gets a clean identity reply;
    #    sending identity first gets silence). Both are read-only queries, so this
    #    changes nothing about the safety guarantee: no WRITE happens until identity
    #    is proven in step 2 below.
    print("\n[1] InfoRequest 0x00 (opens session, learn sizes)")
    info = request(tx, m_info_request(), INFO_RESPONSE, deadline=6.0)
    chunk_size = DEFAULT_CHUNK
    if info:
        fields = _cobs.parse_info_response(info)
        if fields:
            print("    %s" % fields)
            chunk_size = fields.get("max_chunk_size", DEFAULT_CHUNK) or DEFAULT_CHUNK
            hub_pkt = fields.get("max_packet_size")
            if hub_pkt and hasattr(tx, "_packet_size"):
                tx._packet_size = min(tx._packet_size, hub_pkt)
                print("    BLE packet_size capped to %d" % tx._packet_size)
    else:
        chunk_size = SAFE_CHUNK
        print("    no InfoResponse; using safe multi-chunk size %d" % chunk_size)
    if chunk_override:
        chunk_size = chunk_override
        print("    chunk size overridden to %d (--chunk)" % chunk_size)

    # 2. PROVE IDENTITY before writing anything (still before the first WRITE below).
    print("\n[2] identity: DeviceUuidRequest 0x1A")
    msg = request(tx, m_device_uuid_request(), DEVICE_UUID_RESPONSE, deadline=6.0)
    if not msg or len(msg) < 17:
        print("    no DeviceUuidResponse -- cannot prove this is our hub. ABORT (write nothing).")
        return 2
    got = msg[1:17]
    print("    hub uuid bytes: %s" % got.hex())
    if not uuid_matches(got):
        print("    UUID DOES NOT MATCH OUR HUB (%s). ABORT -- writing nothing." % OUR_DEVICE_UUID)
        return 2
    print("    *** identity proven: this is our hub ***")

    # 3. ClearSlotRequest (NACK tolerated -- means the slot was already empty).
    print("\n[3] ClearSlotRequest 0x46 slot %d" % slot)
    cs = request(tx, m_clear_slot(slot), CLEAR_SLOT_RESPONSE, deadline=6.0)
    if cs is None:
        print("    no ClearSlotResponse -- ABORT")
        return 1
    print("    %s" % ("Acknowledged" if is_ack(cs) else "NotAcknowledged (tolerated: slot was empty)"))

    # 4. StartFileUploadRequest with the WHOLE-file CRC.
    file_crc = crc(data)
    print("\n[4] StartFileUploadRequest 0x0C  name=%r slot=%d crc=0x%08X" % (name, slot, file_crc))
    su = request(tx, m_start_file_upload(name, slot, file_crc), START_FILE_UPLOAD_RESPONSE, deadline=8.0)
    if not su or not is_ack(su):
        print("    StartFileUpload not Acknowledged -- ABORT")
        return 1
    print("    Acknowledged")

    # 5. TransferChunkRequest * N, each carrying the RUNNING CRC.
    nchunks = max(1, (len(data) + chunk_size - 1) // chunk_size)
    print("\n[5] TransferChunk 0x10  %d byte(s) in %d chunk(s) of <=%d" % (len(data), nchunks, chunk_size))
    running = 0
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        running = crc(chunk, running)
        tc = request(tx, m_transfer_chunk(running, chunk), TRANSFER_CHUNK_RESPONSE, deadline=8.0)
        if not tc or not is_ack(tc):
            print("    chunk at offset %d not Acknowledged -- ABORT" % i)
            return 1
    print("    all chunks Acknowledged (final running crc 0x%08X)" % running)
    if running != file_crc:
        # 4096 is a multiple of 4, so this should always hold; if not, the transfer is suspect.
        print("    WARNING: running crc != whole-file crc (0x%08X). Do not trust this upload." % file_crc)

    # 6. ProgramFlowRequest(Start) -> launch the stored slot program.
    print("\n[6] ProgramFlowRequest 0x1E action=Start slot %d" % slot)
    pf = request(tx, m_program_flow_start(slot), PROGRAM_FLOW_RESPONSE, deadline=6.0)
    if not pf or not is_ack(pf):
        print("    ProgramFlow(Start) not Acknowledged -- upload stored but not running")
        return 1
    print("    Acknowledged -- program started")

    # 7. Read ConsoleNotification output as text, until program stop or deadline.
    print("\n[7] listening %.0f s for console output (0x21) / program stop (0x20)" % listen_s)
    end = time.monotonic() + listen_s
    while time.monotonic() < end:
        frame = tx.recv(end - time.monotonic())
        if frame is None:
            break
        try:
            msg = _cobs.unpack(frame)
        except Exception:
            print("  << raw %s (decode failed)" % frame.hex(" "))
            continue
        note_notification(msg)
        if msg and msg[0] == PROGRAM_FLOW_NOTIFICATION and len(msg) >= 2 and msg[1]:
            print("    program reported STOP -- done listening")
            break
    print("\ndone.")
    return 0


# --- dry run: compute and print every frame, touch no hardware --------------
def dry_run(name, slot, data, chunk_size):
    print("DRY RUN -- no port opened, no radio, nothing written. Frames it WOULD send:\n")

    def show(label, payload):
        frame = _cobs.pack(payload)
        print("  %s" % label)
        print("    id 0x%02X payload %s" % (payload[0], payload.hex(" ")))
        print("    frame %d B: %s" % (len(frame), frame.hex(" ")))

    show("identity  DeviceUuidRequest 0x1A", m_device_uuid_request())
    show("sizes     InfoRequest 0x00", m_info_request())
    show("clear     ClearSlotRequest 0x46 slot %d" % slot, m_clear_slot(slot))
    file_crc = crc(data)
    show("start     StartFileUploadRequest 0x0C name=%r slot=%d crc=0x%08X" % (name, slot, file_crc),
         m_start_file_upload(name, slot, file_crc))
    nchunks = max(1, (len(data) + chunk_size - 1) // chunk_size)
    running = 0
    for n, i in enumerate(range(0, len(data), chunk_size)):
        chunk = data[i:i + chunk_size]
        running = crc(chunk, running)
        payload = m_transfer_chunk(running, chunk)
        # A chunk frame can be large; show the header, not the whole body.
        head = payload[:7]
        print("  chunk %d/%d  TransferChunkRequest 0x10  size=%d running_crc=0x%08X"
              % (n + 1, nchunks, len(chunk), running))
        print("    header  : %s ... (+%d payload bytes)" % (head.hex(" "), len(chunk)))
    show("start-prog ProgramFlowRequest 0x1E action=Start slot %d" % slot, m_program_flow_start(slot))
    print("\n  whole-file crc 0x%08X  final running crc 0x%08X  %s"
          % (file_crc, running, "MATCH" if running == file_crc else "MISMATCH (chunk size not /4?)"))
    print("\nRe-run with --apply to actually do this against the hub.")
    return 0


def minify_source(text):
    """Strip comments + docstrings so the bytes uploaded to program.py are minimal -- the SOURCE file
    stays fully commented. Uses python_minifier when installed; otherwise returns text unchanged and
    lets multi-chunk carry the size. Never renames: names stay readable in a hub traceback."""
    try:
        import python_minifier
    except ImportError:
        return text, False
    try:
        out = python_minifier.minify(text, remove_literal_statements=True,
                                     rename_locals=False, rename_globals=False, hoist_literals=False)
        return out, True
    except Exception as exc:
        print("    minify skipped (%s) -- uploading full source" % type(exc).__name__)
        return text, False


def usage():
    print(__doc__.split("STATUS:")[0].strip())
    return 64


def main(argv):
    apply_it = "--apply" in argv
    use_ble = "--ble" in argv

    def opt(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default

    slot = int(opt("--slot", "0"))
    listen_s = float(opt("--listen", "10"))
    address = opt("--address", OUR_BLE_ADDRESS)
    wait_s = float(opt("--wait", "90"))
    name_override = opt("--name", None)
    chunk_arg = opt("--chunk", None)
    chunk_override = int(chunk_arg) if chunk_arg else None
    do_minify = "--no-minify" not in argv

    files = [a for a in argv[1:] if not a.startswith("--")
             and argv[argv.index(a) - 1] not in
             ("--slot", "--listen", "--address", "--wait", "--name", "--chunk")]
    if not files:
        return usage()
    local = files[0]
    if not os.path.exists(local):
        print("no such local file: %s" % local)
        return 64
    if not 0 <= slot < NUM_SLOTS:
        print("slot out of range 0..%d" % (NUM_SLOTS - 1))
        return 64

    with open(local, "rb") as fh:
        raw = fh.read()
    data = raw
    if do_minify:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None:
            out, did = minify_source(text)
            if did:
                data = out.encode("utf-8")
                print("minify  : %d -> %d bytes (comments/docstrings stripped; source untouched)"
                      % (len(raw), len(data)))
    # The slot's runnable entry point is the FIXED name "program.py" (raw source) -- ProgramFlow
    # selects by slot NUMBER, so uploading under the source basename ACKs but leaves the slot with
    # nothing to run (measured 2026-09-03: "program started" but no execution). LEGO's own app.py and
    # community uploaders both use "program.py". --name still overrides. See
    # docs/research/slot-execution-and-live-motor-control-2026-09-03.md
    name = name_override or "program.py"

    print("local   : %s  (%d bytes)" % (local, len(data)))
    print("target  : slot %d  name %r" % (slot, name))
    print("transport: %s" % ("BLE %s" % address if use_ble else "USB /dev/spike"))
    print("checksum: whole-file crc32 0x%08X\n" % crc(data))

    if not apply_it:
        return dry_run(name, slot, data, chunk_override or SAFE_CHUNK)

    # --apply: open the transport, prove identity, run the sequence.
    if use_ble:
        try:
            import bleak                                       # noqa: F401
        except ImportError:
            print("NO_BLEAK: python3 -m pip install --user bleak")
            return 5
        tx = None
        try:
            tx = BleTransport(address, wait_s)
            tx.open()
            return run_sequence(tx, name, slot, data, listen_s, chunk_override)
        except Exception as exc:
            print("BLE ERROR: %s: %s" % (type(exc).__name__, exc))
            return 3
        finally:
            if tx is not None:
                tx.close()
    else:
        try:
            import serial
        except ImportError:
            print("NO_PYSERIAL: python3 -m pip install pyserial")
            return 5
        port = _hubio.find_port()
        if port is None:
            print("UNKNOWN: no /dev/spike or /dev/ttyACM0 -- hub not enumerated.")
            return 3
        tx = None
        try:
            tx = UsbTransport(serial, port)
        except Exception as exc:
            print("BUSY_OR_DENIED: %s: %s" % (port, exc))
            return 4
        try:
            return run_sequence(tx, name, slot, data, listen_s, chunk_override)
        finally:
            tx.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
