# demo_day.py -> program.py. DEMO DAY 2026-09-15: sweep a blue-tape square, count mines live.
# ./hub_programmer/slot_upload.py examples/demo_day.py --apply   -> hub shows "S".
#
# SETUP: put the robot INSIDE the square at a corner on the border FARTHEST from the wall, facing
# ALONG that border (parallel to the wall), sensors ~6 cm inside the tape. Tap the button on the side
# the WALL is on (LEFT or RIGHT). 3 s countdown, then it sweeps lanes parallel to the wall, shifting
# toward the wall each lane. Live count on the matrix + beep per mine. Tap LEFT/RIGHT to end and show
# the final count. CENTER kills the program.
#
# Measured rules: mine = reflection >= 30 (carpet 3-9, tape 7-9, neon yellow 55-62, pink 57-99, 2026-09-15).
# Tape = blue fraction >= 0.44 or built-in BLUE, on BOTH sensors within 150 mm (a lane end, not a graze).
# Pose: distance from wheel encoders, heading from the gyro (gyro does not slip; wheels do).
# Obstacles: wheel stall (encoders < 40% of commanded) or a heading kick > 30 deg -> back up, detour
# toward the wall, resume the lane. Lanes use ABSOLUTE headings so turn errors do not accumulate.
import time
import math
import runloop
import motor
import color_sensor
import color
from hub import light_matrix, button, motion_sensor, port
try:
    from hub_telemetry_log import CsvLog
except Exception:
    CsvLog = None

PL = port.A; PR = port.B; PC = port.C; PD = port.D     # C = RIGHT sensor, D = LEFT sensor
LEFT_FWD = -1; RIGHT_FWD = 1                            # MEASURED
MM_PER_DEG = 199.49 / 360.0                             # 63.5 mm wheel, MEASURED

SPEED_DPS = 200          # ~110 mm/s: 270 missed a pink note 2026-09-15 (one sensor, too few samples)
TURN_DPS = 90
TURN_LEAD_DDEG = 30
HOLD_K = 0.4             # dps per ddeg of heading error
HOLD_MAX = 80
# Lane change = 180 deg REVERSE pivot about the wall-side wheel -> shifts exactly one effective track
# width (95 mm, MEASURED) toward the wall. Operator 2026-09-15: the old turn/drive-150/turn moved >10 cm.
PIVOT_DPS = 180
PIVOT_CAP_MS = 9000
PIVOT_IGNORE_TAPE_DDEG = 300   # sensors may still graze the end tape for the first ~30 deg
GLARE_RETRACT_MM = 50          # a "mine" counted this close before a tape stop was shiny tape
BACKOFF_MM = 60
DETOUR_MM = 200
LANE_MAX_MM = 3300       # 10 ft + margin; arena is 8-10 ft
SWEEP_MAX_MM = 3300
RUN_LIMIT_MS = 900000
TICK_MS = 40

MINE_ON = 30; MINE_OFF = 24; MINE_CONSEC = 1   # 1 sample; OFF clears the 15-19 background of the 09-15 survey
BLUE_FRAC = 0.44; MINE_BLUE_VETO = 0.40
TAPE_WINDOW_MM = 150
DEDUPE_MM = 150          # lane pitch is 95 mm now; one note spans two lanes
SENSOR_SIDE_MM = 45      # [ASSUMED] half sensor spacing, only used to de-duplicate a mine seen twice
STALL_WINDOW_MS = 600; STALL_FRAC = 0.40
KICK_DDEG = 300

S_GLYPH = (0,1,1,1,1, 1,0,0,0,0, 0,1,1,1,0, 0,0,0,0,1, 1,1,1,1,0)


class Stop(Exception):
    pass


def ok(fn):
    try:
        return fn()
    except Exception:
        return None


def norm(d):
    return ((d + 1800) % 3600) - 1800


def show(p):
    ok(lambda: light_matrix.show([100 if v else 0 for v in p]))


