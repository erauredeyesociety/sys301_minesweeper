# Research / Papers — INDEX (EXTERNAL, primary literature)

The project's academic paper corpus: **12 openly-available papers**, fetched 2026-08-26.

**How this directory works.** PDFs are **gitignored** ([.gitignore](./.gitignore)); the `.txt` sidecars
and this INDEX **are tracked**, so `grep` over the corpus keeps working for anyone who clones the repo
without carrying 46.8 MiB of PDFs. Full per-paper citation records live in
[bibliography.md](./bibliography.md), appended by [`scripts/fetch_paper.py`](../../../scripts/fetch_paper.py).

**Cite, never recopy** ([../../directives/documentation-discipline.md](../../directives/documentation-discipline.md)).
Grep the sidecar, cite the entry, quote sparingly.

```bash
grep -n -i "boustrophedon" docs/research/papers/*.txt      # search the whole corpus
```

**Every sidecar in this corpus has a real text layer** — no image-only scans. Checked 2026-08-26 by
opening all 12 and confirming each begins with its own title/author block (smallest is `wong2003`, 698 lines).
(For contrast, the Choset 2001 survey noted in [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md)
is an image-only scan at its host and is therefore **NOT** in this corpus.)

**Provenance re-checked 2026-08-26 (audit).** Every arXiv ID in [bibliography.md](./bibliography.md) was
confirmed against the arXiv stamp printed inside the corresponding PDF, and the four non-arXiv **Source**
URLs were re-fetched: `paper59`, `paper60`, `hellgren2024` and `wong2003` returned files **byte-identical**
to the local copies, and `dugi-doc.udg.edu` returned `Content-Length: 8536616`, matching `galceran2013`
exactly. No source URL is dead or points at a different document.

## The corpus

The last column is the point of this file: it turns a pile of PDFs into a bibliography. **CITED** means
the document already leans on this work and the citation is now backed by a local copy. **SHOULD CITE**
means the paper is new to the project and the named document is where it belongs — those documents are
owned by another agent and were **not** edited by this pass.

