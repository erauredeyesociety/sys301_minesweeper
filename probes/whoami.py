#!/usr/bin/env python3
"""whoami.py — WHICH HUB IS OURS? Read our hub's unique identity over the CABLE.

This exists because the classroom will have several SPIKE Prime hubs advertising
over Bluetooth at once, and a BLE scan alone cannot tell you which one is yours.

The cable can. USB is point-to-point: whatever answers on /dev/spike is the hub
physically plugged into this laptop, with no ambiguity. So we read the permanent
identifiers here, write them down, and later match a BLE advertisement against
them instead of guessing from a list of look-alike names.

READ-ONLY. Writes nothing to the hub, changes no setting, touches no firmware.

    python3 probes/whoami.py            # print the identity block
    python3 probes/whoami.py --save     # also append it to docs/findings/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

PROBES = [
    ("uname",        "import os; print(os.uname())"),
    ("device_uuid",  "import hub; print(hub.device_uuid())"),
    ("hardware_id",  "import hub; print(hub.hardware_id())"),
    ("config",       "import hub; print(hub.config)"),
    ("config dir",   "import hub; print(dir(hub.config))"),
    ("battery",      "import hub; print('mV', hub.battery_voltage(), 'degC', hub.temperature())"),
    ("charging",     "import hub; print('usb_charge_mA', hub.usb_charge_current())"),
    ("implementation", "import sys; print(sys.implementation)"),
]


def main(argv):
    code, text = _hubio.run(
        PROBES,
        deadline=45.0,
        title="whoami — permanent identity of the hub on the USB cable",
    )
    if code != _hubio.OK:
        return code

    uuid = _hubio.value(text, "device_uuid")
    hwid = _hubio.value(text, "hardware_id")

    print()
    print("HOW TO USE THIS")
    if uuid or hwid:
        print("  device_uuid : %s" % (uuid or "not returned"))
        print("  hardware_id : %s" % (hwid or "not returned"))
        print()
        print("  These are permanent and unique to this physical hub. Record them.")
        print("  When several hubs are advertising in class, match against these")
        print("  rather than trusting a Bluetooth display name -- names collide,")
        print("  and anyone can rename a hub.")
    else:
        print("  Neither identifier came back. Re-run; if still empty, record")
        print("  UNKNOWN rather than substituting the Bluetooth name.")

    if "--save" in argv:
        dest = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "findings", "_hub-whoami.transcript.txt",
        )
        with open(dest, "w") as fh:
            fh.write(text + "\n")
        print("\n  saved: %s" % dest)
    return _hubio.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
