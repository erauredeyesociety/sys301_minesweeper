"""Every tunable in one place.

Nothing here is a measurement. These are STARTING POINTS chosen so the code runs; each one is
marked with how it must be replaced. Calibration overrides the detection values at run start
(scope TR-4), and the arena values are unknown until the professor answers Q1
(docs/plans/questions-for-the-professor.md).
"""

# --- Arena -------------------------------------------------------------------
# UNKNOWN: "a 10x10 area" has no units. See docs/findings/coverage-time-budget.md --
# at 10 feet an exhaustive single-sensor sweep is 125-204 m of driving.
ARENA_WIDTH_MM = 1000.0        # [ASSUMED] placeholder. MUST come from professor Q1.
ARENA_LENGTH_MM = 1000.0       # [ASSUMED] placeholder. MUST come from professor Q1.

# BOUNDARY_MODE selects what ends a lane: "odometry" (dead reckoning only), "distance"
# (ultrasonic sees the wall), or "wall" (drive until stalled). Only "odometry" needs no
# hardware we do not own.
BOUNDARY_MODE = "odometry"     # [ASSUMED] the spec's default; professor Q3 settles it.
BOUNDARY_MARGIN_MM = 100.0     # [ASSUMED] how far outside the arena the pose may drift before
                               # degraded mode B1 ends the lane. Q3 plus a measured
                               # CROSS_TRACK_ERROR_MM settle it; too tight and healthy odometry
                               # noise ends every lane early.

# --- Run budget --------------------------------------------------------------
RUN_TIMEBOX_S = 300.0          # [ASSUMED] placeholder. MUST come from professor Q2 (how long
                               # the demo slot actually gives us).

# --- Target ------------------------------------------------------------------
TARGET_SIZE_MM = 76.0          # [ASSUMED] standard 3in sticky note; MEASURE the real pack.
# One entry per colour the run must tell apart. Length 1 is presence-only: no RGB buffer, no
# classification, a higher speed ceiling. Professor Q5 (are there decoy colours?) settles it.
CLASSES = ("target",)          # [ASSUMED] narrowest defensible reading of the briefing.

# --- Sweep geometry ----------------------------------------------------------
# Lane pitch must stay under the target size minus twice the cross-track error, or a note
# can fall between two lanes. CROSS_TRACK_ERROR_MM must be MEASURED (UMBmark square-path run).
CROSS_TRACK_ERROR_MM = 15.0    # [ASSUMED] optimistic. Measure before trusting.
LANE_OVERLAP_MM = 5.0          # deliberate safety margin on top of the error allowance

# --- Detection ---------------------------------------------------------------
# Thresholds are DERIVED AT RUN START by calibration.py, never hard-coded (scope TR-4).
# These only bound what calibration is allowed to produce.
# Minimum contrast-to-floor-noise ratio, in MAD units. The research rule is contrast >= 6*SD
# (detection-and-sweep-techniques.md); MAD ~ 0.6745*SD for Gaussian noise, so 6 SD = 8.90 MAD.
# This is the STRUCTURAL gate -- MIN_CONTRAST and MAX_FLOOR_MAD are absolute proxies for it and
# a hand-edit of either breaks their pairing silently. Do not lower without re-reading that rule.
MIN_SNR_MAD = 8.90
MIN_CONTRAST = 12.0            # reflectance points. Below this, calibration FAILS LOUD.
# TOTAL gap between the on and off thresholds, as a fraction of contrast -- calibrate() splits it
# half above and half below the midpoint. WATCH THE SEMANTICS: the 0.25 in
# docs/research/detection-and-sweep-techniques.md section 1 is a HALF-width (its "band" is both
# added to and subtracted from the midpoint), so that source's figure is 0.5 in THIS name. Ours is
# deliberately half of it, which is the narrower, flicker-prone side -- too small and one note is
# counted twice. Do not "sync" it to 0.25 from that document without widening it.
HYSTERESIS_FRACTION = 0.25     # [ASSUMED] settled by replaying recorded runs
MIN_DWELL_SAMPLES = 2          # consecutive samples needed to accept a state change
CALIBRATION_SAMPLES = 20       # per surface, per placement
CALIBRATION_PLACEMENTS = 3     # sample the floor in 3 spots, not 1
# A floor whose own reading wanders invalidates every threshold derived from it, so the floor
# burst is gated on its own spread before contrast is ever considered.
# SET THIS AND MIN_CONTRAST AS A PAIR. The arming rule established in
# docs/research/detection-and-sweep-techniques.md section 1 is contrast >= 6 * floor_sd. We measure
# spread as MAD, not sd; for Gaussian noise MAD ~= 0.6745 sd, so the same rule in MAD units is
# contrast >= 8.9 * floor_MAD (docs/plans/analysis-detection-quality.md line 219). Hence
# MAX_FLOOR_MAD = MIN_CONTRAST / 8.9. Raising one without the other arms a run our own research
# says to refuse: at MIN_CONTRAST 12.0 a floor MAD of 3.0 is only 2.7 sd of separation, and the
# phantom counts get read aloud to the instructor.
MAX_FLOOR_MAD = 1.35           # [ASSUMED] reflectance points, = MIN_CONTRAST / 8.9. BM-0(a)
                               # measures the real floor spread on classroom carpet; too tight and
                               # we never arm, but refusing to arm is a correct outcome (CONOPS
                               # OS-5) and a phantom count is not.
