# find_note.py -> program.py. Drive forward until a STICKY NOTE is seen, stop, and say which colour.
# ./hub_programmer/slot_upload.py examples/find_note.py --apply  -> hub shows "S"; UNPLUG USB, set the
# robot on the carpet facing the note, tap LEFT/RIGHT, stand clear. Replug when the box shows, then:
#   python3 hub_programmer/download.py --all && scripts/decode_telemetry.py
# NOTE: run.py/probes send Ctrl-C which KILLS the Hub OS; POWER-CYCLE the hub before a slot upload.
# Only dep: hub_telemetry_log (in /flash/lib). MicroPython: no f-strings.
#
# THIS IS GATE 1. Detecting a REAL mine on a REAL floor WHILE MOVING is the oldest open question in
# the project (KU-M22 / KU-M32). A hand-held capture cannot answer it; this can.
#
# THE RULE IS BRIGHTNESS, AND IT IS MEASURED (docs/findings/runs/surface-survey-2026-09-08.txt, today,
# both sensors, at this mount height):
#     carpet      reflection  3 - 9        blue tape   reflection  7 - 9
#     yellow note reflection 51 - 73       pink note   reflection 97+
# Zero overlap, and a 43-point gap between the brightest carpet and the dimmest note. NOTE_REFL_MIN
# sits at 30 -- 21 points clear above carpet+tape and 21 points clear below yellow, i.e. dead centre.
#
# WHY BRIGHTNESS AND NOT COLOUR: the carpet is so dark (r+g+b ~ 79 counts) that its chromaticity
# spread is smaller than ONE ADC count -- pure quantisation noise. That noise is what the
# chromaticity anomaly rule divides by, which is why YELLOW measures INVISIBLE to it while the BLUE
# TAPE trips it 100% of the time. Brightness has the opposite character: a dark floor is exactly what
# it wants. It is also COLOUR-AGNOSTIC, so it still works if the mine colour changes on demo day.
#
# THE BLUE TAPE NEEDS NO SPECIAL CASE. It measures 7-9, INSIDE the carpet band, so it is ignored for
# free. No veto, no blue threshold, no extra module.
#
# Colour is reported only AFTER the brightness gate fires, and only to name what was found -- it never
# gates the count. An unclassifiable note is reported UNKNOWN, never forced into a class.
import time
import runloop
import motor
import color_sensor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog

PL = port.A            # left motor
PR = port.B            # right motor
PC = port.C
PD = port.D
# DIRECTION: forward = A:-v, B:+v, the "measured mirror" convention recorded in CLAUDE.md and proven by
# examples/motor_poc.py (drive-checkpoint 2026-09-01). CONFIRMED AGAIN 2026-09-08: a run with this
# flipped to -1 drove BACKWARD, and the operator confirmed the original sign is correct -- the earlier
# apparent reversal was an operating mishap, not a wrong constant. Left as one knob so a future chassis
# change is a one-character edit rather than a hunt through the motor calls.
DIRECTION = 1          # 1 = the recorded, twice-confirmed convention. Do not flip without watching it.
LEFT_FWD = -1 * DIRECTION
RIGHT_FWD = 1 * DIRECTION
SPEED_DPS = 100        # ~55 mm/s at the MEASURED 63.5 mm wheel. Coast after stop measured ~3 mm.
MAX_DEG = 2000         # hard distance cap, ~1100 mm
RUN_CAP_MS = 25000     # hard time cap
ARM_TIMEOUT_MS = 90000
COUNTDOWN_S = 5
TICK_MS = 50           # 20 Hz -- MEASURED achievable in examples/drive_to_tape.py today

NOTE_REFL_MIN = 30     # MEASURED gap: carpet+tape max 9  ->  yellow min 51. Dead centre.
CONSEC_NEEDED = 2      # two in a row, so one bright speck cannot stop the run
# Yellow r/(r+g+b) = 0.355, pink = 0.464, both stable across the whole usable height range. The
# midpoint 0.41 is ~0.05 from each, and blue is ~0.295 on BOTH so it carries no information here.
PINK_R_FRAC_MIN = 0.41

S_GLYPH = (0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0)
BOX = (1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1)
FULL = (1,) * 25
BANG = (0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0)   # found it
HEADER = ("seq,t_ms,phase,relA_deg,relB_deg,velL,velR,statusL,statusR,"
          "yaw_ddeg,accx_mg,accy_mg,accz_mg,reflC_pct,rC,gC,bC,iC,reflD_pct,rD,gD,bD,iD,reason")


class StopRun(Exception):
    pass


def show(pattern):
    light_matrix.show([100 if v else 0 for v in pattern])


def tapped():
    try:
        return button.pressed(button.LEFT) > 0 or button.pressed(button.RIGHT) > 0
    except Exception:
        return False


def none_ok(fn):
    try:
        return fn()
    except Exception:
        return None


