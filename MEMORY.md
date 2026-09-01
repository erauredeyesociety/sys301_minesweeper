# MEMORY.md — sys301_minesweeper

Durable project context across sessions. Pointers and hard-won facts, not a duplicate of the docs.
Operational rules live in [CLAUDE.md](CLAUDE.md); current state lives in [docs/todo.md](docs/todo.md).

> Last updated: 2026-09-01 (robot drives on command; docs-rag /api/ask working)

---

## Hard-won hardware facts — measured 2026-08-27, do not re-derive

- **It is SPIKE 3.** MicroPython 1.24.0, STM32F413. `motor` / `motor_pair` / `runloop` /
  `color_sensor` present, **no `spike` module** — so **every SPIKE 2 tutorial online is useless to
  us**, and most SPIKE material online is SPIKE 2. Check a source's generation before believing it.
- **Our hub:** `device_uuid` `03970000-3600-1B00-1450-30514B323320`, BLE `64:8C:BB:0A:1C:8C`, named
  `Team 21`. **In a room of hubs, identify by connecting and comparing the device UUID** — never by
  name (user-settable) or MAC (type unverified, may rotate).
- **Getting code on is SOLVED:** `./hub_programmer/upload.py <file> --apply` writes into `/flash/lib`
  over the REPL, verified by a SHA-256 the hub computes on itself. **No LEGO app, no compiler, no
  GCC, no Windows VM.** `./hub_programmer/run.py <file>` runs a program in RAM, leaving nothing.
- **Capture a baseline before writing to the hub.** `probes/capture_baseline.py --to /tmp/now` then
  `diff` against `docs/archives/hub-baseline/`. That habit is what makes "the firmware is untouched"
  provable instead of merely asserted.
- **Units:** `acceleration()` milli-g (1 g ≈ 989) · `tilt_angles()` **decidegrees**, yaw wraps ±180°.
- **Robot is BUILT: differential drive.** Port **A = LEFT wheel, B = RIGHT wheel** (both `device.id`
  48), rear unidirectional caster, colour sensors on **C and D** (`device.id` 61) mounted low. Motors
  are mirrored: **robot-forward = `A:-v, B:+v`.** Direct drive → **1 wheel rev = 360 encoder-deg**;
  distance = π × wheel-diameter (diameter still unmeasured). Max speed **930 dps** (measured).
  Confirmed by driving: [[../findings/drive-checkpoint-2026-09-01]].
- **docs-rag `/api/ask` WORKS** via `qwen3:14b` on skytracker — run `./scripts/sky-ollama.sh up` (needs
  ERAU VPN), then `curl .../api/ask -d '{"question":"..."}'` (~80 s). Not sub-5B; nothing pulled.
- **BLE and the REPL are mutually exclusive on one hub:** any probe's Ctrl-C interrupts the Hub OS,
  which owns the CONNECT button, BLE advertising, and the USB control-protocol responder — restart to
  recover. A **slot program** runs under the live Hub OS, so it can drive motors AND stream telemetry
  over BLE at once (the untethered path; `hub_programmer/slot_upload.py`, untested).
- **Three folders, three verbs:** `probes/` reads (read-only by contract) · `hub_programmer/` writes ·
  `examples/` discovers · `src/` runs on the robot. Never do discovery in `src/`.
- ⚠ **Never press-and-hold the CONNECT button while plugging in USB** — that is the DFU gesture.

---

## The one thing to remember

The design briefing was **verbal and there is no document** — stop looking for one. In full:
*"Build a mine sweeper robot that finds all the mines (I think yellow sticky notes) in a 10×10 area."*

**The open question that matters most: 10×10 in what units.** At 10 feet, exhaustive single-sensor
coverage is 125–204 m of driving (8–23 min) and the design must change, not the tuning —
[docs/findings/coverage-time-budget.md](docs/findings/coverage-time-budget.md). Also open: boundary type,
what "finds" means as a deliverable, and whether non-yellow decoys exist. All of it lives in
[docs/plans/questions-for-the-professor.md](docs/plans/questions-for-the-professor.md), to be asked in class.

## Standing constraints (do not re-litigate)

| Constraint | Why | Where |
|---|---|---|
| Stock LEGO firmware only; Pybricks blacklisted | Shared course equipment; a failed restore ends the project | [ADR-0001](docs/decisions/0001-stock-lego-firmware-only.md) |
| Hub OS treated as frozen until identified read-only | Opening the LEGO app can prompt an update | [runbooks/hub-identification.md](docs/runbooks/hub-identification.md) |
| Pure mission logic split from hub I/O | The hub is only available in class; logic must be testable on the laptop | [ADR-0002](docs/decisions/0002-split-mission-logic-from-hub-io.md) |
| Team *collaboration* is in-class; individual programming/design is not restricted | Operator's ruling 2026-08-25 — **not a blocker** | [scope.md § Critical Notes](docs/scope.md#critical-notes) |
| Git mutations are human-only | Standing rule across the operator's projects | [CLAUDE.md](CLAUDE.md) |

