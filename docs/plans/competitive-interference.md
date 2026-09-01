# Competitive interference — authorized scope, deferred build

**Type:** ACTIVE-SPEC (scope capture) · **Created:** 2026-09-01 · **Status:** DOCUMENTED, NOT BUILT

## The fact, captured

The operator states (2026-09-01): **this is a class robot competition in which interfering with other
teams' robots during their sweep is explicitly allowed — it is authorized, not an exploit.** The course
is framed as partly a cybersecurity exercise.

Recording it because it is a real requirement that will shape design (both offense and defense), and
because written team communication is a graded deliverable. **It is not being built yet** — the
operator's direction on 2026-09-01 is *"we are not worried about cyber capabilities yet… continue full
force on developing the robot and later we will address cyber stuff."*

## What this implies for the robot's OWN design — relevant now, even before any offense

Our hub is exposed on the same BLE control plane every SPIKE hub uses, so whatever a team could do to
another team, a team could do to us:

- **The BLE control plane is the attack surface.** LEGO's `FD02` service takes framed commands over a
  write-without-response characteristic — including program start/stop and, plausibly, shutdown. The
  **LEGO Hub OS owns that plane**, not our program, so a program-level password cannot block a
  firmware-level command. Defending it likely means *not advertising* except when we need to connect
  (the advertising window is already short and self-terminating), and preferring the **USB cable**,
  which is point-to-point and cannot be reached over the air, whenever the robot is tethered.
- **Run untethered only as long as necessary.** Every second the hub advertises is exposure.
- **A dropped BLE link must fail safe.** If the robot is being remotely disrupted mid-sweep, it should
  stop or hold heading, never drive blind. This is a `main.py` design requirement regardless of
  offense.

## Open questions to confirm in writing with the professor

- **Get the interference authorization in writing.** It currently rests on a relayed conversation.
  A graded, adversarial activity should have an unambiguous rule set: what is allowed (jamming?
  sending control commands? physical?), what is out of bounds, and whether attribution matters.
- Is there a scoring reward for disruption, or is it purely defensive risk to plan around?

## When it is time to build (deferred)

Revisit only on the operator's word. At that point this splits into **defense** (harden our hub,
detect disruption, fail safe) and **offense** (out of scope until authorization is confirmed in
writing per above). Nothing offensive is designed or built here yet.
