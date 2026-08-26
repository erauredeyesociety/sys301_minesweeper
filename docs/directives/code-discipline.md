# Code Discipline

**Purpose.** Write less code. On a two-sprint project with one programmer, every line is a liability you
must also debug on a robot.

## Layout — and the one rule that matters

```mermaid
flowchart LR
    subgraph HOST["runs on the Ubuntu host AND the hub"]
        M["<b>src/</b><br/>pure Python logic<br/>no hardware, fully testable"]
    end
    subgraph HUB["runs on the hub only"]
        IO["<b>src/</b><br/>thin adapter<br/>the ONLY LEGO API caller"]
    end
    SENSORS(["sensors · motors<br/>light matrix"]) <--> IO
    IO -->|"plain numbers in"| M
    M -->|"decisions out"| IO
```

**`src/` imports NOTHING hub-only.** Not `hub`, `motor`, `motor_pair`, `color_sensor`,
`distance_sensor`, `force_sensor`, `motion_sensor`, or `runloop`. Not "just for a type hint", not "just
in this one file". If it fails to import on a laptop with no robot attached, the boundary is broken.

| Layer | Contains | Imports | Runs on |
|---|---|---|---|
| `src/` | Detection, debounce, counting, calibration/threshold math, sweep state machine, port constants | Plain Python only | Host **and** hub |
| `src/` | Sensor reads, motor drive, light-matrix and speaker output, the run loop | The LEGO API, freely | Hub only |

Readings cross the boundary as **plain numbers**: `sensors.py` reads a device and hands the pure modules
an integer; they return a decision; `sensors.py` acts on it. The pure modules never learn a hub exists.

**Why:** the hub lives in the yellow box between classes and work happens in class — hub time is the
scarcest resource on this project. A bug found on a laptop costs a minute; the same bug found on the robot
costs a class period, with three teammates waiting and only the Builder allowed to operate it. Second
payoff: the report can demonstrate the counting algorithm independently of the hardware, which is a far
stronger verification claim than "it counted right in the demo."
Full rationale: [ADR-0002](../decisions/0002-split-mission-logic-from-hub-io.md); scope TR-2.

**Enforcement is a test, not a convention** — one floor test asserts the boundary holds. If it goes red,
fix the code, never the test. See [testing-discipline.md](./testing-discipline.md).

## Why no code exists yet

Two real blockers: the **mission is unknown** ([../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25)), and
the **hub's API generation is unidentified**. SPIKE 2 (`from spike import PrimeHub`) and SPIKE 3
(`import motor`, `from hub import port`, `import runloop`) are not variants of one API — different call
signatures, different units. Don't write against a guess. Note the second blocker gates only `src/`:
once the mission is known, `src/` can be written and fully tested on the host before the hub is
ever identified. That is precisely what the split buys.

## MicroPython is not full Python

- **No `numpy`/`scipy`/`pandas`.** Do the arithmetic by hand; it's a handful of lines.
- **The standard library is a subset**, often cut down with a different surface than the CPython docs describe.
- **Memory is limited, no swap.** Large lists, per-sample logging into RAM, and string-building in a hot loop will bite.
- **Assume a module is absent until proven present on the actual hub.** "It's in the Python docs" is not
  evidence — prove it with a diagnostic in `scripts/` and record the result in [../findings/](../findings/).
- `src/` gets the strictest reading: write it to the MicroPython subset and it runs on the host for
  free. The reverse is not true.

## Conventions

- **Research and plan so less code is needed.** Motor pairing, timed moves, gyro turns, and light-matrix
  output already exist in the SPIKE API. Custom code needs a documented reason.
- **No magic numbers.** Ports come from [../hardware/port-map.md](../hardware/port-map.md) (TR-5),
  transcribed once into a single constants module. Thresholds are **calibrated at run start**, never
  hard-coded (TR-4).
- **One accountable path per concern.** ONE count variable, ONE calibration routine. Two places that
  compute the count will disagree, and you will find out on Demo Day.
- **Comment the measurement and the why, never the what.** A tuning constant carries what was measured, on
  what surface, under what lighting, and when.
- **Don't over-build error handling out of the gate.** One basic failure path per operation — stop the
  motors, show a state on the matrix. Heavier recovery only against a failure you have actually OBSERVED.
  Some faults belong to the hardware, not the code.