def show_count(n):
    # write() may be unavailable; fall back to n lit pixels (max 25)
    try:
        light_matrix.write(str(n))
    except Exception:
        show([1 if i < n else 0 for i in range(25)])


def beep(hz, ms):
    try:
        import hub
        hub.sound.beep(hz, ms, 60)
    except Exception:
        pass


def btn():
    try:
        if button.pressed(button.LEFT) > 0:
            return "L"
        if button.pressed(button.RIGHT) > 0:
            return "R"
    except Exception:
        pass
    return None


class Robot:
    def __init__(self, wall_sign):
        self.wall = wall_sign                  # +1 wall on LEFT, -1 on RIGHT (positive yaw = left)
        self.h0 = ok(lambda: motion_sensor.tilt_angles()[0]) or 0
        self.x = 0.0; self.y = 0.0             # mm; x along lane 0, y toward the wall
        self.l_prev = motor.relative_position(PL)
        self.r_prev = motor.relative_position(PR)
        self.count = 0
        self.mines = []
        self.on = False; self.hits = 0; self.offs = 0; self.best = None
        self.t0 = time.ticks_ms()
        self.seq = 0
        self.lane = 0
        self.log = None
        if CsvLog is not None:
            self.log = ok(lambda: CsvLog("seq,t_ms,phase,lane,x,y,yaw_rel,encyaw,reflC,rC,gC,bC,reflD,rD,gD,bD,count,event",
                                         prefix="demoday", now_ms=time.ticks_ms()))
        self.enc_yaw = 0.0
        self.odo = 0.0                         # total wheel travel, mm

    def yaw(self):
        y = ok(lambda: motion_sensor.tilt_angles()[0])
        return self.h0 if y is None else y

    def rel(self):
        return norm(self.yaw() - self.h0)

    def note(self, phase, event, cc=None, cd=None, rc=None, rd=None):
        if self.log is None:
            return
        cc = cc or (None, None, None, None); cd = cd or (None, None, None, None)
        row = (self.seq, time.ticks_diff(time.ticks_ms(), self.t0), phase, self.lane, int(self.x), int(self.y),
               self.rel(), int(self.enc_yaw), rc, cc[0], cc[1], cc[2], rd, cd[0], cd[1], cd[2], self.count, event)
        ok(lambda: self.log.append(",".join("" if v is None else str(v) for v in row)))

    def guard(self):
        if time.ticks_diff(time.ticks_ms(), self.t0) > RUN_LIMIT_MS:
            raise Stop("time_limit")
        if time.ticks_diff(time.ticks_ms(), self.t0) > 2000 and btn():
            raise Stop("button")

    def odom(self):
        """Encoders give distance, gyro gives heading. Returns forward mm this tick."""
        l = ok(lambda: motor.relative_position(PL)); r = ok(lambda: motor.relative_position(PR))
        if l is None or r is None:
            return 0.0
        dl = LEFT_FWD * (l - self.l_prev) * MM_PER_DEG
        dr = RIGHT_FWD * (r - self.r_prev) * MM_PER_DEG
        self.l_prev = l; self.r_prev = r
        d = (dl + dr) / 2.0
        self.odo += (abs(dl) + abs(dr)) / 2.0
        th =self.rel() * math.pi / 1800.0
        self.x += d * math.cos(th)
        self.y += d * math.sin(th) * self.wall
        self.enc_yaw += (dr - dl) / 95.0 * 1800.0 / math.pi    # wheel-derived yaw, logged vs gyro
        return d

    def sense(self, phase):
        """Read both sensors, run the mine counter. Returns (blueC, blueD)."""
        rc = ok(lambda: color_sensor.reflection(PC)); rd = ok(lambda: color_sensor.reflection(PD))
        cc = ok(lambda: color_sensor.rgbi(PC)); cd = ok(lambda: color_sensor.rgbi(PD))
        kc = ok(lambda: color_sensor.color(PC)); kd = ok(lambda: color_sensor.color(PD))

        def bfrac(s):
            if s is None or s[0] is None:
                return 0.0
            t = s[0] + s[1] + s[2]
            return (float(s[2]) / t) if t >= 40 else 0.0

        fc = bfrac(cc); fd = bfrac(cd)
        blue_c = fc >= BLUE_FRAC or kc == color.BLUE
        blue_d = fd >= BLUE_FRAC or kd == color.BLUE
        vc = rc if (rc is not None and not blue_c and fc < MINE_BLUE_VETO) else 0
        vd = rd if (rd is not None and not blue_d and fd < MINE_BLUE_VETO) else 0
        v = max(vc, vd)
        side = -1 if vc >= vd else 1          # C = right (-1 toward left axis), D = left (+1)

        if not self.on:
            if v >= MINE_ON:
                self.hits += 1
                if self.hits >= MINE_CONSEC:
                    self.on = True; self.offs = 0
                    self.found(side, phase, cc, cd, rc, rd)
            else:
                self.hits = 0
        else:
            if v < MINE_OFF:
                self.offs += 1
                if self.offs >= 2:
                    self.on = False; self.hits = 0
            else:
                self.offs = 0
        self.seq += 1
        if self.seq % 4 == 0:
            self.note(phase, "", cc, cd, rc, rd)
        return blue_c, blue_d

    def found(self, side, phase, cc, cd, rc, rd):
        th = self.rel() * math.pi / 1800.0
        # Sensors sit AHEAD of the axle and fire at a note's LEADING edge: move the fix toward the note centre,
        # or one note seen from two adjacent opposite-direction lanes lands ~170 mm apart and counts twice.
        fwd = 85.0                                   # [ASSUMED] ~60 mm sensor-ahead + ~25 mm edge-to-centre
        mx = self.x + math.cos(th) * fwd - math.sin(th) * SENSOR_SIDE_MM * side
        my = self.y + (math.sin(th) * fwd + math.cos(th) * SENSOR_SIDE_MM * side) * self.wall
        for (px, py, _o) in self.mines:
            if (px - mx) ** 2 + (py - my) ** 2 < DEDUPE_MM ** 2:
                self.note(phase, "DUP_MINE", cc, cd, rc, rd)
                return
        self.mines.append((mx, my, self.odo))
        self.count += 1
        show_count(self.count)
        beep(1320, 150)
        self.note(phase, "MINE %d at %d,%d" % (self.count, int(mx), int(my)), cc, cd, rc, rd)
        print("MINE %d at x=%d y=%d" % (self.count, int(mx), int(my)))

    def run(self, left, right):
        motor.run(PL, int(LEFT_FWD * left)); motor.run(PR, int(RIGHT_FWD * right))

    def stop(self):
        ok(lambda: motor.stop(PL)); ok(lambda: motor.stop(PR))

    async def turn_to(self, target_rel):
        """Gyro-closed spin to an ABSOLUTE heading. Guarded: if the error GROWS, the spin is backwards."""
        pol = 1
        for attempt in range(3):
            err = norm(target_rel - self.rel())
            if abs(err) <= TURN_LEAD_DDEG + 15:
                break
            best = abs(err); t = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t) < 6000:
                self.guard()
                err = norm(target_rel - self.rel())
                if abs(err) <= TURN_LEAD_DDEG:
                    break
                s = TURN_DPS if abs(err) > 200 else 60
                if err * pol > 0:
                    self.run(-s, s)            # spin LEFT (yaw increases)
                else:
                    self.run(s, -s)            # spin RIGHT
                if abs(err) > best + 150:
                    pol = -pol; best = abs(err)
                best = min(best, abs(err))
                self.odom(); self.sense("turn")
                await runloop.sleep_ms(TICK_MS)
            self.stop()
            await runloop.sleep_ms(200)
            self.odom()
        self.note("turn", "TURN_DONE target=%d got=%d" % (target_rel, self.rel()))

    async def straight(self, heading, max_mm, phase, stop_on_y=None, reverse=False):
        """Drive on a gyro-held ABSOLUTE heading. Returns 'TAPE', 'STALL', 'KICK', 'DIST', 'Y'."""
        dist = 0.0; seen_c = None; seen_d = None
        win_t = time.ticks_ms(); win_d = 0.0
        sgn = -1 if reverse else 1
        while True:
            self.guard()
            err = norm(heading - self.rel())
            if abs(err) > KICK_DDEG:
                self.stop()
                return "KICK"
            s = max(-HOLD_MAX, min(HOLD_MAX, HOLD_K * err))
            if reverse:
                self.run(-(SPEED_DPS * 0.6) - s, -(SPEED_DPS * 0.6) + s)   # turn rate = vR - vL in reverse too
            else:
                self.run(SPEED_DPS - s, SPEED_DPS + s)
            d = self.odom()
            dist += abs(d); win_d += abs(d)
            if not reverse:
                bc, bd = self.sense(phase)
                if bc:
                    seen_c = dist
                if bd:
                    seen_d = dist
                if seen_c is not None and seen_d is not None and abs(seen_c - seen_d) <= TAPE_WINDOW_MM \
                        and dist - max(seen_c, seen_d) < TAPE_WINDOW_MM:
                    self.stop()
                    self.retract_glare()
                    return "TAPE"
            if dist >= max_mm:
                self.stop()
                return "DIST"
            if stop_on_y is not None and self.y >= stop_on_y:
                self.stop()
                return "Y"
            if time.ticks_diff(time.ticks_ms(), win_t) >= STALL_WINDOW_MS:
                expect = abs(SPEED_DPS * (0.6 if reverse else 1.0)) * MM_PER_DEG * \
                    time.ticks_diff(time.ticks_ms(), win_t) / 1000.0
                if win_d < STALL_FRAC * expect and dist > 30:
                    self.stop()
                    return "STALL"
                win_t = time.ticks_ms(); win_d = 0.0
            await runloop.sleep_ms(TICK_MS)
        _ = sgn

    def retract_glare(self):
        """Shiny tape can saturate and read bright-not-blue. A count right before the tape stop was it."""
        while self.mines and self.mines[-1][2] >= self.odo - GLARE_RETRACT_MM:
            self.mines.pop()
            self.count -= 1
            show_count(self.count)
            self.note("lane", "RETRACT_GLARE count=%d" % self.count)

    async def pivot_uturn(self, new_heading):
        """180 deg REVERSE pivot about the WALL-SIDE wheel (held at 0 dps). Shifts one track width toward
        the wall and swings the body back, away from the tape. Returns 'OK', 'TAPE' (both sensors saw
        tape mid-pivot = wall-side border) or 'STALL' (blocked, e.g. the wall)."""
        side = self.wall * (1 if self.lane % 2 == 0 else -1)   # +1 = wall on the robot's LEFT now
        seen_c = False; seen_d = False
        turned = 0; last = self.rel(); t = time.ticks_ms(); why = "OK"
        try:
            while True:
                self.guard()
                now = self.rel()
                turned += abs(norm(now - last)); last = now
                err = norm(new_heading - now)
                if turned > 900 and abs(err) <= TURN_LEAD_DDEG:
                    break
                if time.ticks_diff(time.ticks_ms(), t) > PIVOT_CAP_MS:
                    why = "STALL"
                    break
                if time.ticks_diff(time.ticks_ms(), t) > 2500 and turned < 150:
                    why = "STALL"
                    break
                v = PIVOT_DPS if abs(err) > 250 else 90
                if side > 0:
                    self.run(0, -v)            # hold LEFT wheel, RIGHT wheel backs round it
                else:
                    self.run(-v, 0)            # hold RIGHT wheel, LEFT wheel backs round it
                self.odom()
                bc, bd = self.sense("pivot")
                if turned > PIVOT_IGNORE_TAPE_DDEG:
                    seen_c = seen_c or bc
                    seen_d = seen_d or bd
                    if seen_c and seen_d:
                        why = "TAPE"
                        break
                await runloop.sleep_ms(TICK_MS)
        finally:
            self.stop()
        await runloop.sleep_ms(200)
        self.odom()
        self.note("pivot", "PIVOT_END %s turned=%d err=%d" % (why, turned, norm(new_heading - self.rel())))
        return why

    async def backoff(self, heading):
        await self.straight(heading, BACKOFF_MM, "backoff", reverse=True)

    async def sweep(self):
        toward_wall = 900 * self.wall
        while self.y < SWEEP_MAX_MM:
            heading = 0 if self.lane % 2 == 0 else 1800
            detours = 0; lane_mm_start = self.x
            show_count(self.count)
            while True:
                # Cap the lane at 150 mm past where this END's tape stopped the robot last time, so a missed
                # tape (shiny tape, slow tick) costs ~150 mm, not a 3.3 m trip out of the square.
                if heading == 0:
                    xf = getattr(self, "x_far", None)
                    cap = LANE_MAX_MM if xf is None else max(50.0, xf + 150.0 - self.x)
                else:
                    cap = max(50.0, self.x - (getattr(self, "x_near", 0.0) - 150.0))
                why = await self.straight(heading, cap, "lane")
                self.note("lane", "LANE_END " + why)
                if why == "TAPE":
                    if heading == 0:
                        self.x_far = self.x
                    else:
                        self.x_near = self.x
                    break
                if why == "DIST":
                    break
                if why == "KICK":                       # knocked off heading by an obstacle: realign
                    await self.backoff(self.rel())
                    await self.turn_to(heading)
                    detours += 1
                    if detours > 6:
                        break
                    continue
                # STALL: obstacle. Back up, sidestep toward the wall, resume the lane.
                detours += 1
                if detours > 4:
                    break
                await self.backoff(heading)
                await self.turn_to(norm(toward_wall))
                why2 = await self.straight(norm(toward_wall), DETOUR_MM, "detour")
                if why2 == "TAPE":
                    self.note("detour", "SWEEP_DONE wall tape during detour")
                    return "COMPLETE"
                await self.turn_to(heading)
            _ = lane_mm_start
            await self.backoff(heading)
            # next lane: one reverse pivot about the wall-side wheel (95 mm shift)
            nxt = 0 if (self.lane + 1) % 2 == 0 else 1800
            why = await self.pivot_uturn(nxt)
            if why == "STALL" and self.y < 2000 and not getattr(self, "pstall", False):
                # Pivot blocked mid-arena (obstacle): not the wall. Take the next lane from here instead of
                # ending the demo. A 2nd stall in a row still ends it.
                self.pstall = True
                self.note("pivot", "PIVOT_STALL_MIDARENA continue")
            elif why in ("TAPE", "STALL"):
                return "COMPLETE"
            else:
                self.pstall = False
            self.lane += 1
            await self.turn_to(nxt)                     # trims any residual error only
        return "COMPLETE"


