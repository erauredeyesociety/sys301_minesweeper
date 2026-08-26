#!/usr/bin/env python3
"""Is the SPIKE Prime hub connected, and can this computer talk to it?

    ./find_spike_prime.py              one-line verdict
    ./find_spike_prime.py --verbose    what it found, and what to do about it

Works on Linux, Windows and macOS -- it asks pyserial for the port list, which is the same on all
three. Teammates on Windows can run it unchanged.

WHAT IT DOES NOT DO, deliberately: it never sends anything to the hub and never waits for a reply.
It opens the port for a moment to prove the permissions work, then closes it. A blocking serial read
can hang forever, which is why every hub-touching thing here is bounded
(docs/directives/automation-first.md).

Exit codes, so a script can branch on the answer:
    0  READY        hub found and the port opens
    1  NOT_FOUND    no SPIKE Prime on any port
    2  BUSY         found, but something else holds the port
    3  NO_ACCESS    found, but this user cannot open it (Linux: not in dialout)
    4  NO_PYSERIAL  pyserial is not installed
   64  usage error
"""

import sys
import platform

# LEGO Education SPIKE Prime Technic Large Hub, in USB CDC-ACM mode.
# Source: docs/research/spike-prime-linux-toolchain.md. Edit here if a different hub turns up --
# print the --verbose output and add its VID/PID rather than guessing.
LEGO_VID = 0x0694
SPIKE_PIDS = {
    0x0009: "SPIKE Prime / Technic Large Hub (CDC-ACM)",
    0x0010: "SPIKE Essential (not ours, but recognised so the message is useful)",
}

READY, NOT_FOUND, BUSY, NO_ACCESS, NO_PYSERIAL, USAGE = 0, 1, 2, 3, 4, 64


def hints(state):
    """Platform-specific next step. Kept short -- the runbook has the detail."""
    win = platform.system() == "Windows"
    mac = platform.system() == "Darwin"
    if state == NOT_FOUND:
        common = ["Is the hub switched on? Hold the centre button until the lights come up.",
                  "Try the other end of the cable, and a different cable -- many LEGO USB cables",
                  "  are charge-only and produce no port at all."]
        if win:
            return common + ["Open Device Manager and look under Ports (COM & LPT) for a new entry.",
                             "If it shows with a warning triangle, install the LEGO SPIKE app once to",
                             "  get the driver, then close it -- do NOT let it update the hub."]
        return common + ["Linux: run  dmesg | tail -20  and look for 'cdc_acm ... ttyACM0'."]
    if state == NO_ACCESS:
        if win:
            return ["Close anything that might hold the port (the SPIKE app, a serial terminal),",
                    "then try again."]
        if mac:
            return ["Unusual on macOS. Close any serial terminal and retry."]
        return ["You are not in the 'dialout' group. Fix it once, then log out and back in:",
                "    sudo usermod -aG dialout $USER",
                "Do NOT work around this with sudo -- it leaves root-owned lock files behind."]
    if state == BUSY:
        if win:
            return ["Close the LEGO SPIKE app, any VS Code serial monitor, and PuTTY.",
                    "If it persists, unplug and replug the hub."]
        return ["Find the holder:   sudo fuser -v <port>       (or: sudo lsof <port>)",
                "Usual suspects: ModemManager, brltty, a detached screen session, a Chrome tab",
                "  holding the port via WebSerial.",
                "ModemManager:   sudo systemctl disable --now ModemManager",
                "Stale screen:   screen -ls   then   screen -X -S <id> quit"]
    return []


def find_ports():
    """Every serial port that looks like a LEGO hub. Returns (matches, all_ports)."""
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    matches = [p for p in ports if p.vid == LEGO_VID and p.pid in SPIKE_PIDS]
    if not matches:
        # Fall back to a name match: a hub in an unexpected mode still says LEGO somewhere.
        matches = [p for p in ports
                   if "lego" in (str(p.manufacturer) + str(p.product) + str(p.description)).lower()]
    return matches, ports


def can_open(device):
    """Open the port briefly to prove permissions, then close. Never reads. Never blocks."""
    import serial
    try:
        s = serial.Serial(device, 115200, timeout=0, write_timeout=0)
        s.close()
        return READY, None
    except serial.SerialException as exc:
        text = str(exc).lower()
        if "permission" in text or "access is denied" in text:
            return NO_ACCESS, str(exc)
        if "busy" in text or "in use" in text or "resource" in text:
            return BUSY, str(exc)
        return BUSY, str(exc)
    except Exception as exc:                      # unexpected -> UNKNOWN, never a pass
        return BUSY, repr(exc)


def main():
    args = sys.argv[1:]
    verbose = args in (["-v"], ["--verbose"])
    if args and not verbose:
        print("usage: find_spike_prime.py [--verbose]", file=sys.stderr)
        return USAGE

    try:
        matches, ports = find_ports()
    except ImportError:
        print("NO_PYSERIAL: pyserial is not installed.")
        print("  pip install pyserial        (Linux: sudo apt install python3-serial)")
        return NO_PYSERIAL

    if not matches:
        print("NOT FOUND: no SPIKE Prime detected.")
        if verbose:
            # Only USB devices carry a VID/PID. Bare motherboard ports (ttyS*, unused COM*)
            # are always present and never the hub, so listing them just buries the signal.
            usb = [p for p in ports if p.vid is not None]
            print("\nUSB serial devices this computer can see ({0}):".format(len(usb)))
            for p in usb:
                print("  {0:<20} {1:04x}:{2:04x}  {3}".format(p.device, p.vid, p.pid or 0,
                                                              p.description))
            if not usb:
                print("  (none -- no USB serial device is attached at all)")
            skipped = len(ports) - len(usb)
            if skipped:
                print("  ({0} non-USB ports hidden -- motherboard serial stubs, never the hub)"
                      .format(skipped))
            print("\nWhat to try:")
            for line in hints(NOT_FOUND):
                print("  " + line)
        return NOT_FOUND

    port = matches[0]
    state, detail = can_open(port.device)

    if state == READY:
        print("READY: SPIKE Prime on {0}".format(port.device))
    elif state == NO_ACCESS:
        print("NO ACCESS: found on {0}, but this user cannot open it.".format(port.device))
    else:
        print("BUSY: found on {0}, but something else is holding the port.".format(port.device))

    if verbose:
        name = SPIKE_PIDS.get(port.pid, "unrecognised PID -- check this is really our hub")
        print("\n  device        {0}".format(port.device))
        print("  identified as {0}".format(name))
        print("  vid:pid       {0:04x}:{1:04x}".format(port.vid or 0, port.pid or 0))
        print("  description   {0}".format(port.description))
        if port.serial_number:
            print("  serial        {0}".format(port.serial_number))
        if len(matches) > 1:
            print("  NOTE: {0} hubs matched; using the first.".format(len(matches)))
        if detail:
            print("\n  error: {0}".format(detail))
        for line in hints(state):
            print("  " + line)
        if state == READY:
            print("\n  The port opens, so the wiring and permissions are good.")
            print("  That is NOT the same as knowing the hub's API generation -- do that")
            print("  read-only first: docs/runbooks/hub-identification.md")

    return state


if __name__ == "__main__":
    sys.exit(main())