| Key | Title | Year | What THIS project uses it for | Cited by |
|---|---|---|---|---|
| [borenstein1995-umbmark-benchmark](./borenstein1995-umbmark-benchmark.txt) | UMBmark: A Benchmark Test for Measuring Odometry Errors in Mobile Robots | 1995 | The calibration run we actually intend to perform (5 cw + 5 ccw squares, 4×4 m, stop at each corner — sidecar lines 440–462). Its Table I is a *six-vehicle survey*, **not** the before/after improvement table — that is in borenstein1995b below | **CITED** — [../motion-control-and-odometry.md](../motion-control-and-odometry.md) · [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) · [../../runbooks/measure-drivetrain.md](../../runbooks/measure-drivetrain.md) |
| [borenstein1995b-systematic-odometry-correction](./borenstein1995b-systematic-odometry-correction.txt) | Correction of Systematic Odometry Errors in Mobile Robots | 1995 | The correction **algebra** — α, β, `Ed`, `Eb`, `cL`, `cR`. paper60 says what to measure; this says what to do with it. **This** is the true source of the **10–22× systematic-error reduction** claim: its Table I (sidecar lines 585–620) lists eight experiments at 15, 11, 10, 22, 12, 11, 21, 19-fold. Caveat before quoting the top end: experiment #7 reached 21-fold only after a **second** compensation pass — its single-pass result was 6.4-fold | **CITED** — [../motion-control-and-odometry.md](../motion-control-and-odometry.md) · [../../runbooks/measure-drivetrain.md](../../runbooks/measure-drivetrain.md) |
| [galceran2013-coverage-path-planning-survey](./galceran2013-coverage-path-planning-survey.txt) | A Survey on Coverage Path Planning for Robotics | 2013 | Primary taxonomy source: exact cellular decomposition, the boustrophedon completeness guarantee, and **§10 coverage under localization uncertainty** — the honest answer to "our robot has no global position" | **CITED** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) |
| [wong2003-topological-coverage](./wong2003-topological-coverage.txt) | A topological coverage algorithm for mobile robots | 2003 | The sim-to-real gap we set expectations from: **99.8 % / 99.2 % in simulation, ~85 % on a real Khepera** | **CITED** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) |
| [hellgren2024-vacuum-coverage-comparison](./hellgren2024-vacuum-coverage-comparison.txt) | Comparison of Coverage Algorithms for Robot Vacuum Cleaners in Cluttered Environments | 2024 | Empirical random-walk vs systematic (BA\*) comparison — the basis for rejecting random sweeping on a mission that must **count** mines, not merely visit area. **Weakest source in the corpus: a KTH BSc degree project (15 credits), not peer-reviewed.** It is load-bearing for that rejection, so state its level when citing it, or lean on Galceran's completeness argument instead | **CITED** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) |
| [jonnarth2023-learning-coverage-paths-rl](./jonnarth2023-learning-coverage-paths-rl.txt) | Learning Coverage Paths in Unknown Environments with Deep Reinforcement Learning | 2023 | Problem framing and coverage metrics only. Deep RL is **out of scope** for a two-week SPIKE build — lowest direct use in the corpus | **CITED** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) |
| [krupke2023-coverage-turn-costs](./krupke2023-coverage-turn-costs.txt) | Near-Optimal Coverage Path Planning with Turn Costs | 2023 | Turns are this robot's weakest motion — two point turns per lane, each spending time and injecting heading error. Formal treatment of **turn cost as a first-class objective**. What it actually shows and we may cite: raising the turn weight pushes optimal tours toward *longer straight lines and fewer turns*, at the cost of redundancy (Fig. 2). It does **not** prescribe long-axis lanes for a rectangle — our long-axis choice is our own inference from that trend, and must be labelled as such | **SHOULD CITE** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) § Coverage pattern comparison · [../../findings/coverage-time-budget.md](../../findings/coverage-time-budget.md) |
| [fourney2024-sensory-coverage-efficiency-bounds](./fourney2024-sensory-coverage-efficiency-bounds.txt) | Mobile Robot Sensory Coverage in 2-D Environments: An Optimization Approach with Efficiency Bounds | 2024 | Optimises the **order and viewpoints for observing discrete targets** with a limited-range sensor, with bounds on the approximation gap; the robot's **sensor footprint**, not its body, is the constraint. It names **mine sweeping** as a motivating application (sidecar line 33). It does **NOT** contain lane-spacing-vs-footprint theory (`L` vs `W`) — cite it for the footprint-as-primitive framing only, and keep `L` vs `W` marked as argued from first principles | **SHOULD CITE** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) (lane spacing / detection probability) |
| [shah2025-lawnmower-cellular-decomposition](./shah2025-lawnmower-cellular-decomposition.txt) | End-to-End Framework for Robot Lawnmower Coverage Path Planning using Cellular Decomposition | 2025 | Closest published analogue to what we are building: boustrophedon lanes from cellular decomposition on a real ground robot. An existence proof that our pattern is the standard answer, not our invention | **SHOULD CITE** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) § Coverage pattern comparison |
| [shen2026-coverage-path-planning-survey-2026](./shen2026-coverage-path-planning-survey-2026.txt) | Coverage Path Planning: Classical Foundations, Recent Advances, and Future Directions | 2026 | Current survey; the companion to Galceran 2013 for anything published since. For the Intro Report's background section | **SHOULD CITE** — [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) · Intro Report background |
| [nutalapati2020-wheeled-robot-odometry-calibration](./nutalapati2020-wheeled-robot-odometry-calibration.txt) | A Generalized Framework for Autonomous Calibration of Wheeled Mobile Robots | 2020 | Modern counterpart to UMBmark. Cite when justifying **why** we calibrate wheel diameter and track width instead of trusting geometric values | **SHOULD CITE** — [../motion-control-and-odometry.md](../motion-control-and-odometry.md) · [../../runbooks/measure-drivetrain.md](../../runbooks/measure-drivetrain.md) |
| [niu2019-wheel-mounted-imu-dead-reckoning](./niu2019-wheel-mounted-imu-dead-reckoning.txt) | Wheel-INS: A Wheel-mounted MEMS IMU-based Dead Reckoning System | 2019 | Drift behaviour of a low-cost MEMS IMU in dead reckoning. **CAVEAT: the IMU is wheel-mounted, ours is in the hub** — the mechanisms transfer, the numbers do NOT. Qualitative claim only, never a drift rate | **SHOULD CITE** — [../motion-control-and-odometry.md](../motion-control-and-odometry.md) § gyro drift, *with the mounting caveat stated* |