async def main():
    show(S_GLYPH)
    print("DEMO_DAY armed: tap the button on the WALL side")
    wall = None
    while wall is None:
        b = btn()
        if b == "L":
            wall = 1
        elif b == "R":
            wall = -1
        await runloop.sleep_ms(50)
    for n in (3, 2, 1):
        ok(lambda: light_matrix.write(str(n)))
        beep(660, 80)
        await runloop.sleep_ms(1000)
    bot = Robot(wall)
    show_count(0)
    beep(990, 200)
    reason = "?"
    try:
        reason = await bot.sweep()
    except Stop as e:
        reason = e.args[0]
    except Exception as e:
        reason = "ERROR " + repr(e)
        beep(220, 600)
    finally:
        bot.stop()
    bot.note("end", "END %s mines=%d lanes=%d x=%d y=%d" % (reason, bot.count, bot.lane, int(bot.x), int(bot.y)))
    if bot.log is not None:
        ok(lambda: bot.log.close())
    print("DEMO_DAY END %s mines=%d lanes=%d" % (reason, bot.count, bot.lane))
    for _ in range(bot.count):
        beep(1320, 120)
        await runloop.sleep_ms(250)
    while True:                                          # hold the final count until CENTER
        show_count(bot.count)
        await runloop.sleep_ms(3000)


runloop.run(main())
