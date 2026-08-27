# examples/ble_info_request.py — ask the hub who it is, over Bluetooth.
#
# RUNS ON THE LAPTOP (bleak). Never opens the serial port.
#
#   python3 examples/ble_info_request.py --wait 60
#
# THE QUESTION IT ANSWERS
# A BLE scan finds a hub called "Team 21". That name is user-settable and is no
# evidence the hub is ours. The advertisement does NOT carry device_uuid --
# device_uuid is 03970000 + the STM32F413 die ID, while the BLE address comes
# from a separate TI radio chip, so there is no derivation between them.
# The only way to prove identity is to CONNECT and ask.
#
# WHAT IT SENDS
# One InfoRequest (message id 0x00), which is a read-only query. Nothing is
# written to the hub, no program is uploaded, no setting changed.
#
# [UNVERIFIED] The COBS framing below is implemented from LEGO's published
# algorithm, not copied from a working client. The encoder was checked by hand
# against one known value -- InfoRequest frames to 00 00 02 -- but the DECODER
# has never been run against a real response. So this prints the RAW bytes of
# every notification before attempting to decode, and the raw bytes are the
# result worth keeping even if the decode is wrong.
#
# Transport discovered by examples/ble_connect.py on 2026-08-27:
#   service 0000fd02-0000-1000-8000-00805f9b34fb
#     0000fd02-0001-...  write-without-response   host -> hub
#     0000fd02-0002-...  notify                   hub  -> host

import asyncio
import sys

RX_CHAR = "0000fd02-0002-1000-8000-00805f9b34fb"     # hub -> host, notify
TX_CHAR = "0000fd02-0001-1000-8000-00805f9b34fb"     # host -> hub, write
LEGO_COMPANY_ID = 0x0397
LEGO_SERVICE_16 = "fd02"

OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"

# --- LEGO's COBS variant ----------------------------------------------------
# Ordinary COBS uses 0x00 as the frame delimiter. LEGO uses 0x02, then XORs the
# whole frame by 3 so that 0x00 and 0x03 cannot appear in it -- 0x03 is Ctrl-C,
# which would be catastrophic on a shared serial transport.
DELIMITER = 0x02
NO_DELIMITER = 0xFF
COBS_CODE_OFFSET = DELIMITER
MAX_BLOCK_SIZE = 84
XOR = 3


def cobs_encode(data):
    buffer = bytearray()
    state = {"code_index": 0, "block": 0}

    def begin_block():
        state["code_index"] = len(buffer)
        buffer.append(NO_DELIMITER)
        state["block"] = 1

    begin_block()
    for byte in data:
        if byte > DELIMITER:
            buffer.append(byte)
            state["block"] += 1
        if byte <= DELIMITER or state["block"] > MAX_BLOCK_SIZE:
            if byte <= DELIMITER:
                buffer[state["code_index"]] = (byte * MAX_BLOCK_SIZE
                                               + state["block"] + COBS_CODE_OFFSET)
            begin_block()
    buffer[state["code_index"]] = state["block"] + COBS_CODE_OFFSET
    return bytes(buffer)


def cobs_decode(data):
    buffer = bytearray()

    def unescape(code):
        if code == NO_DELIMITER:
            return None, MAX_BLOCK_SIZE + 1
        value, block = divmod(code - COBS_CODE_OFFSET, MAX_BLOCK_SIZE)
        if block == 0:
            block = MAX_BLOCK_SIZE
            value -= 1
        return value, block

    if not data:
        return b""
    value, block = unescape(data[0])
    for byte in data[1:]:
        block -= 1
        if block > 0:
            buffer.append(byte)
            continue
        if value is not None:
            buffer.append(value)
        value, block = unescape(byte)
    return bytes(buffer)


def pack(payload):
    """Message bytes -> a frame ready to write to the TX characteristic."""
    frame = cobs_encode(payload)
    return bytes(b ^ XOR for b in frame) + bytes([DELIMITER])


def unpack(frame):
    """A received frame (delimiter already stripped) -> message bytes."""
    return cobs_decode(bytes(b ^ XOR for b in frame))


def is_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    for u in (adv.service_uuids or []):
        if LEGO_SERVICE_16 in u.lower():
            return True
    return "spike" in (name or "").lower()