## Calendar (hard)

`25 AUG` Sprint 1 starts · `27 AUG` Sprint 1 · `1 SEP` Sprint 2 + mid-project survey ·
`3, 8 SEP` Sprint 2 · **`10 SEP` DEMO DAY** · `15 SEP` peer review + journal due ·
`18 SEP` Intro Report due (CSER 2022 Word template).

Roughly **five class sessions** for anything needing the robot, the team, or the store. Individual
programming and design work is not restricted to class time.

## Hardware status (2026-08-25)

- Hub: SPIKE Prime Technic Large Hub 45601. **Never connected yet.** Hub OS / API generation UNKNOWN.
- Store offers: motors **45602 large angular** / **45607 small angular**; sensors **45605 color**,
  **45604 distance**, **45606 force**. Prices can change — `inventory.py` records what was actually paid.
- **Owned:** 2 motors, 2 wheels (differential drive, team decision). **Not owned:** any sensor, mounting
  blocks, axles. Sensor mounting height/angle are still free variables — decide them from the research
  *before* buying.
- The team wants **color classification** of sticky notes, not just presence detection (scope FR-2b).

## Environment facts

- Host: Ubuntu 22.04, Python 3.10.12, pyserial 3.5, user in `dialout`, google-chrome installed, `screen`
  present but no `tio`.
- **`ModemManager` is active and enabled** — it will probe `/dev/ttyACM0` with AT commands and corrupt the
  first hub session. Neutralize it before first hub contact:
  [docs/findings/host-environment.md](docs/findings/host-environment.md).
- `earlyoom` is **inactive** and only ~3 GB RAM was free at init — throttle parallel agent/workflow
  spawning accordingly; do not assume host headroom.
- **docs-rag is DEPLOYED but only PARTIALLY WORKING** — `http://127.0.0.1:10060`, built from
  `~/exudeai/rag-bootstrap` 0.8.3 (current; we read it, never modify it).
  **Search: works.** **`/api/ask`: does NOT** (HTTP 500, no LLM pulled).
  **Operator's ruling 2026-08-26: that means it is NOT working.** The point of the docs-rag is to
  *offload tokens* — `ask` returns a synthesised answer, so the caller reads one short answer instead of
  reading and reasoning over chunks. Search alone only saves you *finding* the file. Do not call
  docs-rag "working" until `ask` answers.
  **The fix is NOT a local model.** `docs-rag/.env` names `llama3.2:3b`, but that is rag-bootstrap's
  *availability floor* — "chosen for footprint, not answer quality". **No sub-5B model for this**
  (operator ruling 2026-08-26), and `qwen3.5:9b` LOCAL is explicitly ruled out too: 6.3–6.6 GB on a 6 GB
  card spills 58–65 % to CPU, ~5 min/query. **The target is qwen3.5:9b running REMOTELY on skytracker**
  — which upstream names as the real quality unlock. So `/api/ask` is blocked on the ERAU VPN.
  **Never pull a generation model on initiative** — shared GPU is operator-gated.
  [ADR-0006](docs/decisions/0006-docs-rag-llm-is-operator-gated.md).
  **Temporary pass (operator, 2026-08-26): use search-only docs-rag anyway** — finding the right file in
  a 90-file tree is real value, and the VPN outage is not a reason to leave the tool idle.
  **Revocable; the operator will say when to stop.** The *status* is unchanged: still PARTIAL until
  `/api/ask` answers. Do not let permission-to-use drift into calling it working.
  [docs/runbooks/docs-rag.md](docs/runbooks/docs-rag.md).
- **ResearchHub is on pwnstar (10.231.80.91), port 5347** — discovered, not guessed. Reachable over
  ZeroTier with `~/.ssh/id_git`. `./scripts/rh-tunnel.sh up|status|restart|down` manages the tunnel and
  genuinely detects a stale one (tested by killing the ssh process: status → exit 3, restart repaired it).
  Search: `GET http://127.0.0.1:5347/api/discover/search?q=…`.
  [docs/runbooks/researchhub-tunnel.md](docs/runbooks/researchhub-tunnel.md).
- **Cost of the above: ~1.9 GB, almost all of it ollama's embedding model runner** (the four docs-rag
  containers are only ~143 MB combined). On a 15 GB host with ~4 GB free, that is the thing to stop
  first if memory gets tight.
- Docker was cleaned 2026-08-25: all other projects' containers stopped and removed, all images except
  `sam-scraper-*` deleted (~6.7 GB reclaimed). Volumes untouched.
- Upstream standards: `~/llm-project-bootstrap/` (PROMPTS.md, guides/, directives/, templates/).

## The three research tools — use them BEFORE reading files or guessing

This project has **97+ markdown files**. Reading them end to end is the wrong move and burns context.
All three of these work today:

