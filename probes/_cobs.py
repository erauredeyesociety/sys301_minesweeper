"""_cobs.py — LEGO's framing for the SPIKE Prime control protocol.

The SAME protocol runs over BLE and over the USB serial port, so this lives in
one place and both transports import it. Do not copy it into a second file.

WHAT MAKES IT NOT ORDINARY COBS
  Standard COBS delimits frames with 0x00. LEGO delimits with 0x02, then XORs
  the whole frame by 3. The XOR is not decoration: COBS already escapes every
  byte <= 0x02, so all frame bytes are >= 3, and XOR-ing by 3 guarantees the
  delimiter 0x02 cannot reappear inside a frame (b ^ 3 == 2 would need b == 1,
  which cannot occur). It also keeps 0x03 -- Ctrl-C -- off the wire, which is
  exactly why the same bytes are safe on a serial port that also hosts a REPL.

VALIDATED ON REAL HARDWARE 2026-08-27, both directions:
  encoder: InfoRequest (payload 00) frames to 00 00 02, matching the value
           computed independently from LEGO's published cobs.py
  decoder: a real 17-byte InfoResponse decoded to fields that all landed on
           sensible values (rpc 1.0.47, firmware 1.8.149, max_packet_size 509,
           max_message_size 5000, max_chunk_size 4096)
  See docs/findings/ble-protocol-2026-08-27.md
"""

DELIMITER = 0x02
NO_DELIMITER = 0xFF
COBS_CODE_OFFSET = DELIMITER
MAX_BLOCK_SIZE = 84
XOR = 3

# Message ids we have actually exercised. Others exist; add them when used.
INFO_REQUEST = 0x00
INFO_RESPONSE = 0x01
DEVICE_UUID_REQUEST = 0x1A
DEVICE_UUID_RESPONSE = 0x1B


def encode(data):
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


def decode(data):
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
    """Message bytes -> a frame ready to put on the wire, delimiter included."""
    return bytes(b ^ XOR for b in encode(payload)) + bytes([DELIMITER])


def unpack(frame):
    """One frame with the delimiter already stripped -> message bytes."""
    return decode(bytes(b ^ XOR for b in frame))


def split_frames(buf):
    """Pull complete frames out of a running byte buffer.

    Returns (frames, remainder). Frames are delimiter-stripped and NOT yet
    unpacked, so a caller can log the raw bytes before trusting any decode.
    """
    frames = []
    while DELIMITER in buf:
        i = buf.index(DELIMITER)
        piece = bytes(buf[:i])
        buf = buf[i + 1:]
        if piece:
            frames.append(piece)
    return frames, buf


def parse_info_response(msg):
    """InfoResponse is 17 bytes with a documented layout. Parsing it is also the
    framing self-check: every field landing on a sensible value means the decode
    was right, and nonsense means it was not."""
    if len(msg) < 17 or msg[0] != INFO_RESPONSE:
        return None

    def u16(i):
        return msg[i] | (msg[i + 1] << 8)

    return {
        "rpc_version": "%d.%d.%d" % (msg[1], msg[2], u16(3)),
        "firmware_version": "%d.%d.%d" % (msg[5], msg[6], u16(7)),
        "max_packet_size": u16(9),
        "max_message_size": u16(11),
        "max_chunk_size": u16(13),
        "product_group_device": u16(15),
    }
