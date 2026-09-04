"""main.py -- the competition program, as the IRREDUCIBLE-CORE switchboard.

Wires the pure modules and the hub_* wrappers into the run machine of record at its SMALLEST:

    ARMED -> (tap) -> CALIBRATE_FLOOR -> READY -> (tap + countdown) -> SWEEP -> REPORT

with CALIBRATION_FAILED and ABORT as the two honest exits. Every OPTIONAL feature (target colour,
classification, boundary stop, live telemetry) is a knob-toggled bolt-on that only ADDS to this
skeleton -- docs/plans/minimalism-contract-2026-09-03.md. A professor answer moves a config VALUE or
disables a stage; it never moves a box.

DEFAULT front-end is DETECT_MODE="anomaly": floor_anomaly learns the floor at run start and flags
anything unlike it -- no target sample, no known colour, robust to the floor changing on the day. It
feeds detector.EdgeCounter, which counts on the falling edge, so mines added/removed mid-run are
handled by construction: completion is COVERAGE, never a tally.

LAYER BOUNDARY (ADR-0004): only hub_*.py touch the LEGO API. This file calls them and stays otherwise
pure, so it IMPORTS on the host (check-docs) and only its hub call sites are [UNVERIFIED]. The motion
primitives are grounded in the PROVEN 1 ft square (examples/motor_poc.py, MEASURED 2026-09-03):
straight = drive until the encoders advance; turn = spin until the GYRO reads the angle. Those ran.

Runs as program.py in a slot, started from the hub; it auto-starts into ARMED with the motors HELD, so
it never calibrates on the bench. STOP is a LEFT/RIGHT press (CENTER is the firmware's hard stop).
MicroPython subset: no f-strings.
"""
import time

import config
import odometry
import sweep
import floor_anomaly
import detector
import result
import hub_runtime                       # wraps the hub-only `runloop` (ADR-0004 purity boundary)
import hub_ui
import hub_motors
import hub_imu
import hub_color

try:
    from hub_telemetry_log import CsvLog
except ImportError:
    CsvLog = None

TICK_MS = 100                            # ~10 Hz, the rate MEASURED achievable on the square run


def _now():
    return time.ticks_ms()


def _since(t0):
    return time.ticks_diff(time.ticks_ms(), t0)


async def _sleep(ms):
    await hub_runtime.sleep_ms(ms)


def _tapped():
    """A LEFT or RIGHT press -- the operator's tap and the soft-abort. CENTER is the firmware stop."""
    return hub_ui.button_pressed("left") is True or hub_ui.button_pressed("right") is True


def _traverse_pct():
    """TRAVERSE_SPEED_MMS expressed as a drive percent, clamped so it neither crawl-stalls nor runs
    the bench maximum on the floor. hub_motors.drive() maps percent -> deg/s with the measured ceiling."""
    dps = odometry.mm_to_degrees(config.TRAVERSE_SPEED_MMS)
    pct = 100.0 * dps / hub_motors.DRIVE_MAX_DPS
    return max(12.0, min(60.0, pct))


class RunContext(object):
    """Everything the tick needs: the result, the odometry, the detector, and the run clock."""

    def __init__(self, mission, timebox_ms):
        self.mission = mission
        self.timebox_ms = timebox_ms
        self.t_start = _now()
        self.odo = odometry.Odometry()
        self.floor_model = None
        self.counter = None
        self.abort = False
        self.hit_timebox = False
        self.tick_hz = 0.0
        self.evlog = None
        self.seq = 0

    def elapsed_ms(self):
        return _since(self.t_start)

    def timed_out(self):
        if self.elapsed_ms() >= self.timebox_ms:
            self.hit_timebox = True
            return True
        return False

    def _odo_tick(self):
        enc = hub_motors.read_motor_degrees()
        if enc is not None:
            self.odo.update(enc[0], enc[1], hub_imu.read_yaw_deg())

    def _detect_tick(self):
        # DETECT_MODE="anomaly": distance-from-floor scalar -> the same EdgeCounter a target run uses.
        if self.counter is None or self.floor_model is None:
            return
        sample = hub_color.read_rgb()
        if sample is None:
            self.mission.none_samples += 1
            return
        d = self.floor_model.deviation(sample)
        if d is None:
            self.mission.none_samples += 1
            return
        event = self.counter.update(d)
        if event is not None:
            if event.accepted:
                self.mission.add_detection(color=None)   # anomaly = presence; colour is UNKNOWN
                hub_ui.beep(880, 80)                      # one beep per counted mine: the Builder's tally
                self._log("MINE")
            else:
                self.mission.add_rejected()

    def _log(self, kind):
        if self.evlog is None:
            return
        p = self.odo.pose
        try:
            self.evlog.append("%d,%d,%.0f,%.0f,%.1f,%s"
                              % (self.seq, self.elapsed_ms(), p.x_mm, p.y_mm, p.heading_deg, kind))
        except Exception:
            pass
        self.seq += 1

    def motion_tick(self, detect):
        """One control tick: odometry always, detection when a lane is active, then poll the abort.
        Returns True if an abort was requested."""
        self._odo_tick()
        if detect:
            self._detect_tick()
        if _tapped():
            self.abort = True
        return self.abort


