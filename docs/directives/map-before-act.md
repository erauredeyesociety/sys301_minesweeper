# Map Before Act

**Purpose.** Enumerate the surface before changing anything load-bearing. On this project the guarded
invariants are the **count**, the **calibration**, and the **hub's software state**.

- **Read-only audit first.** Before changing detection, counting, calibration, or the sweep state
  machine, grep every caller and every input to it. No edits in that phase.
- **`ACTIVE != FIRES`.** Trace from the real entry point — the program the hub actually runs — not a
  sibling module that looks right. On a hub with program slots it is genuinely easy to edit one file
  and run another. Verify *which slot ran*.
- **Verify via ground truth, not absence of error.** "The program uploaded" and "the script exited 0"
  are not "the robot counted correctly". Proof is a measured reading or an observed motion, written
  down. See [honest-instrumentation.md](./honest-instrumentation.md).
- **Chesterton's Fence.** A magic constant in tuned robot code usually encodes a measurement someone
  took on the real floor. Find out what it measured before you change it — and record the measurement
  in `docs/findings/` so the next person doesn't have to ask.
- **Prove GONE, not MOVED** before calling code dead — grep the whole tree.
- **One hat at a time:** refactor OR change behavior, never both in the same edit. Mid-sprint, on
  hardware, a combined change is unbisectable.
