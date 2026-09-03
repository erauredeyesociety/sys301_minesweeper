"""Small motion-tuning math helpers.

The functions here are pure arithmetic. They do not command motors and do not import the LEGO API,
so they can be unit-checked on the host before a robot ever moves.
"""
import math

from config import WHEEL_DIAMETER_MM
from odometry import degrees_to_mm, normalize_angle


def clamp(value, lo, hi):
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return max(lo, min(hi, value))


def heading_error_deg(target_deg, current_deg):
    """Shortest signed heading error, positive meaning the target is counter-clockwise from current."""
    return normalize_angle(target_deg - current_deg)


def heading_hold_turn_pct(target_deg, current_deg, kp_pct_per_deg, limit_pct):
    """P-controller turn correction for a differential drive.

    Positive return means "turn left / counter-clockwise" in the same convention as odometry:
    the right wheel travels farther than the left wheel.
    """
    if kp_pct_per_deg < 0.0:
        raise ValueError("kp_pct_per_deg must be non-negative")
    if limit_pct < 0.0:
        raise ValueError("limit_pct must be non-negative")
    return clamp(heading_error_deg(target_deg, current_deg) * kp_pct_per_deg,
                 -limit_pct, limit_pct)


def mix_forward_turn_pct(forward_pct, turn_pct, limit_pct=100.0):
    """Mix robot-forward and turn requests into left/right motor percentages.

    Positive turn_pct is counter-clockwise, so the right side gets more drive.
    """
    if limit_pct <= 0.0:
        raise ValueError("limit_pct must be positive")
    left = clamp(forward_pct - turn_pct, -limit_pct, limit_pct)
    right = clamp(forward_pct + turn_pct, -limit_pct, limit_pct)
    return (left, right)


def effective_wheel_diameter_mm(measured_distance_mm, encoder_delta_deg):
    """Back out rolling wheel diameter from a straight-line distance test.

    Use this after commanding or manually measuring a straight run on the real floor:
    distance = pi * diameter * encoder_degrees / 360.
    """
    if encoder_delta_deg == 0.0:
        raise ValueError("encoder_delta_deg must be non-zero")
    return abs((measured_distance_mm * 360.0) / (math.pi * encoder_delta_deg))


def yaw_gain_deg_per_encoder_diff_deg(left_delta_deg, right_delta_deg, heading_delta_deg):
    """Observed heading degrees per encoder-difference degree for a spin/arc test."""
    diff = right_delta_deg - left_delta_deg
    if diff == 0.0:
        raise ValueError("right-left encoder delta must be non-zero")
    return heading_delta_deg / diff


def track_width_from_spin_mm(left_delta_deg, right_delta_deg, heading_delta_deg,
                             wheel_diameter_mm=None):
    """Estimate effective track width from an in-place or curved turn.

    Formula: heading_rad = (right_distance - left_distance) / track_width.
    """
    if wheel_diameter_mm is None:
        wheel_diameter_mm = WHEEL_DIAMETER_MM
    heading_rad = math.radians(heading_delta_deg)
    if heading_rad == 0.0:
        raise ValueError("heading_delta_deg must be non-zero")
    diff_mm = degrees_to_mm(right_delta_deg - left_delta_deg, wheel_diameter_mm)
    return abs(diff_mm / heading_rad)


def unwrap_degrees(samples):
    """Unwrap yaw samples that wrap at +/-180 degrees."""
    samples = list(samples)
    if not samples:
        return []
    out = [float(samples[0])]
    for sample in samples[1:]:
        out.append(out[-1] + normalize_angle(float(sample) - out[-1]))
    return out


def fit_slope_through_origin(xs, ys):
    """Least-squares slope y = m*x with no intercept."""
    xs = list(xs)
    ys = list(ys)
    if len(xs) != len(ys):
        raise ValueError("xs and ys length mismatch")
    den = sum(x * x for x in xs)
    if den == 0.0:
        raise ValueError("all x values are zero")
    return sum(x * y for x, y in zip(xs, ys)) / den


def track_width_from_samples_mm(left_deg, right_deg, heading_deg, wheel_diameter_mm=None):
    """Estimate track width from synchronized encoder and heading samples."""
    left_deg = list(left_deg)
    right_deg = list(right_deg)
    heading_deg = unwrap_degrees(heading_deg)
    if not (len(left_deg) == len(right_deg) == len(heading_deg)):
        raise ValueError("left, right, and heading sample counts must match")
    if len(left_deg) < 2:
        raise ValueError("need at least two samples")
    if wheel_diameter_mm is None:
        wheel_diameter_mm = WHEEL_DIAMETER_MM

    l0, r0, h0 = left_deg[0], right_deg[0], heading_deg[0]
    diff_mm = []
    heading_rad = []
    for l, r, h in zip(left_deg[1:], right_deg[1:], heading_deg[1:]):
        diff_mm.append(degrees_to_mm((r - r0) - (l - l0), wheel_diameter_mm))
        heading_rad.append(math.radians(h - h0))
    return abs(fit_slope_through_origin(heading_rad, diff_mm))


def stop_margin_mm(speed_mms, reaction_ms, coast_mm=0.0, safety_mm=0.0):
    """Distance budget needed after deciding to stop."""
    if speed_mms < 0.0 or reaction_ms < 0.0 or coast_mm < 0.0 or safety_mm < 0.0:
        raise ValueError("speed, reaction, coast, and safety margins must be non-negative")
    return speed_mms * (reaction_ms / 1000.0) + coast_mm + safety_mm
