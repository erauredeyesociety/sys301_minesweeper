"""Distance sensor 45604 -- ULTRASONIC, not time-of-flight. Boundary detection.

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

# --- Distance sensor --------------------------------------------------------
# Role: arena boundary and obstacles. Whether we need it at all depends on professor Q3 (what bounds
# the area) -- it is unpurchased, so this is scaffolding against a decision not yet made.

def read_distance_mm():
    """Distance in mm. None when nothing is in range -- which is NOT the same as zero.

    Returning 0 for out-of-range would read as 'a wall is touching us' and drive a stop. None.
    """
    if API == API_SPIKE3:
        mm = _distance.distance(hub_api._require(hub_api.DISTANCE_PORT, "hub_api.DISTANCE_PORT"))
        # SPIKE 3 returns -1, NOT an exception, whenever it cannot read -- which is the COMMON case
        # pointed at open space or an off-axis wall (docs/research/detection-and-sweep-techniques.md).
        # -1 mm is not a distance; it is the sentinel this module exists to translate.
        if mm is None or mm < 0:
            return None
        return mm
    if API == API_SPIKE2:
        # SPIKE 2 answers in CENTIMETRES and this function is named _mm: convert, or every boundary
        # test is off by 10x. It returns None out of range, which is already the right answer.
        cm = hub_api._distance_obj().get_distance_cm(short_range=False)
        if cm is None:
            return None
        return cm * 10.0
    return None