| Tool | Command | Use it for |
|---|---|---|
| **docs-rag** | `RAG_ENDPOINT_URL=http://127.0.0.1:10060 python3 docs-rag/client/ragq.py -n 5 "question"` | Finding which of *our own* documents answers something. Returns `[[RAG:<path>#chunk]]` — open only that file, only that part. ⚠ **search only; `/api/ask` is broken** |
| **ResearchHub** | `./scripts/rh-query.sh "question"` — **never raw curl** | Academic literature. Repairs a stale tunnel itself; exit 3 = tunnel down, 4 = remote down, 5 = query failed, so an empty result is genuinely empty |
| **Web search / fetch** | the normal tools | Anything outside the repo and outside the literature — LEGO specs, library docs, part numbers |

Plus **12 papers already on disk** in `docs/research/papers/` with grep-able `.txt` sidecars and an
INDEX — check there before fetching anything new. `scripts/fetch_paper.py <url|doi|arxiv-id>` files a
new one properly.

**Every workflow brief must carry these instructions**, or agents read whole files and run out of context.
**Cite by path, never recopy prose** — that is a hard project standard.

**If a search 503s, ollama has died.** `./docs-rag/ollama-serve.sh` restarts it; `./scripts/stack.sh
status` says which of the four pieces is actually broken. It has died twice in one day — check it before
concluding a document is missing.

## Starting the stack — run this first, every session

Nothing here starts at boot, by design. One command brings it all up and proves it:

```bash
cd ~/sys301_minesweeper && ./scripts/stack.sh up      # or: status | down
```

What it does, in order — each step depends on the one before:

1. **Local ollama + `nomic-embed-text`** (`docs-rag/ollama-serve.sh`). **docs-rag search 503s without
   this** — and its `/api/health` still reports `embedding_service: true` while it is dead, so trust
   `stack.sh status` (which runs a real query) and never the health endpoint.
2. **docs-rag** — `http://127.0.0.1:10060`, semantic search over this repo's `docs/`.
   Re-ingest after writing docs: `docs-rag/rag ingest`.
3. **ResearchHub tunnel** to pwnstar over **ZeroTier** — `./scripts/rh-query.sh "question"` runs the
   preflight itself and repairs a stale tunnel automatically. Never raw curl.
4. **skytracker ollama** (optional, for a larger LLM) — `./scripts/sky-ollama.sh up`. Needs the
   **ERAU VPN**, which is a *different* network from ZeroTier. Forwards to local **11435** so it cannot
   collide with local ollama, and binds the docker bridge as well as loopback — a loopback-only forward
   is invisible to containers and docs-rag would fail with "All connection attempts failed".
   **UNTESTED as of 2026-08-26 — skytracker has never been reached.** The ERAU VPN authenticates then
   dies before installing routes (`RTNETLINK answers: File exists`). Ground truth each time: no `10.32.x`
   address, no `tun` device, no `openconnect` process, SSH times out. Try
   `sudo openconnect --background --script=/usr/share/vpnc-scripts/vpnc-script --user=<netid> dbvpn1.erau.edu`.
   **This blocks nothing** — docs-rag runs on local embeddings. Skytracker would only free ~1.9 GB and
   make `/api/ask` work. **Before switching docs-rag to it, confirm it has `nomic-embed-text`**: the index
   is 768-dimensional and a different embedder means a full re-ingest, not a config change.

`./scripts/stack.sh down` stops everything and frees ~1.9 GB — almost all of it ollama's model runner,
not the containers.

**Networks are spotty by design here** (the operator moves between them). Every tunnel script detects a
stale forward by making a real request, not by checking a PID, and repairs it. If something fails, run
`./scripts/stack.sh status` — it names which of the four is broken.

## Where things are

- **Source material from the course:** `docs/course/source-material/` — student instructions PDF, journal rubric HTML,
  example handwritten journal entry, CSER 2022 report template (`.docx` + `.pdf`).
- **Operator's raw platform notes:** `docs/archives/operator-notes/2026-08-25_spike-platform-notes.md`, `docs/archives/operator-notes/2026-08-25_available-sensors.md` (superseded by `docs/research/`).
- **Budget:** `./inventory.py` — live ledger, single source of truth. `--verbose` for a statement.
- **Everything else:** [docs/README.md](docs/README.md) is the map.

## Open questions held for the operator

- [ ] **"10×10" in what units** — the highest-leverage unknown in the project
- [ ] Boundary type (walls / tape / colored border / none) — decides whether we buy the distance sensor
- [ ] What "finds" means: a count, locations, stopping on each, retrieval
- [ ] Yellow only, or decoy colors present
- [ ] Demo Day time limit and scoring rule (all-of-them vs most-in-the-time pull opposite ways)
- [ ] Arena floor surface and whether we can practise on it
- [ ] Team member names and role assignments; confirm the operator is the **Programmer** `[ASSUMED]`
- [ ] Whether an official LEGO Hub OS update would be acceptable *if* identification shows we need one

Full list with rationale: [docs/plans/questions-for-the-professor.md](docs/plans/questions-for-the-professor.md)

**RESOLVED:** the out-of-class-work rule (not a blocker) · the design briefing (verbal, captured, partial)
