# Runbooks — INDEX

Repeatable operator procedures. Written so a teammate can follow them under time pressure without
context. Every hub-touching step **an agent runs** goes through a script with an explicit timeout
([../directives/automation-first.md](../directives/automation-first.md)); steps a human performs at the
machine state the observation to expect instead.

| Runbook | When to run it | Owner | Status |
|---|---|---|---|
| [hub-identification.md](./hub-identification.md) | First time the hub is connected — **READ-ONLY**, writes nothing, must not trigger a Hub OS update. Resolves the `[UNKNOWN]` SPIKE 2 vs SPIKE 3 API generation that blocks all mission code. | Programmer (plugs in), operator | Ready to run · hub-side steps **UNVERIFIED** (no hub yet) |
| [demo-day.md](./demo-day.md) | End of every class (pack-out check), start of class 10 SEP, and before/after every dry run | **Builder** — the only authorised robot operator | Drafted · mission- and arena-dependent steps **PENDING** the instructor's briefing |
| [measure-drivetrain.md](./measure-drivetrain.md) | The first class session at which a driving chassis and the hub exist together — **planned 3 SEP**. **No colour sensor is needed for any step in it** (only the plan's BM-5 sensing-loaded loop rate and BM-6 spot size want one), so it must not be held behind that purchase. Measures the drivetrain constants the whole sweep design rests on: effective rolling diameter under load, track width from a spin turn that actually closes, top ground speed (saturation vs control loss), and cross-track error over a real lane. | **Builder** operates; **Programmer** at the laptop | Written 2026-08-25 · **UNRUN, no hub, no robot** — every hub-side step is **UNVERIFIED**. Plan and drop order: [../plans/bench-measurement-plan.md](../plans/bench-measurement-plan.md) |
| [researchhub-tunnel.md](./researchhub-tunnel.md) | Only when the literature workflow is actually needed — a real literature review for the Intro Report, or a search `grep` over `docs/` could not answer. **Not needed to build the robot.** Covers the SSH forward to ResearchHub on pwnstar (up / status / stale-repair / port discovery) and `fetch_paper.py`. | Programmer | Verified 2026-08-25, **independently re-verified** the same day (discover/up/status/restart/down, `/health`, a real search, and the fetcher all re-run) · port **5347** confirmed by probe · link is **flaky**, expect `restart` |
| [docs-rag.md](./docs-rag.md) | Any time you would otherwise `cat` or grep a long file in `docs/` — ask the project's own docs a question and get back a file path + line span. Covers start / stop / re-ingest / query / when it breaks. | Whoever is searching (no hub, no roles) | **Search VERIFIED 2026-08-25**, independently re-verified same day (down/up round-trip, real queries, hand-checked citations, read-only mount proven) · `/api/ask` **returns HTTP 500** — no LLM model pulled · ollama dies on reboot, restart it with `./ollama-serve.sh` · ollama costs **~2 GB**, which `rag doctor` does not count |

Deploy runbook lands once the toolchain route is chosen ([../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md)).
