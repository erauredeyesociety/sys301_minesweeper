"""Boustrophedon ("lawnmower") coverage as a state machine that emits motion commands.

Chosen over spiral and random walk because it is the pattern the coverage-path-planning
literature prescribes for a robot with no global localization: every lane is a straight run
that can be re-squared against a known reference at each end, so heading error is corrected
every lane instead of accumulating across the whole run.
See docs/research/detection-and-sweep-techniques.md.

Structural de-duplication: each lane is driven exactly once and lanes do not overlap beyond
the deliberate margin, so the same target cannot be presented to the detector twice. That is
a property of the PATH, not of the odometry -- which matters, because the odometry is the
part we do not trust.

This module emits commands and consumes completion signals. It never touches a motor.
"""

import config

# Commands the caller (the hub-facing layer) is expected to execute.
CMD_DRIVE = "drive"      # value: millimetres forward
CMD_TURN = "turn"        # value: degrees, positive = right
CMD_RESQUARE = "resquare"  # re-establish heading against a fixed reference; no value
CMD_STOP = "stop"

# States
IDLE = "idle"
LANE = "lane"            # driving a sweep lane, detector active
RESQUARE = "resquare"    # re-square the heading at the end of a lane, before turning out of it
TURN_A = "turn_a"        # first 90 deg of the lane change
STEP = "step"            # sideways step to the next lane
TURN_B = "turn_b"        # second 90 deg, now facing back down the arena
DONE = "done"


class Command(object):
    def __init__(self, kind, value=0.0, detect=False):
        self.kind = kind
        self.value = value
        self.detect = detect   # should the detector be running during this command?

    def describe(self):
        return "{0}({1:.1f}){2}".format(
            self.kind, self.value, " +detect" if self.detect else "")


class SweepPlan(object):
    """Drives the lane sequence. Call next_command() until it returns a CMD_STOP."""

    def __init__(self, width_mm=None, length_mm=None, pitch_mm=None):
        self.width_mm = config.ARENA_WIDTH_MM if width_mm is None else width_mm
        self.length_mm = config.ARENA_LENGTH_MM if length_mm is None else length_mm
        self.pitch_mm = config.lane_pitch_mm() if pitch_mm is None else pitch_mm
        if self.pitch_mm <= 0.0:
            raise ValueError("lane pitch must be positive")
        if self.width_mm <= 0.0 or self.length_mm <= 0.0:
            raise ValueError("arena dimensions must be positive")

        self.total_lanes = config.lane_count(self.width_mm) if pitch_mm is None \
            else self._lanes_for(self.width_mm, self.pitch_mm)
        self.state = IDLE
        self.lane_index = 0
        self.turn_direction = 1   # +1 right, -1 left; alternates each lane change
        self.stop_requested = False

    @staticmethod
    def _lanes_for(width, pitch):
        n = int(width / pitch)
        if n * pitch < width:
            n += 1
        return n

    def path_length_mm(self):
        """Driving distance for the whole sweep, lanes plus sideways steps."""
        lanes = self.total_lanes * self.length_mm
        steps = (self.total_lanes - 1) * self.pitch_mm if self.total_lanes > 1 else 0.0
        return lanes + steps

    def estimated_seconds(self, speed_mms=None):
        speed = config.TRAVERSE_SPEED_MMS if speed_mms is None else speed_mms
        if speed <= 0.0:
            raise ValueError("speed must be positive")
        return self.path_length_mm() / speed

    def estimated_lane_seconds(self, speed_mms=None):
        """Seconds for ONE more lane plus its sideways step. TURN TIME IS EXCLUDED.

        Not estimated_seconds(), which is the whole sweep: the time box asks "can I afford the next
        lane?" at each lane start, and answering that with the cost of every remaining lane would
        trip the box on lane 1 of every run (degraded mode T1).

        The exclusion is not a rounding error -- two 90 deg turns per lane change at an unmeasured
        TURN_RATE_DPS is real time this number does not contain, so it UNDERSTATES the lane. Fold
        turn time in once BM-4/BM-7 have measured a turn rate.
        """
        speed = config.TRAVERSE_SPEED_MMS if speed_mms is None else speed_mms
        if speed <= 0.0:
            raise ValueError("speed must be positive")
        return (self.length_mm + self.pitch_mm) / speed

    def stop_after_current_lane(self):
        """Finish the lane in progress, then stop instead of turning into the next one.

        A lane boundary is the only place a truncated run is still reportable: coverage is
        lanes_completed / lanes_planned, and a sweep abandoned halfway down a lane has no honest
        value for either. The time box (T1) calls this rather than stopping where it stands.
        """
        self.stop_requested = True

    def next_command(self):
        """Advance the state machine one step and return the command to execute."""
        if self.state == IDLE:
            self.state = LANE
            return Command(CMD_DRIVE, self.length_mm, detect=True)

        if self.state == LANE:
            self.lane_index += 1
            if self.lane_index >= self.total_lanes:
                self.state = DONE
                return Command(CMD_STOP)
            if self.stop_requested:
                self.state = DONE
                return Command(CMD_STOP)
            # Re-square only when another lane follows. Squaring against a boundary the robot has
            # just finished with drives it back into that boundary for nothing, and after the last
            # lane there is no heading left to protect.
            self.state = RESQUARE
            return Command(CMD_RESQUARE, detect=False)

        if self.state == RESQUARE:
            self.state = TURN_A
            return Command(CMD_TURN, 90.0 * self.turn_direction)

        if self.state == TURN_A:
            self.state = STEP
            return Command(CMD_DRIVE, self.pitch_mm)

        if self.state == STEP:
            self.state = TURN_B
            return Command(CMD_TURN, 90.0 * self.turn_direction)

        if self.state == TURN_B:
            self.turn_direction = -self.turn_direction
            self.state = LANE
            return Command(CMD_DRIVE, self.length_mm, detect=True)

        return Command(CMD_STOP)

    def is_done(self):
        return self.state == DONE

    def lanes_remaining(self):
        return max(0, self.total_lanes - self.lane_index)
