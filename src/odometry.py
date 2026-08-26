"""Dead-reckoned pose from wheel encoders and the hub gyro. Pure arithmetic, no hub imports.

WHAT WE KNOW FOR CERTAIN, and it is enough to write this now:
  - **All three candidate motors have built-in absolute rotary encoders** (45602 / 45603 / 45607).
    LEGO's fact sheets give 360 counts per revolution and "can be controlled with an accuracy of
    +/- 3 degrees". So relative wheel rotation is available regardless of which motors we own.
  - **The hub has a 6-axis IMU** (3-axis gyro + 3-axis accelerometer), so absolute-ish heading is
    available without any external sensor.

WHAT WE DO NOT KNOW, and why it does not block this file:
  - Which motors we own (KU-T3) -- affects speed and torque, NOT the arithmetic here.
  - Wheel diameter and track width (KU-M3) -- these are the two constants everything below scales by.
    They are function ARGUMENTS and config values, never baked in, so measuring them later changes a
    number and not a line of code.

USE THE GYRO FOR HEADING, NOT THE ENCODERS. Encoder-difference heading is blind to the dominant error:
unequal effective wheel diameters curve the robot while both encoders read identical counts. The gyro
sees that; the encoders cannot. Encoder heading is kept here only as a cross-check -- a growing
disagreement between the two is itself a useful fault signal.
See docs/research/motion-control-and-odometry.md.
"""

import math

import config


def wheel_circumference_mm(diameter_mm=None):
    if diameter_mm is None:
        diameter_mm = config.WHEEL_DIAMETER_MM
    return math.pi * diameter_mm


def degrees_to_mm(motor_degrees, diameter_mm=None):
    """Motor rotation (degrees) -> ground distance (mm), assuming direct drive."""
    return (motor_degrees / 360.0) * wheel_circumference_mm(diameter_mm)


def mm_to_degrees(distance_mm, diameter_mm=None):
    """Ground distance (mm) -> motor rotation (degrees). The inverse; used to command a drive."""
    circ = wheel_circumference_mm(diameter_mm)
    if circ <= 0.0:
        raise ValueError("wheel circumference must be positive")
    return (distance_mm / circ) * 360.0


def mm_per_count(diameter_mm=None, counts_per_rev=None):
    """Ground resolution of one encoder count. The floor on position accuracy."""
    if counts_per_rev is None:
        counts_per_rev = config.ENCODER_COUNTS_PER_REV
    return wheel_circumference_mm(diameter_mm) / counts_per_rev


def normalize_angle(degrees):
    """Wrap to (-180, 180]. Every heading comparison must go through this."""
    a = degrees % 360.0
    if a > 180.0:
        a -= 360.0
    return a


def heading_from_encoders(left_mm, right_mm, track_width_mm=None):
    """Heading CHANGE implied by a differential wheel-distance difference, in degrees.

    Cross-check only -- see the module docstring for why this is not the heading source.
    """
    if track_width_mm is None:
        track_width_mm = config.TRACK_WIDTH_MM
    if track_width_mm <= 0.0:
        raise ValueError("track width must be positive")
    return math.degrees((right_mm - left_mm) / track_width_mm)


class Pose(object):
    """Position and heading in arena coordinates. x right, y forward, heading 0 = +y, CCW positive."""

    def __init__(self, x_mm=0.0, y_mm=0.0, heading_deg=0.0):
        self.x_mm = x_mm
        self.y_mm = y_mm
        self.heading_deg = heading_deg

    def copy(self):
        return Pose(self.x_mm, self.y_mm, self.heading_deg)

    def describe(self):
        return "pose(x={0:.1f} y={1:.1f} hdg={2:.1f})".format(
            self.x_mm, self.y_mm, self.heading_deg)


