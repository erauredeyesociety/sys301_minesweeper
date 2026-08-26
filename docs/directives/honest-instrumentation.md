# Honest Instrumentation

**Purpose.** The fastest way to lose a hardware project is to believe a number nothing measured. On
Demo Day the robot either counts correctly or it doesn't; every claim before then must be traceable to
an actual observation.

- **NEVER report a sensor reading, a count, or a "works" that was not observed.** No invented values,
  no "should be around 70%", no reporting a hub result while the hub is unplugged. If it wasn't run,
  say it wasn't run. This is blacklist-level ([../scope.md](../scope.md)).
- **A check that cannot run returns UNKNOWN — never pass.** If `/dev/ttyACM0` is absent, the hub check
  is UNKNOWN, not green. No bare `except`, no skip-to-pass.
- **A deploy script must assert known-correct output**, not "no error". "The upload command exited 0"
  proves nothing about what is on the hub.
- **One accountable path per concern.** ONE count variable, ONE calibration routine, ONE port map
  ([../hardware/port-map.md](../hardware/port-map.md)) that the code reads. Two places that compute
  the count WILL disagree, and you will debug it on Demo Day.
- **Instrument before you need it.** The hub has a light matrix and a speaker — use them as the live
  state display (calibrating / sweeping / count) so a failed run is diagnosable from across the room
  without a laptop.
- **Log what you measured, with units and conditions.** A reflected-light threshold is meaningless
  without the floor surface and the lighting it was taken under. Put it in `docs/findings/`.
