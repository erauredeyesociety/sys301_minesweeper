#!/usr/bin/env python3
"""bluetooth_state.py — is the hub's radio on, and can OUR code use it?

Two separate questions, often confused:
  A. Does the hub's FIRMWARE have Bluetooth running (the LEGO app connects to it)?
  B. Can a Python program WE write open its own BLE socket?

The presence of a 'bluetooth' module in help('modules') suggests B may be
possible, which contradicts an inference this project made earlier. This probe
gathers evidence without acting on it.

STRICTLY READ-ONLY. It inspects classes with dir() and reads getters. It does
NOT call bluetooth.BLE(), does NOT call active(True), does NOT advertise, pair,
or connect. Instantiating the BLE stack could collide with the firmware's own
use of the radio, and that is an operator decision, not a probe's.

    python3 probes/bluetooth_state.py

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

PROBES = [
    # What the module offers, without instantiating anything.
    ("module",        "import bluetooth; print(bluetooth)"),
    ("dir bluetooth", "import bluetooth; print(dir(bluetooth))"),
    ("dir BLE class", "import bluetooth; print(dir(bluetooth.BLE))"),
    ("BLE doc",       "import bluetooth; print(getattr(bluetooth.BLE, '__doc__', None))"),

    # Does the firmware expose its own radio state anywhere on hub?
    ("dir hub",       "import hub; print(dir(hub))"),
    ("hub.light",     "import hub; print(dir(hub.light))"),
    ("dir button",    "import hub; print(dir(hub.button))"),

    # The buttons themselves -- the operator is pressing one and seeing nothing.
    ("button consts", "import hub; print([b for b in dir(hub.button) if not b.startswith('_')])"),

    # Is there a system/menu module that owns the BLE name?
    ("dir machine",   "import machine; print(dir(machine))"),
    ("unique_id",     "import machine; print(machine.unique_id())"),

    # Anything on the filesystem that names the hub?
    ("flash",         "import os; print(os.listdir('/flash'))"),
]


def main():
    code, text = _hubio.run(
        PROBES,
        deadline=55.0,
        title="bluetooth_state — read-only. Does NOT instantiate BLE().",
    )
    print()
    print("READING THIS")
    print("  'dir bluetooth' showing BLE plus UUID/FLAG_* constants means this is")
    print("  the standard MicroPython ubluetooth module, and a hub program could")
    print("  in principle drive the radio. It does NOT prove the firmware will")
    print("  allow it while its own stack is running -- that needs a deliberate")
    print("  test the operator approves, not a probe.")
    return code


if __name__ == "__main__":
    sys.exit(main())
