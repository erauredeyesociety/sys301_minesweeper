#!/usr/bin/env python3
"""devices.py — identify what is on each port, and read it once.

Closes two unknowns in one pass:
  * KU-M15 -- the numeric values of the motor status constants. We saw an empty
    port report 5 and a motor report 0, but 5 was never mapped to a NAME.
  * KU-T3  -- which motors we own, confirmed by the hub's own device id rather
    than by eye.

READ-ONLY. Reads encoder positions and colour values. Does NOT command motion,
does NOT change a device mode, and does NOT assume the robot is still wired
A/B motors and C/D colour after a rebuild.

    python3 probes/devices.py

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

PROBES = [
    # The status constants, so a status number stops being a mystery.
    ("motor status constants",
     "import motor; print({n: getattr(motor, n) for n in "
     "['READY','RUNNING','STALLED','ERROR','DISCONNECTED','CANCELLED','CONTINUE']})"),

    ("stop constants",
     "import motor; print({n: getattr(motor, n) for n in "
     "['COAST','BRAKE','HOLD','SMART_COAST','SMART_BRAKE']})"),

    # What each port says it is.
    ("device ids A-F",
     'import device; from hub import port; '
     'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
     ' try:\\n  print(L, device.id(getattr(port,L)))\\n'
     ' except Exception as e:\\n  print(L, \'-\')")'),

    # Motors: encoder state, without moving anything. Known angular motor ids seen in LEGO docs and
    # our probes: 48/49/65. The loop keeps working if the Builder swaps ports later.
    ("motors A-F",
     'import device,motor; from hub import port; '
     'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
     ' p=getattr(port,L)\\n'
     ' try:\\n  did=device.id(p)\\n'
     ' except Exception:\\n  did=-1\\n'
     ' if did in (48,49,65):\\n'
     '  print(L, \'id\', did, \'info\', motor.info(p), \'abs\', motor.absolute_position(p), '
     '\'rel\', motor.relative_position(p), \'vel\', motor.velocity(p), \'duty\', '
     'motor.get_duty_cycle(p), \'status\', motor.status(p))\\n'
     ' else:\\n  print(L, \'not_motor\', did, \'status\', motor.status(p))")'),

    # Colour sensors: the three reads the mission depends on, over every port because rebuilds happen.
    ("colour sensors A-F",
     'import device,color_sensor; from hub import port; '
     'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
     ' p=getattr(port,L)\\n'
     ' try:\\n  did=device.id(p)\\n'
     ' except Exception:\\n  did=-1\\n'
     ' try:\\n  print(L, \'id\', did, \'color\', color_sensor.color(p), \'refl\', '
     'color_sensor.reflection(p), \'rgbi\', color_sensor.rgbi(p))\\n'
     ' except Exception as e:\\n  print(L, \'not_colour\', did)")'),

    # The colour constant table, so a returned integer can be named.
    ("colour constants",
     "import color; print({n: getattr(color, n) for n in dir(color) if not n.startswith('_')})"),
]


def main():
    code, text = _hubio.run(PROBES, deadline=90.0,
                            title="devices — what is on each port, read once")
    print()
    print("READING THIS")
    print("  device.id() 48 vs 49 vs 65 distinguishes angular motors. Whatever")
    print("  it reports is the answer -- the operator's recollection is not.")
    print()
    print("  colour: rgbi() is (r, g, b, intensity). Its RANGE is unknown until we")
    print("  see values over a bright and a dark surface -- do not assume 0-255.")
    return code


if __name__ == "__main__":
    sys.exit(main())
