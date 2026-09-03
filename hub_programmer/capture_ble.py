#!/usr/bin/env python3
"""capture_ble.py -- capture raw Hub OS telemetry notifications to tmp/telemetry.

Run this only in the clean Hub OS state: power-cycle the hub, press CONNECT once, and do not run
REPL tools first. It does not command motors. If a slot program is moving motors, this should still
be able to listen to firmware DeviceNotification frames once BLE coexistence is proven.

    python3 hub_programmer/capture_ble.py --seconds 30 --interval-ms 100

Exit codes: 0 capture finished · 2 identity mismatch · 3 no BLE/hub · 5 missing bleak · 64 usage
"""
import csv
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slot_upload                                            # noqa: E402

DEVICE_NOTIFICATION_REQUEST = 0x28
DEVICE_NOTIFICATION_RESPONSE = 0x29
DEVICE_NOTIFICATION = 0x3C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEST = os.path.join(ROOT, "tmp", "telemetry")


def opt(argv, flag, default):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 >= len(argv):
            raise ValueError("%s needs a value" % flag)
        return argv[i + 1]
    return default


def m_device_notification_request(interval_ms):
    return struct.pack("<BH", DEVICE_NOTIFICATION_REQUEST, int(interval_ms))


def _s16(data, offset):
    return struct.unpack_from("<h", data, offset)[0]


def _u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _i32(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def port_name(n):
    return "ABCDEF"[n] if 0 <= n < 6 else str(n)


def summarize_device_notification(msg):
    """Best-effort decode of DeviceNotification 0x3C; raw bytes remain authoritative."""
    if len(msg) < 3 or msg[0] != DEVICE_NOTIFICATION:
        return ""
    total = _u16(msg, 1)
    data = msg[3:]
    out = ["size=%d" % total]
    i = 0
    sizes = {0: 2, 1: 21, 2: 26, 10: 12, 11: 4, 12: 9, 13: 4, 14: 11}
    while i < len(data):
        t = data[i]
        n = sizes.get(t)
        if n is None or i + n > len(data):
            out.append("raw_tail@%d=%s" % (i, data[i:].hex()))
            break
        rec = data[i:i + n]
        if t == 0:
            out.append("battery=%d" % rec[1])
        elif t == 1:
            vals = [_s16(rec, 3 + 2 * k) for k in range(9)]
            out.append("imu faces=%d/%d vals=%s" % (rec[1], rec[2], vals))
        elif t == 10:
            out.append("motor%s type=%d abs=%d power=%d speed=%d pos=%d" %
                       (port_name(rec[1]), rec[2], _s16(rec, 3), _s16(rec, 5),
                        struct.unpack_from("<b", rec, 7)[0], _i32(rec, 8)))
        elif t == 12:
            out.append("color%s code=%d rgb=(%d,%d,%d)" %
                       (port_name(rec[1]), struct.unpack_from("<b", rec, 2)[0],
                        _u16(rec, 3), _u16(rec, 5), _u16(rec, 7)))
        elif t == 13:
            out.append("distance%s=%d" % (port_name(rec[1]), _u16(rec, 2)))
        else:
            out.append("type%d=%s" % (t, rec.hex()))
        i += n
    return "; ".join(out)


def output_path(dest, interval_ms, seconds):
    os.makedirs(dest, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    return os.path.join(dest, "%s-ble-%dms-%ds.csv" % (stamp, interval_ms, seconds))


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__.strip())
        return 64
    try:
        seconds = int(float(opt(argv, "--seconds", "30")))
        interval_ms = int(float(opt(argv, "--interval-ms", "1000")))
        address = opt(argv, "--address", slot_upload.OUR_BLE_ADDRESS)
        wait_s = float(opt(argv, "--wait", "60"))
        dest = opt(argv, "--dest", DEFAULT_DEST)
    except ValueError as exc:
        print(exc)
        return 64
    if seconds <= 0 or interval_ms < 0:
        print("--seconds must be positive and --interval-ms must be non-negative")
        return 64

    try:
        import bleak                                           # noqa: F401
    except ImportError:
        print("NO_BLEAK: python3 -m pip install --user bleak")
        return 5

    out = output_path(dest, interval_ms, seconds)
    tx = None
    count = 0
    try:
        tx = slot_upload.BleTransport(address, wait_s)
        tx.open()

        print("\n[1] identity: DeviceUuidRequest 0x1A")
        msg = slot_upload.request(tx, slot_upload.m_device_uuid_request(),
                                  slot_upload.DEVICE_UUID_RESPONSE, deadline=6.0)
        if not msg or len(msg) < 17 or not slot_upload.uuid_matches(msg[1:17]):
            print("identity mismatch or no DeviceUuidResponse; capture aborted")
            return 2

        print("\n[2] InfoRequest 0x00")
        info = slot_upload.request(tx, slot_upload.m_info_request(),
                                   slot_upload.INFO_RESPONSE, deadline=6.0)
        if info:
            fields = slot_upload._cobs.parse_info_response(info)
            print("    %s" % fields)

        print("\n[3] DeviceNotificationRequest interval=%d ms" % interval_ms)
        slot_upload.request(tx, m_device_notification_request(interval_ms),
                            DEVICE_NOTIFICATION_RESPONSE, deadline=6.0)

        print("\n[4] capturing %.0f s -> %s" % (seconds, out))
        with open(out, "w", newline="") as fh:
            fh.write("# ble DeviceNotification capture\n")
            fh.write("# address,%s\n" % address)
            fh.write("# interval_ms,%d\n" % interval_ms)
            writer = csv.writer(fh)
            writer.writerow(["rx_ms", "msg_id_hex", "payload_len", "summary", "payload_hex", "frame_hex"])
            start = time.monotonic()
            end = start + seconds
            while time.monotonic() < end:
                frame = tx.recv(end - time.monotonic())
                if frame is None:
                    break
                rx_ms = int((time.monotonic() - start) * 1000.0)
                try:
                    msg = slot_upload._cobs.unpack(frame)
                except Exception as exc:
                    writer.writerow([rx_ms, "DECODE_FAIL", len(frame), type(exc).__name__, "", frame.hex()])
                    continue
                mid = msg[0] if msg else -1
                if mid == DEVICE_NOTIFICATION:
                    count += 1
                writer.writerow([rx_ms, "0x%02X" % mid if mid >= 0 else "",
                                 max(0, len(msg) - 1), summarize_device_notification(msg),
                                 msg.hex(), frame.hex()])
        print("captured %d DeviceNotification frame(s)" % count)
        return 0
    except Exception as exc:
        print("BLE ERROR: %s: %s" % (type(exc).__name__, exc))
        return 3
    finally:
        if tx is not None:
            try:
                tx.send(m_device_notification_request(0))
            except Exception:
                pass
            tx.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
