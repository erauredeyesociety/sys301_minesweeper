# Decisions (ADRs) — INDEX

One-screen records of why we chose X over Y. **Immutable** — a reversal is a NEW record that
supersedes; never edit an old one. Keep wrong ideas WITH the why, because the why is the value.

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-stock-lego-firmware-only.md) | Stock LEGO firmware only; Pybricks blacklisted | Accepted |
| [0002](./0002-split-mission-logic-from-hub-io.md) | Split pure mission logic from hub I/O | **Superseded by 0004** (goal still binding) |
| [0003](./0003-repo-holds-all-team-work.md) | This repo holds all team work, including course deliverables | Accepted |
| [0004](./0004-flat-src-supersedes-package-split.md) | Flat `src/` supersedes the package split; purity enforced by a grep | Accepted (enforcement amended by 0005) |
| [0005](./0005-no-test-suite-verify-on-hardware.md) | No test suite — verification happens on the robot | Accepted |
| [0006](./0006-docs-rag-llm-is-operator-gated.md) | The docs-rag's LLM is operator-gated; no sub-5B; remote 9B on skytracker is the target | Accepted |
| [0007](./0007-deploy-by-writing-modules-to-flash-lib.md) | Deploy by writing modules into `/flash/lib` over the REPL, verified by an on-hub SHA-256; Chrome + WebSerial is the fallback | Accepted — closes the *module* half of KU-D1; program launch stays open as KU-M16 |