CALIBRATION_FLOOR_MS = 3000    # [ASSUMED] how long the floor burst drives. Long enough that the
                               # measured tick rate is not noise; settled by the first hub session.
CALIBRATION_PROMPT_TIMEOUT_S = 30.0  # [ASSUMED] operator preference. Without it the robot waits
                               # forever with motors live for a target that may never arrive.

# --- Event width gate --------------------------------------------------------
# A real note produces an event of a plausible width. Too narrow is noise; too wide is a
# seam, a shadow, or two notes merged. Widths are in SAMPLES, so they depend on sample rate
# and traverse speed -- recompute with expected_width_samples() rather than guessing.
MIN_EVENT_SAMPLES = 2
MAX_EVENT_SAMPLES = 400        # generous; tighten once the real sample rate is measured
# The two fractions event_width_gates() scales the expected full-chord width by. A crossing that
# clips the edge of a note is short but real; one much wider than a note is a seam or a shadow.
EDGE_CHORD_FRACTION = 0.25     # [ASSUMED] the shortest fraction of a full chord that still counts.
                               # Settled by replaying recorded runs; too high and every note the
                               # lane only grazes is rejected as too_narrow.
WIDTH_GATE_SLACK = 2.0         # [ASSUMED] how much wider than a full chord an event may be.
                               # Absorbs tick-rate and speed error; settled by the same replay.

# --- Drivetrain geometry -----------------------------------------------------
# NONE of these are measured. They are the constants everything else scales by, which is exactly
# why they live here and are passed as arguments elsewhere -- measuring them changes a number,
# never a line of code. We own a hodge-podge of parts and several wheel sizes, so do not treat any
# of this as settled until scripts/measure-drivetrain runs on the real robot.
WHEEL_DIAMETER_MM = 56.0       # [ASSUMED] LEGO Ø56 (base set). We may be running Ø24 or Ø88.
                               # MEASURE the EFFECTIVE rolling diameter under load, not the moulded
                               # number -- they differ, and the difference is surface-dependent.
TRACK_WIDTH_MM = 176.0         # [ASSUMED] placeholder. Distance between the wheel contact patches.
                               # Derive it from a spin-turn test, not a ruler: the effective value
                               # is what makes a commanded 360 deg turn actually close.
ENCODER_COUNTS_PER_REV = 360.0 # LEGO fact sheets, all three motor types. The one figure here that
                               # is a spec rather than a guess.

# --- Motion ------------------------------------------------------------------
# UNVERIFIED: classification needs several pure samples inside a note, which caps speed
# (~160 mm/s at a 20 mm chord vs ~360 mm/s at 30 mm) -- docs/research/color-discrimination.md.
# Presence-only detection tolerates more. Start slow; speed is an optimisation, not a default.
TRAVERSE_SPEED_MMS = 150.0     # [ASSUMED] starting point
SAMPLE_RATE_HZ = 100.0         # UNVERIFIED as a LOOP rate -- it is the LEGO spec figure for the
                               # colour sensor DEVICE. Value unchanged 2026-08-27.
                               # What the 2026-08-27 hub session added: a full IMU tick (tilt +
                               # accel + gyro read together) costs 1.350 ms MEASURED over 300
                               # iterations, i.e. 14% of a 10 ms budget. So 100 Hz is plausible
                               # FROM THE IMU SIDE ALONE. It says nothing about the cost of
                               # driving, detecting or logging, and it is NOT a measured loop
                               # rate -- KU-M5 stays OPEN.
                               # docs/findings/imu-characterisation-2026-08-27.md
TURN_RATE_DPS = 90.0           # [ASSUMED] degrees per second in a spin turn. Only used to say how
                               # long a turn should take; BM-4 / BM-7 measure it.

# --- Degraded modes ----------------------------------------------------------
# Thresholds for the responses in docs/plans/mission-algorithm.md section "Degraded modes".
MAX_CONSECUTIVE_NONE = 10      # [ASSUMED] unreadable ticks in a row before the run faults.
                               # First hub session settles it: too low and one dropped read kills
                               # a healthy run, too high and the robot sweeps blind for seconds.
