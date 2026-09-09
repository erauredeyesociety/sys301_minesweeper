# calibrate_directions.py -> program.py. SETTLE what forward, backward, left and right actually mean.
# Needs hub_drive on the hub first:
#   ./hub_programmer/upload.py src/hub_drive.py --apply
#   ./hub_programmer/slot_upload.py examples/calibrate_directions.py --apply
#   -> hub shows "S"; UNPLUG, put the robot on open floor facing away from you, tap LEFT/RIGHT.
#   Replug, then: python3 hub_programmer/download.py --all && scripts/decode_telemetry.py
#
# ⚠ MOVES THE ROBOT. Clear ~600 mm ahead and behind, and room to spin. Every move is short and capped.
#
# WHY: direction was got wrong three times on 2026-09-08, every time by INFERRING it from another
# program's sign convention rather than measuring it. Encoder signs and yaw signs are CONVENTIONS,
# not directions -- only a human watching the robot can say which way it physically went. This is
# that measurement, made once, so src/hub_drive.py can own the answer.
#
# WHAT THE OPERATOR DOES: watch, and note whether each announced move matched its name. The hub
# announces each move on the matrix and with a beep BEFORE it moves, so there is no ambiguity about
# which move you are watching:
#     >  arrow up      FORWARD      (should move AWAY from you)
#     >  arrow down    BACKWARD     (should move TOWARD you)
#     >  R             SPIN RIGHT   (clockwise seen from ABOVE)
#     >  L             SPIN LEFT    (anticlockwise seen from above)
#
# The log records the encoder and yaw deltas for each, so the CONVENTIONS are captured alongside
# what actually happened. If a move went the wrong way, flip exactly one constant in
# src/hub_drive.py -- FORWARD_SIGN for the drives, TURN_SIGN for the spins -- and re-run this.
#
# MicroPython: no f-strings.
import time
import runloop
import motor
from hub import light_matrix, button, motion_sensor, port
from hub_telemetry_log import CsvLog
import hub_drive

PL = port.A
PR = port.B
SPEED_DPS = 100
DRIVE_MS = 1200        # ~66 mm at the measured 63.5 mm wheel -- visible, but small enough to be safe
SPIN_DDEG = 900        # 90 degrees
SETTLE_MS = 700        # let the robot come fully to rest before reading the end state
ARM_TIMEOUT_MS = 90000
COUNTDOWN_S = 5
TICK_MS = 50

S_GLYPH = (0,1,1,1,1, 1,0,0,0,0, 0,1,1,1,0, 0,0,0,0,1, 1,1,1,1,0)
BOX = (1,1,1,1,1, 1,0,0,0,1, 1,0,0,0,1, 1,0,0,0,1, 1,1,1,1,1)
FULL = (1,)*25
UP = (0,0,1,0,0, 0,1,1,1,0, 1,0,1,0,1, 0,0,1,0,0, 0,0,1,0,0)
DOWN = (0,0,1,0,0, 0,0,1,0,0, 1,0,1,0,1, 0,1,1,1,0, 0,0,1,0,0)
R_GLYPH = (1,1,1,0,0, 1,0,0,1,0, 1,1,1,0,0, 1,0,1,0,0, 1,0,0,1,0)
L_GLYPH = (1,0,0,0,0, 1,0,0,0,0, 1,0,0,0,0, 1,0,0,0,0, 1,1,1,1,0)
HEADER = ("seq,t_ms,phase,relA_deg,relB_deg,velL,velR,statusL,statusR,"
          "yaw_ddeg,accx_mg,accy_mg,accz_mg,reflC_pct,rC,gC,bC,iC,reflD_pct,rD,gD,bD,iD,reason")


def show(p):
    light_matrix.show([100 if v else 0 for v in p])


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
        pass


async def wait_tap(timeout_ms):
    show(S_GLYPH)
    print("ARMED: clear space ahead, behind and around. Tap LEFT or RIGHT.")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if tapped():
            return True
        await runloop.sleep_ms(50)
    return False