# --- motion primitives (grounded in examples/motor_poc.py; [UNVERIFIED] hub call sites) -------------

async def drive_distance_mm(mm, ctx, detect):
    """Drive forward until the mean encoder advance reaches `mm`, running the detector each tick when
    `detect`. Bounded by the encoders and the timebox; motors always stopped in the finally."""
    enc0 = hub_motors.read_motor_degrees()
    if enc0 is None:
        return False
    target_deg = odometry.mm_to_degrees(abs(mm))
    speed = _traverse_pct()
    reached = False
    hub_motors.drive(speed, speed)
    try:
        while True:
            enc = hub_motors.read_motor_degrees()
            if enc is not None:
                advanced = (abs(enc[0] - enc0[0]) + abs(enc[1] - enc0[1])) / 2.0
                if advanced >= target_deg:
                    reached = True
                    break
            if ctx.motion_tick(detect):
                break
            if ctx.timed_out():
                break
            await _sleep(TICK_MS)
    finally:
        hub_motors.stop_motors()
        ctx.motion_tick(detect)          # capture the segment's true end
    return reached                       # True only if the FULL distance was driven (not cut short)


async def turn_degrees(deg, ctx):
    """Spin in place until the GYRO heading changes by |deg| (deg>0 = right). Gyro-closed, so it does
    NOT depend on TRACK_WIDTH_MM -- the same trick the square run proved. Detector off during a turn."""
    y0 = hub_imu.read_yaw_deg()
    if y0 is None:
        return
    speed = _traverse_pct()
    left, right = (speed, -speed) if deg > 0 else (-speed, speed)   # opposite wheels = spin
    hub_motors.drive(left, right)
    try:
        while True:
            y = hub_imu.read_yaw_deg()
            if y is not None and abs(odometry.normalize_angle(y - y0)) >= abs(deg):
                break
            if ctx.motion_tick(False):
                break
            if ctx.timed_out():
                break
            await _sleep(TICK_MS)
    finally:
        hub_motors.stop_motors()


# --- states -----------------------------------------------------------------------------------------

async def wait_for_tap(ctx, timeout_ms):
    """Poll for a LEFT/RIGHT tap. Returns True on tap, False on timeout (a fault / no operator)."""
    t0 = _now()
    while _since(t0) < timeout_ms:
        if _tapped():
            return True
        await _sleep(50)
    return False


async def wait_release(timeout_ms=2000):
    """Wait for the operator to LET GO of LEFT/RIGHT, so one press cannot both start a stage and be
    re-read as the next stage's abort (there is no tap-vs-hold discrimination -- contract sec.4.6)."""
    t0 = _now()
    while _tapped() and _since(t0) < timeout_ms:
        await _sleep(30)


async def calibrate_floor(ctx):
    """Creep forward sampling the floor, then build the anomaly model and derive its thresholds.
    Returns True on success; False is a CORRECT outcome when the floor is too noisy/busy to model."""
    if config.DETECT_MODE != "anomaly":
        # BOLT-ON: the "target" front-end (calibration.py + CALIBRATE_TARGET) is not in the core build.
        return False
    samples = []
    speed = _traverse_pct()
    hub_motors.drive(speed, speed)
    t0 = _now()
    ticks = 0
    try:
        while _since(t0) < config.CALIBRATION_FLOOR_MS:
            s = hub_color.read_rgb()
            if s is not None:
                samples.append(s)
            ticks += 1
            await _sleep(TICK_MS)
    finally:
        hub_motors.stop_motors()
    dt = _since(t0) / 1000.0
    ctx.tick_hz = (ticks / dt) if dt > 0 else 0.0
    try:
        model = floor_anomaly.build_floor_model(samples)
        cal = floor_anomaly.derive_thresholds(model, samples)
        # DERIVE: turn the MEASURED tick rate into detector width gates, so a too-wide plateau (a floor
        # seam, or two merged notes) is REJECTED rather than counted as one mine. A rate too low to
        # resolve the target raises -> CALIBRATION_FAILED, the honest outcome (config.event_width_gates).
        lo, hi = config.event_width_gates(ctx.tick_hz, config.TRAVERSE_SPEED_MMS, config.TARGET_SIZE_MM)
    except Exception:                    # CalibrationError / no samples / rate too low -> refuse to arm
        return False
    ctx.floor_model = model
    ctx.counter = detector.EdgeCounter(cal, min_width=lo, max_width=hi)
    return True