async def find(seconds):
    from bleak import BleakScanner
    found = asyncio.Event()
    box = {}

    def on_detect(dev, adv):
        if not box and is_lego(adv.local_name or dev.name or "", adv):
            box["dev"] = dev
            box["name"] = adv.local_name or dev.name or ""
            found.set()

    print("waiting up to %.0f s. PRESS THE CONNECT BUTTON ON THE HUB." % seconds)
    scanner = BleakScanner(detection_callback=on_detect)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass
    finally:
        await scanner.stop()
    if not box:
        print("\nNo LEGO hub advertised. The window after a CONNECT press is short;")
        print("press it again and re-run.")
        return None, None
    print("FOUND %s %r" % (box["dev"].address, box["name"]))
    return box["dev"], box["name"]


def parse_info_response(msg):
    """LEGO's InfoResponse is 17 bytes with a documented layout. Parsing it is
    also how we CHECK the framing: if every field lands on a sensible value,
    the COBS decode was right. Nonsense here means the decoder is wrong."""
    if len(msg) < 17 or msg[0] != 0x01:
        return None
    def u16(i):
        return msg[i] | (msg[i + 1] << 8)
    return [
        ("rpc version", "%d.%d.%d" % (msg[1], msg[2], u16(3))),
        ("firmware version", "%d.%d.%d" % (msg[5], msg[6], u16(7))),
        ("max_packet_size", u16(9)),
        ("max_message_size", u16(11)),
        ("max_chunk_size", u16(13)),
        ("product_group_device", u16(15)),
    ]


async def amain(argv):
    wait_s = 60.0
    if "--wait" in argv:
        wait_s = float(argv[argv.index("--wait") + 1])

    # Sanity-check the encoder against the one frame we can verify by hand.
    probe = pack(b"\x00")
    print("InfoRequest frames to: %s" % probe.hex(" "))
    if probe != b"\x00\x00\x02":
        print("  WARNING: expected 00 00 02. The encoder is wrong; not sending.")
        return 2
    print("  matches the expected 00 00 02\n")

    from bleak import BleakClient

    device, _name = await find(wait_s)
    if device is None:
        return 1

    frames = []
    buf = bytearray()

    def on_notify(_handle, data):
        print("  RAW notification %3d bytes: %s" % (len(data), data.hex(" ")))
        buf.extend(data)
        while DELIMITER in buf:
            idx = buf.index(DELIMITER)
            frame = bytes(buf[:idx])
            del buf[:idx + 1]
            if frame:
                frames.append(frame)

    async with BleakClient(device, timeout=20.0) as client:
        print("connected: %s" % client.is_connected)
        await client.start_notify(RX_CHAR, on_notify)
        for label, msg_id in (("InfoRequest", 0x00), ("DeviceUuidRequest", 0x1A)):
            frame = pack(bytes([msg_id]))
            print("\nsending %s (id 0x%02X) as %s" % (label, msg_id, frame.hex(" ")))
            await client.write_gatt_char(TX_CHAR, frame, response=False)
            await asyncio.sleep(4.0)
        await client.stop_notify(RX_CHAR)

    print("\n--- %d complete frame(s) ---" % len(frames))
    for f in frames:
        print("\nframe raw   : %s" % f.hex(" "))
        try:
            msg = unpack(f)
        except Exception as exc:
            print("decode FAILED: %s -- the raw bytes above are still the result"
                  % type(exc).__name__)
            continue
        print("decoded     : %s" % msg.hex(" "))
        if msg:
            print("message id  : 0x%02X" % msg[0])
        fields = parse_info_response(msg)
        if fields:
            for k, v in fields:
                print("   %-22s %s" % (k, v))
        if msg and msg[0] == 0x1B:
            uuid_bytes = msg[1:17]
            print("   device uuid bytes    %s" % uuid_bytes.hex())
        hexs = msg.hex().lower()
        want = OUR_DEVICE_UUID.replace("-", "").lower()
        if want in hexs:
            print("*** THIS HUB IS OURS -- device_uuid matches the USB-read value ***")

    if not frames:
        print("\nNo complete frame came back. Either the hub ignored the request")
        print("(framing wrong) or it replies on a path we are not watching.")
        print("The absence is a result: record it rather than retrying blindly.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain(sys.argv)))
