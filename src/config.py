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

# --- Target ------------------------------------------------------------------
TARGET_SIZE_MM = 76.0          # [ASSUMED] standard 3in sticky note; MEASURE the real pack.

# --- Sweep geometry ----------------------------------------------------------
# Lane pitch must stay under the target size minus twice the cross-track error, or a note
# can fall between two lanes. CROSS_TRACK_ERROR_MM must be MEASURED (UMBmark square-path run).
CROSS_TRACK_ERROR_MM = 15.0    # [ASSUMED] optimistic. Measure before trusting.
LANE_OVERLAP_MM = 5.0          # deliberate safety margin on top of the error allowance

# --- Detection ---------------------------------------------------------------
# Thresholds are DERIVED AT RUN START by calibration.py, never hard-coded (scope TR-4).
# These only bound what calibration is allowed to produce.
MIN_CONTRAST = 12.0            # reflectance points. Below this, calibration FAILS LOUD.
HYSTERESIS_FRACTION = 0.25     # gap between on/off thresholds, as a fraction of contrast
MIN_DWELL_SAMPLES = 2          # consecutive samples needed to accept a state change
CALIBRATION_SAMPLES = 20       # per surface, per placement
CALIBRATION_PLACEMENTS = 3     # sample the floor in 3 spots, not 1

# --- Event width gate --------------------------------------------------------
# A real note produces an event of a plausible width. Too narrow is noise; too wide is a
# seam, a shadow, or two notes merged. Widths are in SAMPLES, so they depend on sample rate
# and traverse speed -- recompute with expected_width_samples() rather than guessing.
MIN_EVENT_SAMPLES = 2
MAX_EVENT_SAMPLES = 400        # generous; tighten once the real sample rate is measured

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
SAMPLE_RATE_HZ = 100.0         # UNVERIFIED: LEGO spec figure for the colour sensor


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


def expected_width_samples(chord_mm=None):
    """How many samples the sensor takes while crossing a target of the given chord."""
    if chord_mm is None:
        chord_mm = TARGET_SIZE_MM
    if TRAVERSE_SPEED_MMS <= 0.0:
        raise ValueError("TRAVERSE_SPEED_MMS must be positive")
    return (chord_mm / TRAVERSE_SPEED_MMS) * SAMPLE_RATE_HZ