def beep(hz, ms):
    try:
        import hub
        hub.sound.beep(hz, ms, 20)
    except Exception:
        pass                      # [UNVERIFIED] signature; a silent hub must not fail the run


def name_colour(rgbi_sample):
    """-> 'YELLOW' / 'PINK' / 'UNKNOWN'. Reporting only -- this NEVER gates the count.

    UNKNOWN rather than a forced guess: a wrong colour stated confidently is worse than an honest
    'I could not tell', and the count is already correct without it.
    """
    if rgbi_sample is None or rgbi_sample[0] is None:
        return "UNKNOWN"
    tot = rgbi_sample[0] + rgbi_sample[1] + rgbi_sample[2]
    if tot <= 0:
        return "UNKNOWN"
    if rgbi_sample[0] >= 1000 or rgbi_sample[1] >= 1000 or rgbi_sample[2] >= 1000:
        return "UNKNOWN"          # saturated: ratios collapse to 33/33/33, no colour left
    return "PINK" if (float(rgbi_sample[0]) / tot) >= PINK_R_FRAC_MIN else "YELLOW"


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: set the robot on the carpet facing the note, then tap LEFT or RIGHT")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if tapped():
            return True
        await runloop.sleep_ms(50)
    return False


async def countdown():
    for s in range(COUNTDOWN_S, 0, -1):
        show(FULL if (s % 2) else BOX)
        print("COUNTDOWN %d" % s)
        await runloop.sleep_ms(1000)


async def find_note():
    log = CsvLog(HEADER, prefix="findnote", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    box = {"seq": 0, "hits": 0, "colour": "UNKNOWN", "refl": 0}

    def sample(phase):
        """Log one full row; return True when THIS tick looks like a note (brightness only)."""
        t = time.ticks_diff(time.ticks_ms(), t0)
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        cc = none_ok(lambda: color_sensor.rgbi(PC)) or (None, None, None, None)
        cd = none_ok(lambda: color_sensor.rgbi(PD)) or (None, None, None, None)
        rc = none_ok(lambda: color_sensor.reflection(PC))
        rd = none_ok(lambda: color_sensor.reflection(PD))
        row = (box["seq"], t, phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
               rc, cc[0], cc[1], cc[2], cc[3], rd, cd[0], cd[1], cd[2], cd[3], "")
        log.append(",".join("" if v is None else str(v) for v in row))
        box["seq"] += 1

        # A failed read is NOT a detection -- None must never stop the robot.
        hit_c = rc is not None and rc >= NOTE_REFL_MIN
        hit_d = rd is not None and rd >= NOTE_REFL_MIN
        if hit_c or hit_d:
            # Name it from whichever sensor is brighter -- that one is furthest onto the note.
            if hit_c and (not hit_d or rc >= rd):
                box["colour"] = name_colour(cc)
                box["refl"] = rc
            else:
                box["colour"] = name_colour(cd)
                box["refl"] = rd
            return True
        return False

    def guard():
        if tapped():
            raise StopRun("STOP_button")
        if time.ticks_diff(time.ticks_ms(), t0) >= RUN_CAP_MS:
            raise StopRun("time_cap")

    reason = "time_cap"
    l0 = 0
    try:
        motor.run(PL, LEFT_FWD * SPEED_DPS)
        motor.run(PR, RIGHT_FWD * SPEED_DPS)
        l0 = motor.relative_position(PL)
        while True:
            guard()
            if abs(motor.relative_position(PL) - l0) >= MAX_DEG:
                reason = "distance_cap"
                break
            if sample("search"):
                box["hits"] += 1
                if box["hits"] >= CONSEC_NEEDED:
                    reason = "NOTE_FOUND"
                    break
            else:
                box["hits"] = 0
            await runloop.sleep_ms(TICK_MS)
    except StopRun as exc:
        reason = exc.args[0]
    finally:
        motor.stop(PL)
        motor.stop(PR)
        for _ in range(4):                 # capture the TRUE stopping point, motors already cut
            sample("stopped")
            await runloop.sleep_ms(100)
        travelled = abs((none_ok(lambda: motor.relative_position(PL)) or l0) - l0)
        mm = travelled / 360.0 * 199.49    # 63.5 mm wheel, MEASURED 2026-09-03
        log.append("#end reason=%s colour=%s refl=%s rows=%d deg=%d mm=%d"
                   % (reason, box["colour"], box["refl"], box["seq"], travelled, int(mm)))
        log.close()
        if reason == "NOTE_FOUND":
            show(BANG)
            beep(880, 120)
            time.sleep_ms(160)
            beep(1320, 200)
        else:
            show(BOX)
        print("FIND_NOTE done: %s colour=%s refl=%s after %d rows, %d deg (~%d mm) -> %s"
              % (reason, box["colour"], box["refl"], box["seq"], travelled, int(mm), log.path))


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    await countdown()
    await find_note()


runloop.run(main())