async def countdown(ctx):
    """The 10 s 'clear the arena' window, cancellable by a tap. Returns False if aborted."""
    for s in range(config.COUNTDOWN_S, 0, -1):
        hub_ui.show_digit(s) if s <= 9 else hub_ui.show_glyph("block")
        hub_ui.beep(1000, 60)
        for _ in range(10):
            if _tapped():
                return False
            await _sleep(100)
    return True


async def do_sweep(ctx):
    """Drive the boustrophedon plan, counting on each falling edge, until COMPLETE / TIMEBOX / ABORT."""
    plan = sweep.SweepPlan()
    ctx.mission.lanes_planned = plan.total_lanes
    hub_imu.reset_yaw()                  # zero the heading so the logged pose is in the arena frame
    hub_ui.show_glyph("arrow")
    while not plan.is_done():
        if ctx.timed_out():
            plan.stop_after_current_lane()
        cmd = plan.next_command()
        if cmd.kind == sweep.CMD_STOP:
            break
        if cmd.kind == sweep.CMD_DRIVE:
            reached = await drive_distance_mm(cmd.value, ctx, cmd.detect)
            if cmd.detect and reached:                 # count only a lane actually finished
                ctx.mission.lanes_completed += 1
        elif cmd.kind == sweep.CMD_TURN:
            await turn_degrees(cmd.value, ctx)
        # CMD_RESQUARE is a no-op under BOUNDARY_MODE="odometry" (the core has no boundary reference).
        if ctx.abort:
            return "ABORTED"
    # Every planned lane swept => COMPLETE even if the clock ran out on the final step; lanes left
    # unswept because the timebox cut in => TIMEBOX.
    if plan.lanes_remaining() == 0:
        return "COMPLETE"
    return "TIMEBOX" if ctx.hit_timebox else "COMPLETE"


async def show_number(n):
    for ch in str(int(max(0, n))):
        hub_ui.show_digit(int(ch))
        await _sleep(500)
        hub_ui.show_glyph("blank")
        await _sleep(150)


async def do_report(mission):
    """Motors already stopped. Cycle the result pages forever; the operator stops the program (FR-5)."""
    hub_motors.stop_motors()
    while True:
        for glyph, number in mission.display_pages():
            hub_ui.show_glyph(glyph)
            await _sleep(config.REPORT_PAGE_DWELL_MS)
            await show_number(number)


async def hold(glyph):
    """Terminal hold on a glyph (CALIBRATION_FAILED / not-armed). The operator stops the program."""
    while True:
        hub_ui.show_glyph(glyph)
        await _sleep(500)


def _status_const(name):
    return {"COMPLETE": result.STATUS_COMPLETE,
            "TIMEBOX": result.STATUS_TIMEBOX,
            "ABORTED": result.STATUS_ABORTED}.get(name, result.STATUS_UNKNOWN)


def _open_event_log(ctx):
    if CsvLog is None or not getattr(config, "LOG_EVENTS", True):
        return
    try:
        ctx.evlog = CsvLog("seq,t_ms,x_mm,y_mm,heading_deg,event", prefix="mission", now_ms=_now())
    except Exception:
        ctx.evlog = None


async def main():
    hub_ui.tone_rising()
    mission = result.MissionResult()
    ctx = RunContext(mission, int(config.RUN_TIMEBOX_S * 1000))
    reached_report = False
    try:
        # ARMED -- motors HELD, wait for the operator's tap ON THE ARENA. Never calibrate on the bench.
        hub_motors.stop_motors()
        hub_ui.show_glyph("s")
        if not await wait_for_tap(ctx, 120000):
            hub_ui.tone_falling()
            await hold("x")                                  # no operator -> fault, hold
            return
        # CALIBRATE_FLOOR (SELFCHECK + DERIVE collapse into this step)
        hub_ui.show_glyph("dot")
        if not await calibrate_floor(ctx):
            hub_ui.tone_falling()
            mission.set_status(result.STATUS_UNKNOWN, "calibration_failed")
            await hold("x")                                  # refusing to arm is a CORRECT outcome
            return
        _open_event_log(ctx)
        # READY -- the only state that accepts a start.
        hub_ui.show_glyph("border")
        if not await wait_for_tap(ctx, 300000):
            mission.set_status(result.STATUS_ABORTED, "no_start")
        else:
            await wait_release()         # so the start press is not re-read as a countdown abort
            if not await countdown(ctx):
                mission.set_status(result.STATUS_ABORTED, "abort_in_countdown")
            else:
                status = await do_sweep(ctx)
                mission.set_status(_status_const(status), status)
                reached_report = True
    finally:
        hub_motors.stop_motors()
        if ctx.evlog is not None:
            try:
                ctx.evlog.close()
            except Exception:
                pass
    mission.duration_s = ctx.elapsed_ms() / 1000.0
    if reached_report or mission.status != result.STATUS_UNKNOWN:
        await do_report(mission)


if __name__ == "__main__":
    hub_runtime.run(main())
