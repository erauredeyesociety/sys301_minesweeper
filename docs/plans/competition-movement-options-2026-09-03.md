# Competition Movement Options - 2026-09-03

**Type:** SIDE-CAR PLAN - not a finalized competition design
**Scope:** movement strategies to test next, using the rebuilt robot facts and the existing lawnmower
research. This note does not touch hardware and does not change the state machine in
[mission-algorithm.md](./mission-algorithm.md) or [competition-program-design.md](./competition-program-design.md).

## Measured Facts vs Assumptions

| Item | Status |
|---|---|
| Motors on A/B, `device.id` 48, max speed 930 deg/s | **MEASURED** by hub probes; left/right physical direction still depends on the latest post-rebuild direction check before floor work |
| Colour sensors on C/D, `device.id` 61 | **MEASURED** by hub probes |
| Two colour sensors aligned on the same front line, between the powered wheels | **OPERATOR-REPORTED** current build fact; measure spacing and height before using it as a control signal |
| Wheel diameter 2.5 in / 63.5 mm | **OPERATOR-REPORTED** nominal wheel size; effective rolling diameter still needs BM-3 |
| Boustrophedon/lawnmower sweep | **RESEARCHED** as the baseline coverage pattern, not yet competition-proven |
| Competition boundary/tape line usable by colour sensors | **ASSUMED** until floor/tape reflectance and line width are measured |
| Corner start allowed | **ASSUMED POSSIBILITY** until the competition rules or professor confirm it |

## Candidate Movement Modes

| Mode | Use | Why it is attractive | Main risk |
|---|---|---|---|
| **M0: bench telemetry motion** | Small motor runs, hand shakes, sensor passes over tape/cards | Fastest way to make telemetry decode real motor/IMU/colour changes | Not competition-like; only validates logging and parsers |
| **M1: gyro-held straight lane** | Drive a short straight segment while logging yaw and encoders | Needed for any sweep, even if no boundary following works | Requires heading gain and stop margin tuning |
| **M2: line-between-sensors follower** | Keep a tape/boundary line centered between C and D | Uses the two-sensor front bar as a direct left/right error signal | Only works if line width/spacing make the two sensors see distinguishable states |
| **M3: corner-start square-up** | Begin in a known corner, align to two boundary edges, reset pose | Gives odometry a clean `(0,0,heading)` seed before sweeping | Needs reliable boundary detection and a legal corner start |
| **M4: odometry lawnmower with boundary stop** | Sweep lanes by distance, turn 90-step-90, stop on boundary/tape | Fits the existing architecture and coverage research | Depends on BM-3/BM-4/BM-8 and boundary stop not firing falsely |
| **M5: hybrid line-assisted lawnmower** | Use M4 for lanes, use M2 only when crossing/approaching boundary lines | Lets tape correct local drift without full line following everywhere | Needs mode switching rules from telemetry evidence |

## Sensor and Line Assumptions

The two-sensor line follower is plausible only if the physical line is wide enough to be seen reliably
but not so wide that both sensors are always on the same colour. The first useful geometry is:

```
sensor_spacing_mm = measured centre-to-centre spacing between C and D spots
line_width_mm     = measured tape/boundary width
spot_diameter_mm  = measured colour sensor footprint at mounted height
```

For a "keep the line between the sensors" controller, the clean states are:

| Left C | Right D | Meaning |
|---|---|---|
| floor | floor | centered over the interior floor, no boundary correction |
| tape | floor | line is under/near left sensor; steer right or stop, depending on mode |
| floor | tape | line is under/near right sensor; steer left or stop, depending on mode |
| tape | tape | line is too wide, robot is over the boundary, or sensors are too close; stop and log |

This assumes the line/tape reflectance separates from the floor on both sensors after per-sensor
calibration. If the tape and floor are not separable, M2/M3/M5 are dropped and the sweep falls back to
odometry plus human-observed bounded tests.

## Corner-Start Setup

If a corner start is allowed, use it as a calibration ritual, not as magic localization:

1. Place the robot against or just inside the chosen corner with the front sensor bar square to the first
   boundary line.
2. Log a stationary pre-roll: yaw, pitch/roll/stable flag, motor degrees, both reflections/RGBI values.
3. Reset yaw only while stationary and stable.
4. Nudge forward slowly until C/D see the first boundary transition, then stop.
5. Optionally rotate or back up to sample the second boundary edge if the rules and space allow it.
6. Set pose to the chosen corner frame only after the log shows the expected left/right edge order.

The lawnmower planner can then treat the corner as the origin: first lane runs along one boundary axis,
the lane pitch steps into the arena, and each end-of-lane turn remains the existing 90-step-90 pattern.
The corner does not remove the need for odometry calibration; it only prevents the initial pose from
being a guess.

## Telemetry Needed Per Mode

| Mode | Required fields |
|---|---|
| M0 | `t_ms`, `seq`, motor A/B absolute and relative degrees, motor speed/status, yaw/pitch/roll or angular rate, C/D reflection, C/D RGBI, command percent, battery if available |
| M1 | M0 plus target heading, heading error, correction percent, left/right command percent, stop reason |
| M2 | M0 plus left/right floor-vs-line boolean, line state (`none`, `left`, `right`, `both`), steering correction, edge timestamp per sensor |
| M3 | M0 plus corner phase, yaw reset time, first-edge and second-edge samples, computed skew/angle if both sensors cross the same edge |
| M4 | M1 plus lane index, lane target heading, commanded lane distance, estimated x/y/heading, boundary-stop flag, detection event state |
| M5 | M2 and M4 combined, plus active control mode (`gyro_lane`, `line_center`, `boundary_stop`, `turn`) |

The important sequencing point: log raw sensor values even when the live stream is thinned. The parser
can later change thresholds, line states, and tuning gains without rerunning the robot.

## Next Bounded Tests

These are intentionally small and safe. They are not autonomous competition runs.

| Test | Setup | Pass condition | Unlocks |
|---|---|---|---|
| **T1: stationary verbose log** | Hub still, motors idle, wiggle/shake by hand, move tape/cards under C/D | Log shows changing IMU and both colour sensors with correct timestamps | Confirms internal log schema and decoder |
| **T2: wheels-up motor telemetry** | Robot blocked or held, short A/B motor command | Encoders, motor status, command percent, and IMU disturbance are recorded together | Proves movement telemetry without floor risk |
| **T3: hand-guided line crossing** | Motors off, slide/tilt robot or tape so boundary crosses C then D | Decoder labels left/right/both line states and edge order correctly | Proves two-sensor line geometry before driving |
| **T4: low-speed straight nudge** | Short, attended floor move away from USB cable if possible | M1 log computes heading error/correction and bounded stop | First heading-hold tuning data |
| **T5: line-between-sensors crawl** | Very short tape segment, slow speed, human ready to lift/stop | M2 correction sign is correct; stop on `both` works | Decides whether line-centering is viable |
| **T6: corner ritual dry run** | Mark a small fake corner with tape, no full sweep | Corner phases appear in log and reset pose only after expected edge evidence | Decides whether corner-start lawnmower is worth implementing |

## Recommendation

Do the telemetry ladder first: T1, T2, T3. It directly supports the user's immediate goal of decoding
motor, IMU, and colour data, and it gives the BLE/internal-log work a concrete record to carry. After
that, run T4/T5 only with the robot attended and the movement bounded. M4/M5 stay design candidates until
BM-3 effective wheel diameter, BM-4 turn scale/track width, and a real line/tape separability result exist.
