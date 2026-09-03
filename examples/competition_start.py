# examples/competition_start.py -- the competition START ritual, proven end to end. NO MOTORS.
#
# Proves the operational shell competition needs, decoupled from the (still-unknown) sweep/detection
# algorithm:  ARM ("S") -> operator taps LEFT/RIGHT -> 10 s countdown -> autonomous phase (here:
# event-filtered logging, no motion) -> DONE.  It is safe on a desk / white paper.
#
# WHY LEFT/RIGHT AND NOT CENTER for the tap:  the CENTER button (button.POWER) belongs to the
# firmware -- a single press from the slot menu is what LAUNCHED this program, and a press WHILE it
# runs STOPS it (docs/research/hub-menu-and-buttons-2026-09-03.md).  A program therefore cannot use
# CENTER as its own input; the operator's deliberate "go" is a LEFT or RIGHT tap, which a program
# CAN read.  So the full competition start is a TWO-stage gesture:
#     menu digit -> single CENTER press (firmware launches program.py)
#     "S" on matrix -> LEFT/RIGHT tap (this program arms) -> 10 s -> run.
#
# DEPENDENCIES must be on the hub in /flash/lib before this slot runs -- this IS the real
# competition deploy (program.py plus its src/ modules):
#     hub_api  hub_ui  event_filter  hub_telemetry_log
# See docs/runbooks/competition-start-stop.md for the one deploy command and the operator gesture.
#
# SLOT RUN (the real test):
#     ./hub_programmer/slot_upload.py examples/competition_start.py --apply --listen 30
#     then on the hub: navigate to the slot, single-press CENTER, and tap LEFT/RIGHT when "S" shows.
#     afterwards:  python3 hub_programmer/download.py --all  &&  scripts/decode_telemetry.py
#
# Running this ALSO exercises hub_ui.show_glyph / show_digit / button_pressed on real hardware for
# the first time -- their SPIKE 3 call sites were written but never run.
#
# MicroPython: no f-strings.

import time
import runloop
import color_sensor
from hub import motion_sensor, port
import hub_ui
from event_filter import EventFilter
from hub_telemetry_log import CsvLog

COUNTDOWN_S = 10          # the operator's "clear the arena" window
ARM_TIMEOUT_MS = 90000    # if no tap in 90 s, FAULT out loud rather than wait forever on the desk
RUN_MS = 30000            # autonomous phase length for this proof (competition run has a real stop)
TICK_MS = 100
PC = port.C               # colour sensors, front corners
PD = port.D

COLUMNS = (
    "seq", "t_ms", "phase",
    "yaw_ddeg", "pitch_ddeg", "roll_ddeg", "accx_mg", "accy_mg", "accz_mg",
    "reflC_pct", "reflD_pct", "reason",
)

# Deadbands in each channel's own units: log a row only when something actually moved. yaw 30 ddeg =
# 3 deg of turn; accx 150 mg = a real bump; reflection 8 % = a surface change worth a SLAM landmark.
DEADBANDS = {"yaw_ddeg": 30, "pitch_ddeg": 40, "accx_mg": 150, "reflC_pct": 8, "reflD_pct": 8}
HEARTBEAT_MS = 2000       # never go more than 2 s without a row, so a quiet stretch is still alive


def none_ok(fn):
    try:
        return fn()
    except Exception:
        return None


async def wait_for_tap():
    """Show 'S' and wait for a LEFT/RIGHT tap. Returns True on tap, False on timeout (a fault)."""
    hub_ui.show_glyph("s")
    print("ARMED: showing 'S' -- tap LEFT or RIGHT to start the countdown")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ARM_TIMEOUT_MS:
        # button_pressed returns True/False, or None if it cannot read -- None must NOT read as a tap.
        if hub_ui.button_pressed("left") is True or hub_ui.button_pressed("right") is True:
            return True
        await runloop.sleep_ms(50)
    return False


async def countdown():
    """10..1 on the matrix (full frame = 10, digits 9..1), then the running glyph. Console mirrors it."""
    for s in range(COUNTDOWN_S, 0, -1):
        if s >= 10:
            hub_ui.show_glyph("block")     # two digits won't fit; a full frame means "ten"
        else:
            hub_ui.show_digit(s)
        print("COUNTDOWN %d" % s)
        await runloop.sleep_ms(1000)
    hub_ui.show_glyph("arrow")             # autonomous phase running


async def autonomous_logging_phase():
    """The placeholder 'mission': read IMU + both colour sensors, log only significant samples."""
    ef = EventFilter(DEADBANDS, heartbeat_ms=HEARTBEAT_MS)
    log = CsvLog(",".join(COLUMNS), prefix="startritual", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    seq = 0
    written = 0
    stopped_by = "timeout"
    try:
        while time.ticks_diff(time.ticks_ms(), t0) < RUN_MS:
            t = time.ticks_diff(time.ticks_ms(), t0)
            # SOFT STOP: a LEFT/RIGHT tap ends the run cleanly. The arming tap is long released by
            # now (the 10 s countdown separates them), so this cannot self-trigger. In the real
            # mission this same branch also calls motor.stop() on both drives before breaking.
            # The firmware CENTER press is the independent HARD stop of last resort.
            stop_tap = hub_ui.button_pressed("left") is True or hub_ui.button_pressed("right") is True
            tilt = none_ok(lambda: motion_sensor.tilt_angles()) or (None, None, None)
            acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
            rc = none_ok(lambda: color_sensor.reflection(PC))
            rd = none_ok(lambda: color_sensor.reflection(PD))
            values = {"yaw_ddeg": tilt[0], "pitch_ddeg": tilt[1],
                      "accx_mg": acc[0], "reflC_pct": rc, "reflD_pct": rd}
            # A stop is a significant event -- force it into the log so the run's end is timestamped.
            reason = ef.consider(t, values, event=("STOP" if stop_tap else None))
            if reason:
                row = (seq, t, "run", tilt[0], tilt[1], tilt[2], acc[0], acc[1], acc[2], rc, rd, reason)
                log.append(",".join("" if v is None else str(v) for v in row))
                written += 1
            seq += 1
            if stop_tap:
                stopped_by = "button"
                print("STOP: operator tapped LEFT/RIGHT -- ending run early")
                break
            await runloop.sleep_ms(TICK_MS)
    finally:
        kept, dropped, frac = ef.summary()
        log.append("#filter kept=%d dropped=%d frac=%.3f" % (kept, dropped, frac))
        log.close()
        print("RUN done: %d ticks, %d rows written (%.1f%% kept) -> %s"
              % (seq, written, 100.0 * frac, log.path))


async def main():
    print("=== competition START ritual (no motors) ===")
    armed = await wait_for_tap()
    if not armed:
        hub_ui.show_glyph("x")
        print("NOT ARMED: no LEFT/RIGHT tap in %d s -- buttons unreadable or nobody tapped. FAULT."
              % (ARM_TIMEOUT_MS // 1000))
        return
    print("armed -> %d s countdown" % COUNTDOWN_S)
    await countdown()
    await autonomous_logging_phase()
    hub_ui.show_glyph("border")            # DONE -- a steady box, distinct from the running arrow
    print("=== ritual complete ===")


runloop.run(main())