HEADING_DISAGREE_LIMIT_DEG = 10.0  # [ASSUMED] gyro-vs-encoder gap that marks the run DEGRADED.
                               # BM-9 plus one lane run settles it; too low and the flag stops
                               # meaning anything.
STUCK_YAW_TICKS = 50           # [ASSUMED] ticks of unchanged yaw while the encoders show a turn
                               # before falling back to encoder heading. Expressed at
                               # SAMPLE_RATE_HZ, so it is 0.5 s -- rescale it by the rate measured
                               # at run start rather than trusting the tick count.
                               # CAVEAT added 2026-08-27, MEASURED: angular_velocity() reads
                               # exactly 0,0,0 on a stationary hub, which suggests a deadband or
                               # filtering (unverified as an explanation). If tilt_angles() yaw is
                               # filtered the same way, a SLOW turn could hold yaw constant for
                               # many ticks and make a HEALTHY gyro look stuck. Do not lower this
                               # number until a slow turn has been watched on the bench.

# --- Reporting ---------------------------------------------------------------
REPORT_PAGE_DWELL_MS = 1200    # [ASSUMED] how long one matrix frame is held. Settled by eye on a
                               # real hub (Stage 1): short enough to cycle, long enough to read.
BEEP_MS = 150                  # [ASSUMED] length of one beep. Same Stage 1 eyeball/ear test.


def lane_pitch_mm():
    """Widest lane spacing that still guarantees a target cannot slip between lanes."""
    pitch = TARGET_SIZE_MM - 2.0 * CROSS_TRACK_ERROR_MM - LANE_OVERLAP_MM
    if pitch <= 0.0:
        raise ValueError(
            "cross-track error too large for target size: no lane pitch can guarantee coverage")
    return pitch


def lane_count(width_mm=None):
    """How many lanes are needed to cover the arena width."""
    if width_mm is None:
        width_mm = ARENA_WIDTH_MM
    pitch = lane_pitch_mm()
    n = int(width_mm / pitch)
    if n * pitch < width_mm:
        n += 1
    return n


def sweep_path_mm(width_mm=None, length_mm=None):
    """Total driving distance for an exhaustive sweep, excluding turns."""
    if width_mm is None:
        width_mm = ARENA_WIDTH_MM
    if length_mm is None:
        length_mm = ARENA_LENGTH_MM
    return lane_count(width_mm) * length_mm


def expected_width_samples(chord_mm=None, speed_mms=None, rate_hz=None):
    """How many samples the sensor takes while crossing a target of the given chord.

    speed_mms and rate_hz default to the module constants, which are both guesses. Pass the
    MEASURED values when they exist -- the tick rate is measured at every run start.
    """
    if chord_mm is None:
        chord_mm = TARGET_SIZE_MM
    if speed_mms is None:
        speed_mms = TRAVERSE_SPEED_MMS
    if rate_hz is None:
        rate_hz = SAMPLE_RATE_HZ
    if speed_mms <= 0.0:
        raise ValueError("traverse speed must be positive, got {0}".format(speed_mms))
    if rate_hz <= 0.0:
        raise ValueError("sample rate must be positive, got {0}".format(rate_hz))
    return (chord_mm / speed_mms) * rate_hz


def event_width_gates(rate_hz, speed_mms, chord_mm):
    """Detector width gates, in samples, from the rate the loop ACTUALLY achieved.

    Called at DERIVE with the rate counted during the floor burst. This is the whole point of
    measuring that rate: MIN_EVENT_SAMPLES and MAX_EVENT_SAMPLES are unmeasured guesses, and a
    gate built from a rate that is too high rejects every real target as too_narrow -- the robot
    drives over a mine, sees it, and does not count it, with nothing on the matrix to say so.
    """
    full = expected_width_samples(chord_mm, speed_mms=speed_mms, rate_hz=rate_hz)
    lo = max(2, int(EDGE_CHORD_FRACTION * full))
    hi = int(WIDTH_GATE_SLACK * full)

    # `lo` has a floor of 2 and `hi` does not, so below roughly speed/chord Hz the pair INVERTS and
    # the detector can never accept anything -- it would drive the whole sweep counting zero, with
    # nothing on the matrix to say why. Raise instead of clamping: a clamp would paper over a tick
    # rate so low the mission is already lost, and this must be discovered at DERIVE on a bench, not
    # inferred afterwards from a zero count (honest-instrumentation.md).
    if lo > hi:
        raise ValueError(
            "loop rate {0:.1f} Hz is too low to detect a {1:.0f} mm target at {2:.0f} mm/s: "
            "a full crossing is only {3:.2f} samples, so the width gates invert ({4} > {5}). "
            "Slow the robot down or raise the loop rate; do not widen the gates.".format(
                rate_hz, chord_mm, speed_mms, full, lo, hi))
    return (lo, hi)