async def run():
    log = CsvLog(HEADER, prefix="caldir", now_ms=time.ticks_ms())
    t0 = time.ticks_ms()
    box = {"seq": 0, "note": ""}

    def sample(phase):
        acc = none_ok(lambda: motion_sensor.acceleration()) or (None, None, None)
        row = (box["seq"], time.ticks_diff(time.ticks_ms(), t0), phase,
               none_ok(lambda: motor.relative_position(PL)),
               none_ok(lambda: motor.relative_position(PR)),
               none_ok(lambda: motor.velocity(PL)), none_ok(lambda: motor.velocity(PR)),
               none_ok(lambda: motor.status(PL)), none_ok(lambda: motor.status(PR)),
               none_ok(lambda: motion_sensor.tilt_angles()[0]), acc[0], acc[1], acc[2],
               "", "", "", "", "", "", "", "", "", "", box["note"])
        log.append(",".join("" if v is None else str(v) for v in row))
        box["seq"] += 1
        box["note"] = ""

    def state():
        return (none_ok(lambda: motor.relative_position(PL)) or 0,
                none_ok(lambda: motor.relative_position(PR)) or 0,
                hub_drive.read_yaw() or 0)

    async def announce(glyph, name):
        show(glyph)
        print("")
        print(">>> " + name + " -- WATCH")
        for _ in range(3):
            beep(1320, 70)
            await runloop.sleep_ms(180)
        await runloop.sleep_ms(600)

    async def move(glyph, name, start_fn, ms):
        """Run one primitive for `ms`, and report the encoder and yaw deltas it produced."""
        await announce(glyph, name)
        a0, b0, y0 = state()
        box["note"] = "BEGIN_" + name
        start_fn()
        t = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t) < ms:
            sample(name)
            await runloop.sleep_ms(TICK_MS)
        hub_drive.stop()
        await runloop.sleep_ms(SETTLE_MS)
        a1, b1, y1 = state()
        dy = hub_drive.normalize_ddeg(y1 - y0)
        box["note"] = "END_%s_dA%d_dB%d_dYaw%d" % (name, a1 - a0, b1 - b0, dy)
        sample(name)
        print("    %-9s  encoderA %+5d  encoderB %+5d  yaw %+5d ddeg"
              % (name, a1 - a0, b1 - b0, dy))
        return (a1 - a0, b1 - b0, dy)

    print("=" * 66)
    print("DIRECTION CALIBRATION -- watch the robot and check each move matches its name")
    print("=" * 66)
    print("  hub_drive: FORWARD_SIGN=%d  TURN_SIGN=%d" % (hub_drive.FORWARD_SIGN, hub_drive.TURN_SIGN))

    try:
        f = await move(UP, "FORWARD", lambda: hub_drive.forward(SPEED_DPS), DRIVE_MS)
        b = await move(DOWN, "BACKWARD", lambda: hub_drive.backward(SPEED_DPS), DRIVE_MS)

        await announce(R_GLYPH, "SPIN_RIGHT")
        box["note"] = "BEGIN_SPIN_RIGHT"
        sample("SPIN_RIGHT")
        y0, y1, got_r = hub_drive.turn_by(SPIN_DDEG, SPEED_DPS, on_tick=lambda: sample("SPIN_RIGHT"))
        box["note"] = "END_SPIN_RIGHT_want%d_got%s" % (SPIN_DDEG, got_r)
        sample("SPIN_RIGHT")
        print("    SPIN_RIGHT wanted +%d ddeg, achieved %s" % (SPIN_DDEG, got_r))
        await runloop.sleep_ms(SETTLE_MS)

        await announce(L_GLYPH, "SPIN_LEFT")
        box["note"] = "BEGIN_SPIN_LEFT"
        sample("SPIN_LEFT")
        y0, y1, got_l = hub_drive.turn_by(-SPIN_DDEG, SPEED_DPS, on_tick=lambda: sample("SPIN_LEFT"))
        box["note"] = "END_SPIN_LEFT_want%d_got%s" % (-SPIN_DDEG, got_l)
        sample("SPIN_LEFT")
        print("    SPIN_LEFT  wanted -%d ddeg, achieved %s" % (SPIN_DDEG, got_l))

        print("")
        print("=" * 66)
        print("WHAT TO CHECK -- the numbers cannot tell you this, only your eyes can:")
        print("  FORWARD moved AWAY from you?      if not, flip FORWARD_SIGN in src/hub_drive.py")
        print("  SPIN_RIGHT went CLOCKWISE?        if not, flip TURN_SIGN in src/hub_drive.py")
        print("  A right spin should give a POSITIVE yaw delta. Got %s." % got_r)
        print("  A left spin should give a NEGATIVE yaw delta. Got %s." % got_l)
        print("=" * 66)
        log.append("#end fwd_dA=%d fwd_dB=%d fwd_dYaw=%d back_dA=%d back_dB=%d right=%s left=%s"
                   % (f[0], f[1], f[2], b[0], b[1], got_r, got_l))
    finally:
        hub_drive.stop()
        log.close()
        show(BOX)
        print("CALIBRATION done -> %s" % log.path)


async def main():
    if not await wait_tap(ARM_TIMEOUT_MS):
        show(BOX)
        print("NOT ARMED: no tap. FAULT.")
        return
    for s in range(COUNTDOWN_S, 0, -1):
        show(FULL if (s % 2) else BOX)
        print("COUNTDOWN %d" % s)
        await runloop.sleep_ms(1000)
    await run()


runloop.run(main())