class Odometry(object):
    """Integrates encoder deltas into a pose, taking heading from the gyro when it is offered.

    Feed it ABSOLUTE motor positions each tick; it differences them itself, so a caller cannot
    double-count by forgetting to reset. Distances use the exact-arc form when the heading changed
    during the tick, which matters on turns and costs nothing on straights.
    """

    def __init__(self, wheel_diameter_mm=None, track_width_mm=None, pose=None):
        self.wheel_diameter_mm = (config.WHEEL_DIAMETER_MM
                                  if wheel_diameter_mm is None else wheel_diameter_mm)
        self.track_width_mm = (config.TRACK_WIDTH_MM
                               if track_width_mm is None else track_width_mm)
        self.pose = Pose() if pose is None else pose
        self._last_left_deg = None
        self._last_right_deg = None
        self.distance_mm = 0.0          # total path length travelled
        self.encoder_heading_deg = 0.0  # independent cross-check, gyro not involved

    def reset(self, pose=None):
        self.pose = Pose() if pose is None else pose
        self._last_left_deg = None
        self._last_right_deg = None
        self.distance_mm = 0.0
        self.encoder_heading_deg = self.pose.heading_deg

    def update(self, left_motor_deg, right_motor_deg, gyro_heading_deg=None):
        """One tick. Absolute encoder positions in degrees; gyro heading in degrees if available."""
        if self._last_left_deg is None:
            self._last_left_deg = left_motor_deg
            self._last_right_deg = right_motor_deg
            if gyro_heading_deg is not None:
                self.pose.heading_deg = normalize_angle(gyro_heading_deg)
                self.encoder_heading_deg = self.pose.heading_deg
            return self.pose

        d_left = degrees_to_mm(left_motor_deg - self._last_left_deg, self.wheel_diameter_mm)
        d_right = degrees_to_mm(right_motor_deg - self._last_right_deg, self.wheel_diameter_mm)
        self._last_left_deg = left_motor_deg
        self._last_right_deg = right_motor_deg

        d_center = (d_left + d_right) / 2.0
        self.distance_mm += abs(d_center)

        self.encoder_heading_deg = normalize_angle(
            self.encoder_heading_deg
            + heading_from_encoders(d_left, d_right, self.track_width_mm))

        start_heading = self.pose.heading_deg
        if gyro_heading_deg is None:
            end_heading = normalize_angle(
                start_heading + heading_from_encoders(d_left, d_right, self.track_width_mm))
        else:
            end_heading = normalize_angle(gyro_heading_deg)

        delta = normalize_angle(end_heading - start_heading)

        if abs(delta) < 1e-9:
            # Straight: integrate along the current heading.
            theta = math.radians(start_heading)
            self.pose.x_mm += d_center * math.sin(theta) * -1.0
            self.pose.y_mm += d_center * math.cos(theta)
        else:
            # Turning: exact arc, not the small-angle approximation.
            radius = d_center / math.radians(delta)
            t0 = math.radians(start_heading)
            t1 = math.radians(end_heading)
            self.pose.x_mm += -radius * (math.cos(t0) - math.cos(t1))
            self.pose.y_mm += radius * (math.sin(t1) - math.sin(t0))

        self.pose.heading_deg = end_heading
        return self.pose

    def heading_disagreement_deg(self):
        """Gyro-vs-encoder heading gap. Grows with wheel-diameter mismatch or slip -- a fault signal.

        UNVERIFIED: the threshold at which this means 'stop and re-square' must be MEASURED.
        """
        return abs(normalize_angle(self.pose.heading_deg - self.encoder_heading_deg))


def cross_track_error_mm(heading_error_deg, lane_length_mm):
    """Lateral drift at the end of a straight lane, given a constant heading error.

    This is the number that sets lane pitch: a target can slip between two lanes if this grows past
    half the margin. 1 degree over 1.2 m is ~21 mm -- see docs/findings/coverage-time-budget.md.
    """
    return abs(lane_length_mm * math.tan(math.radians(heading_error_deg)))