## Honest gaps — what we could not get

| Wanted | Outcome |
|---|---|
| **Choset, "Coverage for robotics — a survey of recent results" (2001)** | The CMU RI copy is an **image-only scan with no text layer**. Not fetched: a sidecar-less PDF cannot be grepped and would be dead weight. Galceran 2013 restates its taxonomy and is in the corpus instead |
| **Gabriely & Rimon, Spiral-STC (primary papers)** | ScienceDirect / ACM / Springer — **paywalled**. Not bypassed. Spiral-STC is described second-hand via Galceran §6.2, and [../detection-and-sweep-techniques.md](../detection-and-sweep-techniques.md) already rejects it for this robot |
| **Acar & Choset (2002), boundary-following coverage** | Paywalled. Reachable only through Galceran §10's summary |
| **Bretl & Hutchinson, guaranteed coverage under bounded error (ICRA)** | Paywalled. Same — summarised via Galceran |
| **A quantified drift figure for the SPIKE Prime hub IMU specifically** | **Does not exist in the literature.** No academic source measures this hub. Per the operator's standing guidance, the deliverable is the *procedure that measures it* on our own hardware, not a borrowed number |
| **Detection-probability / sweep-width theory for a downward robot sensor** | ResearchHub returns only **land search-and-rescue** sweep-width literature (human searchers, not robot sensors). Judged not transferable; Fourney 2024 is the closest usable substitute |

## Provenance notes

- 11 of 12 fetched with `python3 scripts/fetch_paper.py <arxiv-id|url>`.
- **`hellgren2024`** needed a **direct `curl` fallback**: `diva-portal.org` exceeds the fetcher's 30 s
  `TIMEOUT` and failed twice. Sidecar produced manually with `pdftotext`.
- **`wong2003`** — the host filename (`spiral_stc_...pdf`) **mislabels this paper**: the PDF's own first
  page reads *"A topological coverage algorithm for mobile robots · Sylvia C. Wong · Bruce A. MacDonald"*.
  The 2003 IROS year comes from an **external record**, not from the PDF, which carries no date; its
  newest internal reference is 2002. Treat the year as **UNVERIFIED**; author and title are verified.
- **`borenstein1995b` was renamed from `borenstein1996`** (audit, 2026-08-26). The PDF's own header line
  reads *"Proceedings of the 1995 International Conference on Intelligent Robots and Systems (IROS '95),
  Pittsburgh, Pennsylvania, August 5-9, pp. 569-574"* — it is a 1995 paper, and the old key would have
  led the Intro Report to cite the *different* 1996 IEEE T-RA article of a similar name.

## Size

Measured with `stat`, 2026-08-26. MiB = 1024², KiB = 1024.

| | Bytes | |
|---|---|---|
| PDFs (**gitignored**, 12 files) | 49,089,154 | **46.8 MiB** |
| `.txt` sidecars, 12 files (**tracked**) | 838,823 | **819.2 KiB** |
| Everything tracked here (sidecars + `INDEX.md` + `bibliography.md` + `.gitignore`) | — | **~843 KiB** |

Nothing here is committed until the operator runs the git commands — git mutations are human-only.
