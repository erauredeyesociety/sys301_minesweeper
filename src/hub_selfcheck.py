"""Is every device we expect connected and responding? A DIAGNOSTIC, not a test.

Part of the hub-facing layer. **Only `hub_*.py` modules may import the LEGO API** -- everything else in
`src/` stays pure and runs on the host ([ADR-0004], enforced by ./scripts/check-docs.py).

Split out of the old monolithic `sensors.py` on 2026-08-26: one file per device, so each stays small
enough to read in one sitting. That is load-bearing here -- this project carries no test suite and no
debugger, and smallness is what replaces both (test_methodology.md).

THE RULE: a reader returns None when it cannot read. NEVER 0, never a default, never a last-known
value. A caller that gets None knows it has no data; a caller that gets 0 does not.
"""
import hub_api
from hub_api import API, API_SPIKE2, API_SPIKE3

# as useless as one that always passes.
REQUIRED_PROBES = ("left_motor", "right_motor", "yaw", "color_reflection")


def selfcheck(required=None):
    """Is every device we expect actually connected and responding? Returns a dict of findings.

    An UNKNOWN result is a legitimate answer and is never reported as a pass. This is a DIAGNOSTIC,
    not a test -- it needs the hub, so it can never live in a test suite.

    `required` overrides REQUIRED_PROBES -- pass ("distance",) too once a distance sensor is fitted
    and the port map records it. Probes outside the required set still run and still report; they
    just do not veto the verdict.
    """
    required = REQUIRED_PROBES if required is None else tuple(required)
    report = {"api": API, "checks": {}, "required": required}
    if not hub_api.available():
        report["verdict"] = "UNKNOWN"
        report["reason"] = "no LEGO API present -- running on the host, nothing to check"
        return report

    # left_motor and right_motor are NOT independent: both go through read_motor_degrees(), which
    # reads the pair in one call and raises as one. If either side is unassigned or unplugged, BOTH
    # probes report the same failure -- so main.py's FAULT display must show the "detail" string,
    # which names the port actually at fault, not just the probe name, or the Builder is sent to the
    # wrong plug. Per-side attribution would need a per-side read the LEGO API shape does not give.
    probes = (
        ("left_motor", lambda: read_motor_degrees()[0]),
        ("right_motor", lambda: read_motor_degrees()[1]),
        ("yaw", read_yaw_deg),
        ("color_reflection", read_reflection),
        ("distance", read_distance_mm),
    )
    for name, fn in probes:
        try:
            value = fn()
        except hub_api.PortMapIncomplete as exc:
            report["checks"][name] = {"state": "UNASSIGNED", "detail": str(exc)}
        except Exception as exc:                      # a device that is absent raises; that is data
            report["checks"][name] = {"state": "FAIL", "detail": repr(exc)}
        else:
            state = "UNKNOWN" if value is None else "OK"
            report["checks"][name] = {"state": state, "value": value}

    # Only the REQUIRED probes decide the verdict. A missing optional device is reported, not fatal.
    missing = [n for n in required if n not in report["checks"]]
    bad = [n for n in required
           if report["checks"].get(n, {}).get("state") != "OK"]
    if missing:
        report["verdict"] = "UNKNOWN"
        report["reason"] = "required probe(s) never ran: " + ", ".join(missing)
    elif bad:
        report["verdict"] = "NOT_OK"
        report["reason"] = "required probe(s) not OK: " + ", ".join(bad)
    else:
        report["verdict"] = "OK"
    return report
