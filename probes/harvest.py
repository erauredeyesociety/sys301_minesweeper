#!/usr/bin/env python3
"""harvest.py — grab EVERYTHING in one USB window. Run this the moment the cable goes in.

WHY THIS EXISTS
  On 2026-08-27 the robot was plugged in, probed narrowly one question at a
  time, and then unplugged for physical reasons before half the useful data had
  been taken. USB access on a robot that has to DRIVE is scarce and interrupted
  without warning. So the rule is: when the cable is in, harvest first and think
  afterwards. A question you did not ask costs a whole session.

ORDERING IS DELIBERATE AND LOAD-BEARING
  PHASE 1 runs BEFORE anything sends Ctrl-C, because Ctrl-C interrupts the LEGO
  Hub OS, and the Hub OS is what would answer the control protocol. Asking that
  question after dropping to the REPL would answer the wrong question.
  PHASE 2 then takes the REPL and reads everything else.

READ-ONLY. Listings, dir(), getters, file reads, and two protocol QUERIES.
It commands no motion and writes nothing to the hub.

    python3 probes/harvest.py                 # everything, saved under docs/findings/runs/
    python3 probes/harvest.py --quick         # skip the slow API-surface dump

Exit codes: 0 harvested · 2 partial · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cobs                                                 # noqa: E402
import _hubio                                                # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "docs", "findings", "runs")
BAUD = 115200

# ---------------------------------------------------------------- PHASE 2 sets
CORE = [
    ("uname",           "import os; print(os.uname())"),
    ("implementation",  "import sys; print(sys.implementation)"),
    ("path",            "import sys; print(sys.path)"),
    ("device_uuid",     "import hub; print(hub.device_uuid())"),
    ("hardware_id",     "import hub; print(hub.hardware_id())"),
    ("battery",         "import hub; print('mV', hub.battery_voltage(), 'mA', hub.battery_current(), 'degC', hub.temperature())"),
    ("mem",             "import gc; gc.collect(); print('free', gc.mem_free(), 'alloc', gc.mem_alloc())"),
    ("flash",           "import os; print(sorted(os.listdir('/flash')))"),
    ("flash/lib",       "import os; print(sorted(os.listdir('/flash/lib')) if 'lib' in os.listdir('/flash') else 'none')"),
    ("program slots",   "import os; print(sorted(os.listdir('/flash/program')))"),
    ("statvfs",         "import os; print(os.statvfs('/flash'))"),
]

PORTS = [
    ("device ids",
     'import device; from hub import port; '
     'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
     ' try:\\n  print(L, device.id(getattr(port,L)))\\n'
     ' except Exception as e:\\n  print(L, \'-\')")'),
    ("motor info",
     'import motor; from hub import port; '
     'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
     ' try:\\n  print(L, motor.info(getattr(port,L)))\\n'
     ' except Exception as e:\\n  print(L, \'-\')")'),
    ("motor encoders",
     'import motor; from hub import port; '
     'exec("for L in [\'A\',\'B\']:\\n'
     ' try:\\n  p=getattr(port,L)\\n  print(L, \'abs\', motor.absolute_position(p), \'rel\', motor.relative_position(p), \'vel\', motor.velocity(p), \'st\', motor.status(p))\\n'
     ' except Exception as e:\\n  print(L, \'-\', e)")'),
    ("colour sensors",
     'import color_sensor; from hub import port; '
     'exec("for L in [\'C\',\'D\']:\\n'
     ' try:\\n  p=getattr(port,L)\\n  print(L, \'color\', color_sensor.color(p), \'refl\', color_sensor.reflection(p), \'rgbi\', color_sensor.rgbi(p))\\n'
     ' except Exception as e:\\n  print(L, \'-\', e)")'),
    ("imu",
     "import hub; m=hub.motion_sensor; "
     "print('tilt', m.tilt_angles(), 'acc', m.acceleration(), 'gyro', m.angular_velocity(), "
     "'up', m.up_face(), 'stable', m.stable())"),
]

CONSTANTS = [
    ("motor status",  "import motor; print({n: getattr(motor,n) for n in ['READY','RUNNING','STALLED','ERROR','DISCONNECTED','CANCELLED','CONTINUE']})"),
    ("motor stop",    "import motor; print({n: getattr(motor,n) for n in ['COAST','BRAKE','HOLD','SMART_COAST','SMART_BRAKE']})"),
    ("colour",        "import color; print({n: getattr(color,n) for n in dir(color) if not n.startswith('_')})"),
    ("orientation",   "import orientation; print({n: getattr(orientation,n) for n in dir(orientation) if not n.startswith('_')})"),
]

API_SURFACE = [
    ("dir motor",           "import motor; print(dir(motor))"),
    ("dir motor_pair",      "import motor_pair; print(dir(motor_pair))"),
    ("dir runloop",         "import runloop; print(dir(runloop))"),
    ("dir color_sensor",    "import color_sensor; print(dir(color_sensor))"),
    ("dir distance_sensor", "import distance_sensor; print(dir(distance_sensor))"),
    ("dir force_sensor",    "import force_sensor; print(dir(force_sensor))"),
    ("dir device",          "import device; print(dir(device))"),
    ("dir motion_sensor",   "import hub; print(dir(hub.motion_sensor))"),
    ("dir light_matrix",    "import hub; print(dir(hub.light_matrix))"),
    ("dir sound",           "import hub; print(dir(hub.sound))"),
    ("modules",             "help('modules')"),
]


def phase1_protocol(port):
    """Ask the control protocol a question BEFORE any Ctrl-C exists on this port."""
    try:
        import serial
    except ImportError:
        return "NO_PYSERIAL", []
    lines = ["# PHASE 1 -- LEGO COBS control protocol over USB, no Ctrl-C sent"]
    frames = []
    try:
        ser = serial.Serial(port, BAUD, timeout=0.5, write_timeout=3.0)
    except Exception as exc:
        return "BUSY: %s" % exc, []
    try:
        ser.reset_input_buffer()
        buf = bytearray()
        for label, mid in (("InfoRequest", _cobs.INFO_REQUEST),
                           ("DeviceUuidRequest", _cobs.DEVICE_UUID_REQUEST)):
            frame = _cobs.pack(bytes([mid]))
            lines.append("-> %-20s %s" % (label, frame.hex(" ")))
            ser.write(frame)
            deadline = time.monotonic() + 3.5
            while time.monotonic() < deadline:
                chunk = ser.read(256)
                if chunk:
                    buf.extend(chunk)
                    got, rest = _cobs.split_frames(buf)
                    buf = bytearray(rest)
                    for f in got:
                        frames.append(f)
                        lines.append("<- raw %s" % f.hex(" "))
                        msg = _cobs.unpack(f)
                        lines.append("   decoded %s" % msg.hex(" "))
                        info = _cobs.parse_info_response(msg)
                        if info:
                            for k, v in info.items():
                                lines.append("     %-22s %s" % (k, v))
                        if msg and msg[0] == _cobs.DEVICE_UUID_RESPONSE:
                            lines.append("     device_uuid  %s" % msg[1:17].hex())
    finally:
        try:
            ser.close()
        except Exception:
            pass
    if not frames:
        lines.append("NO FRAMES -- the control protocol did NOT answer on USB.")
        lines.append("That is a real result: this VCP is the MicroPython REPL only.")
    return "\n".join(lines), frames


def main(argv):
    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 — plug the hub in.")
        return 3
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    dest = os.path.join(OUT_DIR, "harvest-%s.txt" % stamp)

    print("HARVEST -- everything in one USB window. Saving to")
    print("  %s" % dest)
    print()

    chunks = []

    print("--- PHASE 1: control protocol (before any Ctrl-C) ---")
    text, frames = phase1_protocol(port)
    print(text)
    chunks.append(text)
    print()

    groups = [("CORE", CORE, 60.0), ("PORTS + LIVE READINGS", PORTS, 70.0),
              ("CONSTANTS", CONSTANTS, 50.0)]
    if "--quick" not in argv:
        groups.append(("API SURFACE", API_SURFACE, 90.0))

    failed = 0
    for title, probes, deadline in groups:
        print("--- PHASE 2: %s ---" % title)
        code, out = _hubio.run(probes, deadline=deadline, title=title, echo=False)
        if code != _hubio.OK:
            print("  FAILED (exit %d)" % code)
            failed += 1
        else:
            print(out)
        chunks.append("\n\n########## %s ##########\n%s" % (title, out))
        print()

    with open(dest, "w") as fh:
        fh.write("# harvest %s   port %s\n" % (stamp, port))
        fh.write("# READ-ONLY. Nothing was written to the hub.\n\n")
        fh.write("\n".join(chunks) + "\n")

    print("=" * 66)
    print("saved: %s" % dest)
    if frames:
        print("NOTABLE: the control protocol ANSWERED over USB -- slot upload over")
        print("the cable is possible, no BLE advertising window needed.")
    if failed:
        print("PARTIAL: %d group(s) failed." % failed)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
