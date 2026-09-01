# Lessons Learned — INDEX

Prescriptive rules distilled from **our own** mistakes, as **WHEN → DON'T → BECAUSE**. The
generalization of a finding, not the finding itself. These are the Intro Report's "what we would do
differently" section.

| Lesson | Date | One-line |
|---|---|---|
| [dont-interrupt-the-hub-os-if-you-want-bluetooth.md](./dont-interrupt-the-hub-os-if-you-want-bluetooth.md) | 2026-09-01 | The CONNECT button, BLE advertising, and the USB control-protocol responder are all **Hub OS services**; a probe's Ctrl-C interrupts the Hub OS and kills all three until a **restart** — it does not self-recover. Prefer the control protocol (no Ctrl-C) when you want Bluetooth alive. Un-retracts the earlier 'probing kills BLE' claim, whose retraction rested on a false self-recovery assumption. |
| [bound-the-inputs-before-trusting-a-conclusion.md](./bound-the-inputs-before-trusting-a-conclusion.md) | 2026-08-25 | A decision-grade conclusion inherits its weakest input; audit the inputs, not just the arithmetic |
| [model-only-to-the-next-decision.md](./model-only-to-the-next-decision.md) | 2026-08-25 | Stop modelling an unmeasured number once it stops changing a decision; carry it as a variable and go measure |
| [a-tool-works-when-it-does-its-job.md](./a-tool-works-when-it-does-its-job.md) | 2026-08-26 | Report status against the tool's purpose, not the component you tested — partial is PARTIAL, not working-with-a-caveat |
| [say-which-kind-of-verified.md](./say-which-kind-of-verified.md) | 2026-08-26 | *measured* means **on real hardware** and nothing else — say "computed" or "confirmed against" otherwise. And never initiate a hardware connection: the operator says when it is connected |
| [working-with-the-operator.md](./working-with-the-operator.md) | 2026-08-26 | **Project management, not code.** Seven recurring collaboration corrections: shared resources are operator-gated · their definition of "working" governs · script the ritual because complex commands cost *them* an approval · don't build ahead of an unproven dependency · research broadly, implement narrowly · scope creep hides in bookkeeping · **check the source before complying** |
| [dont-time-one-call-in-a-tight-loop.md](./dont-time-one-call-in-a-tight-loop.md) | 2026-08-27 | Benchmark the call **mix** you will ship, never one call in a tight loop summed — a repeated call may be served from a cache. Ours disagreed with itself by **4×** (0.328 ms summed vs 1.350 ms mixed) and implied an impossible 6,000–45,000 Hz |
| [probe-with-scripts-not-commands.md](./probe-with-scripts-not-commands.md) | 2026-08-27 | Interrogate hardware from a **script with a deadline**, never a typed command — a script that hangs is disposable, a hung session is not. Bash *inside* Python is fine; the rule is about who holds the thing that can block |

The two are siblings: **bound the inputs your conclusion rests on, then stop refining them and go measure.**
