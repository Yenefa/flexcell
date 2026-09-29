# EXPERIMENTS — log

> One entry per experiment: purpose / scenario / configuration / result / evidence
> location. **Chat history is not experiment memory** — if a result is not recorded here
> (or linked from here), it did not happen. Benchmark (M3) numbers must regenerate from
> the replay store (#7/#8) — no hand-written PASS lines.

## Index

| ID    | Experiment                                                              | Outcome                  | Evidence                                                              |
| ----- | ----------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------------- |
| E-001 | Day-1 environment verification                                          | PASS                     | acceptance/day1 (delivery host) + [DAY1_REPORT.md](../DAY1_REPORT.md) |
| E-002 | Day-2 MoveToPose acceptance                                             | PASS 10/10               | acceptance/day2 + [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)            |
| E-003 | Week-1 deterministic skills battery                                     | PASS                     | acceptance/week1                                                      |
| E-004 | Week-1.5 demo hardening — delivery acceptance (att3)                    | PASS                     | acceptance/week15/delivery_20260926/                                  |
| E-005 | Week-1.5 cold-start re-verification                                     | PASS                     | acceptance/week15/cs_20260926/                                        |
| E-006 | M2.3 audit remediation — runtime acceptance                             | PASS (gated)             | acceptance/sessions/ (FLEXCELL_STAGE) + ~/.ros/flexcell/referee.jsonl |
| E-007 | Scenario runner batch (S1×2 + S2 + S5), episode replay                  | PASS                     | ~/.ros/flexcell/episodes/batch_20260928_051219.jsonl                  |
| E-008 | Metrics report over real store + S7 adaptation probe                    | PASS                     | ~/.ros/flexcell/episodes/batch_20260928_124615.jsonl                  |
| E-009 | New-machine (RTX 4060 laptop) bring-up + first official benchmark batch | SUPERSEDED (not citable) | setup/acceptance/m3_seed_batch_20260929*/                             |
| E-010 | T6 hardening: gate_flood + injection lifecycle + reset determinism      | PASS                     | this entry (measurements inline)                                      |
| M3-*  | Hybrid Agent Benchmark (cells A-D × S1-S7)                              | NOT RUN                  | — (RFC #15; harness #7/#8/#9)                                         |

## Entries

### E-001 — Day-1 environment verification

- **Purpose**: prove the ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2 + OpenMANIPULATOR-X
  stack end-to-end on the target machine.
- **Scenario**: Plan & Execute to a joint target; verify real motion in Gazebo physics.
- **Configuration**: WSL2 Ubuntu-24.04; Gazebo Harmonic 8.15.0; MoveIt 2; 6 colcon
  packages; 3 Gazebo controllers.
- **Result**: PLAN/EXECUTE error_code=1; MOTION_DETECTED=True; link poses move in
  physics; `/joint_states` consistent with the plan.
- **Evidence**: acceptance/day1/ (delivery host); [DAY1_REPORT.md](../DAY1_REPORT.md).

### E-002 — Day-2 MoveToPose acceptance

- **Purpose**: validate the agent-callable MoveToPose skill contract (typed request →
  MoveIt → Gazebo → measured result).
- **Scenario**: 10 cases — happy paths, timeout, cancel, IK-unreachable.
- **Result**: 10/10. Happy-path measured pose error 6-9 mm; timeout/cancel truly
  interrupt with `stop_confirmed`; IK fast-fail ≈ 1.06 s.
- **Evidence**: acceptance/day2/; [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md).

### E-003 — Week-1 deterministic skills

- **Purpose**: observe/pick/place/verify + strict FSM with measured-not-inherited
  success; typed negative paths.
- **Configuration**: conveyor-servo magnetic carry backend (see
  [ADR-001](ADR/ADR-001-simulation-manipulation-backend.md)); ground-truth truth loop.
- **Result**: full chain OBSERVE→PICK→PLACE→VERIFY SUCCEEDED with ground-truth error
  4.9-6.5 mm across runs; OBJECT_UNKNOWN / NOT_CARRIED / IK_UNREACHABLE /
  RESOURCE_BUSY all typed; Day-2 regression 10/10 (zero degradation).
- **Evidence**: acceptance/week1/ (18 artifacts).

### E-004 — Week-1.5 demo hardening (delivery acceptance, att3)

- **Purpose**: lifecycle CLI + strict health gate; dual-object A/B scenario; bounded
  recovery + fixed failure injection; repeatability.
- **Configuration**: recovery budget=1 (REOBSERVE+RETRY; recoverable = GRASP / MOTION /
  WORLD_STATE failures; otherwise typed abort); `/flexcell/inject`
  (`scenario:once\|always`); WorldState v1.5 frozen (`source=SIMULATION_GROUND_TRUTH`).
- **Result**: cold-machine run fully green — precheck 12 patterns all zero → start 34 s →
  happy demo 5.9/8.7 mm → double injection recovered → stop zero residue → poststop all
  zero. 5/5 repeats 2.5-10.6 mm; budget exhaustion → `ERR_RECOVERY_EXHAUSTED`; Day-2
  regression 10/10. att1/att2 servo-starvation failures were honestly caught (measured
  rise ≈ 0, zero false successes) — environment race, not code regression.
- **Evidence**: acceptance/week15/delivery_20260926/ (incl. `att1_att2/`).

### E-005 — Week-1.5 cold-start re-verification

- **Result**: run_id `week1_demo_v1-201be3fa`, 10.4/12.8 mm.
- **Evidence**: acceptance/week15/cs_20260926/.
- **Note**: `flexcell reset` may exit RC=139 (SIGSEGV) while reporting JSON `"ok":true`
  — vendor deserialize-thread/exit race; judge reset success by the JSON/health, not the
  exit code.

### E-006 — M2.3 audit remediation: runtime acceptance (2026-09-28)

- **Purpose**: verify the audit P0 fixes (ghost-trajectory guard, typed policy abort,
  cancel propagation, atomic admission) and the P1 acceptance infrastructure (colcon test,
  hard gates, independent referee, measured parity) under the live stack, headless.
- **Scenario**: happy demo + measured parity vs the frozen delivery baseline; referee ×5
  (independent gz-truth recompute of box_rise / zone_error cross-checked against the
  servers' jsonl); battery 61 (happy/recovery/exhaust/invalid) and battery 32 (10 cases)
  under hard gates; mutex probe (concurrent RunDemo+RunPickPlace); mid-pick cancel probe.
- **Configuration**: WSL2 Ubuntu-24.04 (headless: gz `-s`, no RViz), flexcell world;
  versioned `sessions/` dirs for artifacts.
- **Result**:
  - offline 86/86 (6 suites incl. new `test_runtime_guards`) and `colcon test` 86/0/0;
  - happy demo SUCCEEDED; measured parity vs `66_run_record_happy.jsonl` PASS;
  - exhaust → typed `ERR_RECOVERY_EXHAUSTED` (audit P1-2 acceptance); recovery →
    REOBSERVE+RETRY; invalid → typed negative (no catch-all wording);
  - mutex: second concurrent task → `ERR_RESOURCE_BUSY`; mid-pick cancel →
    `OUTCOME_CANCELED` + joint velocities ~0 after the stop;
  - battery 32: all 10 gates green (timeout/cancel details carry
    "preempted; stop confirmed"; MOTION_DETECTED=True);
  - referee: **zone_error agrees with the servers to ≤0.2 mm in every run** across all
    rounds; box_rise exposed a real mechanics finding — the teleport servo's set_pose
    requests succeed but the box reaches its pinned plateau seconds after the lift
    (carry engage unconfirmed; audit P2). The referee was re-scoped as an INTEGRITY
    check (overclaim / fake-grasp detection) with the catch-up delta logged as the D4
    monitoring metric; two INCONSISTENT verdicts in the final round were genuine demo
    failures (natural carry flake → typed BUDGET_EXHAUSTED policy abort, exercising the
    P0-2 path end-to-end) — detected, not masked.
- **Evidence**: `$FLEXCELL_STAGE/setup/acceptance/sessions/` (versioned session dirs);
  `~/.ros/flexcell/referee.jsonl`.
- **Open**: box_rise two-sided referee agreement is blocked by the carry-servo
  catch-up variance — contact grasping (D4) is the structural fix; the demo result
  detail prints `zone_%s_error_m` as 0.0000 while verify measures mm-scale (verify
  sampling moment to be checked in hardening).

### E-007 — Scenario runner batch: S1×2 + S2 + S5 with episode replay (2026-09-28)

- **Purpose**: close issue #7 — the scenario runner orchestrates reset → injection →
  demo/task → episode collection → offline policy-input replay → batch summary, with
  Wilson-CI success reporting (metric #1).
- **Configuration**: headless stack, flexcell world; batch `S1:2 S2:1 S5:1`;
  policy = FSMPolicy (replay of every recorded decision).
- **Result**: SCENARIO RUNNER PASS — S1 2/2 SUCCEEDED (CI95 [0.34, 1.00]), S2
  (injected first-attempt failure, recovered) 1/1 SUCCEEDED, S5 (retry exhaustion)
  FAILED as expected with the typed abort; **all 4 episodes replayed with 0 diverged
  decisions** (8/10/12/5 steps). Batch summary:
  `~/.ros/flexcell/episodes/batch_20260928_051219.jsonl`.
- **Evidence**: batch summary jsonl + the episode files it references.

### E-008 — Metrics report over the real store + S7 adaptation probe (2026-09-28)

- **Purpose**: close issues #8 (metrics report generator) and #9 (S7 perturbation
  builder).
- **#8**: `setup/95_metrics_report.py` regenerates every number from the replay store —
  per-cell success rate with Wilson 95% CI, decision-latency percentiles (metric 3),
  safety invalid-per-1000 (metric 6), and replay integrity per episode (planted-
  proposal records classified as gate evidence, excluded from the integrity
  denominator). Verified on the full store (21 episodes incl. dev iterations, kept in
  a separate `dev/*` bucket so they can never pollute a cell) and on the E-007 batch:
  both REPORT: PASS. Primitives in `contracts/metrics.py` (6 unit tests).
- **#9**: `setup/96_s7_perturb.py` — seeded off-canonical box placement inside the
  reachable band (geometry priors: ground plane, x∈[0.16,0.28], |y|≤0.24, ≥0.12 m
  separation, off zone centres), applied via the gz set_pose service; the runner
  attaches the schedule to the batch row. S7:2 batch → SCENARIO RUNNER PASS: both
  off-canonical demos SUCCEEDED (the deterministic baseline adapts to perturbed
  placement — the expected S7 outcome per ratified ⑥) with 0 diverged replay steps.
  Batch summary: `~/.ros/flexcell/episodes/batch_20260928_124615.jsonl`.
- **Evidence**: episode store + both batch summaries; report text in the issue
  comments.

### E-009 — New-machine bring-up + first official benchmark batch (2026-09-29)

- **Purpose**: bring the RTX 4060 laptop to a verified workcell per
  [REPRODUCE.md](../REPRODUCE.md) and produce the **first M3-seed benchmark
  numbers** on a real store (S1/S2/S5/S7 × 20/20/20/10, policy = FSMPolicy,
  `decision_policy=fsm` verified from the live startup banner).
- **Machine**: i5-13500H / 16 threads / 16 GB, WSL2 Ubuntu-24.04, `.wslconfig`
  memory=10GB + swap=16GB (WSL saw 7 GB before, 9 GB after). **No hardware GL in
  WSL** — the Windows NVIDIA driver is not installed (WMI shows only Intel UHD,
  `nvidia-smi` → `Failed to initialize NVML`), so WSLg falls back to llvmpipe.
  All runtime verification was therefore **headless** (two machine-local patches,
  neither a repo change: `' -s'` added to the upstream gz launch args in the
  gitignored `src/`, and `start_rviz:=false` in the `/tmp/flexcell_cli` copy).
  Proof per run: `pgrep -af '[g]z sim'` shows the server only, `rviz2` count 0.
- **Build/test baseline reproduced**: `colcon build` (4 workers) upstream exit 0
  - flexcell exit 0; `colcon test` → **130 tests, 0 errors, 0 failures, 0
    skipped**. `rosdep update` failed 12/12 (WSL egress flakes to
    `raw.githubusercontent.com`, plus an `EE certificate key too weak` intercept)
    → **dependency closure NOT_VERIFIED** (same caveat as the delivery host,
    workspace WSL-001); the closure is evidenced by build + tests + runtime.
- **Three real defects found and fixed** (all in-repo, all blocking):
  1. `setup/flexcell_admin.py` used `os.environ` without ever importing `os`
     (missing since `d3c2d04`) → every `health`/`reset` died with `NameError`,
     so the CLI's skill-fleet readiness gate could **never** pass and
     `flexcell start` always failed. The working copy only existed in the
     delivery host's F: staging, which is now unreachable. After the one-line
     fix: strict health **17 checks `ok: true`, `hard_fail: []`**.
  2. `95_metrics_report.py` had no `s7_perturb_v1 → S7` mapping, so the S7 cell
     silently degraded into a `dev/*` bucket. Mapping added; the report now emits
     a real `## Cell S7`.
  3. `94_scenario_runner.py::arm_inject` guarded on `if payload:`, which made the
     **empty** payload a no-op — so the runner's post-episode "always clear" never
     reached the client and an armed `once`/`always` injection stayed live for
     every later episode of the batch. Measured effect: with S5 before S7, all 10
     S7 episodes were pre-failed by the leftover `exhaust_demo_v1:always`
     injection (0.52 s episodes, `err=23`, no motion). Now `if payload is None:
return`, and the pick server log shows the clear landing
     (`failure injection DISABLED`). This is why the delivery-host batches never
     caught it: E-007 put S5 last, E-008 ran S7 alone.
- **First batch (superseded, kept as defect evidence)** —
  `setup/acceptance/m3_seed_batch_20260929/`: S1 16/20 = 0.80
  CI95 [0.58, 0.92] · S2 13/20 = 0.65 [0.43, 0.82] · S5 0/20 SUCCEEDED
  (= 20/20 correctly FAILED, typed) · **S7 0/10 = 0.00 [0.00, 0.28] — invalid,
  pre-failed by defect 3**. `REPORT: PASS (70 episodes, 0 replay-dirty)` — note
  the reporter's verdict is _replay integrity_, not outcome correctness; the
  runner's own verdict was `FAIL (21)`.
- **Clean batch** — `setup/acceptance/m3_seed_batch_20260929_clean/`, run as four
  independently resumable per-cell segments (the WSL VM restarted twice mid-batch
  and killed the detached runner, so the batch was re-planned into
  S1/S2/S5/S7 segments whose row files merge into one `batch_merged.jsonl`;
  partial attempts sit in the store but in no row file, so they cannot enter the
  report). Every number below is regenerated by `95_metrics_report.py` from the
  replay store over `batch_merged.jsonl` (70 rows); the report is committed
  verbatim as `95_metrics_report.md`.

  | Cell | Scenario                        | success (metric 1)                                                       | Wilson 95% CI       | replay integrity |
  | ---- | ------------------------------- | ------------------------------------------------------------------------ | ------------------- | ---------------- |
  | S1   | canonical happy demo            | 18/20 = **0.90**                                                         | [0.70, 0.97]        | 20/20 clean      |
  | S2   | injected failure, first attempt | 8/20 = **0.40**                                                          | [0.22, 0.61]        | 20/20 clean      |
  | S5   | retry exhaustion                | 1/20 SUCCEEDED → 19/20 correctly FAILED (typed `ERR_RECOVERY_EXHAUSTED`) | [0.01, 0.24]        | 20/20 clean      |
  | S7   | off-canonical placement         | 6/10 = **0.60**                                                          | [0.31, 0.83] ⚠ n<20 | 10/10 clean      |

  `REPORT: PASS (70 episodes, 0 replay-dirty)`, 0 `dev/*` buckets (S7 is a real
  cell again). Row-level: 70 rows, 19 outcome mismatches, **0 replay-dirty**.
  Runner verdict per segment: `S1 FAIL (2)`, and S2/S5/S7 likewise non-zero
  because the deterministic baseline missed the expected outcome — that is the
  measurement, not a harness fault.

- **S7 recovered from 0/10 to 6/10 once defect 3 was fixed** — direct evidence
  that the first batch's S7 collapse was the leftover injection, not the
  perturbation: the deterministic baseline does adapt to off-canonical placement
  (the expected S7 outcome per ratified ⑥), it just has to survive the same
  intermittent servo failure as S1.
- **S2 is the weak cell and the reason is physical**: all 12 S2 failures are
  `BUDGET_EXHAUSTED` from the grasp failure (8 succeeded with
  `demo done: A->zone_1 (0.0000m), B->zone_2 (0.0000m)`), i.e. S2 pays the servo
  failure twice over — it needs two successful picks _and_ a recovery leg. S1
  (0.90) vs S2 (0.40) is the honest per-pick reliability gap on this machine.
- **One S5 episode succeeded when it should have exhausted** (run 20,
  `dabdd93d`): its `fsm_trace` is
  `PICK_A(attempt=1):OK, PLACE_A:OK, VERIFY_A:OK, PICK_B:OK, PLACE_B:OK,
VERIFY_B:OK` with `error_code 0` — i.e. **the `always` injection was never
  armed for that episode**, not a policy error. The arming rides a transient
  topic publisher (`w1_client` publishes 5× over ~1 s then exits) and the client
  _does_ print `INJECT WARNING: no subscriber matched; payload may be lost`, but
  `arm_inject` uses `capture_output=True` and never checks it, so a lost arm is
  silent. Consequence for the numbers: S5's failure path is n=19, and injection
  arming is currently **unverified by construction** — worth a follow-up (assert
  on the client's warning, or make arming an action/服务 call instead of a topic).
- **Environment caveat that applies to every number above**: no hardware GL in
  WSL (llvmpipe), so all runs are headless; load ~10-12 on 16 threads; the carry
  servo intermittently fails to lift (`box_rise_m ≈ -0.001..-0.004`,
  `inj=None`), which is the declared teleport-servo compromise, not new
  degradation. The delivery host's frozen Week-1.5 baseline was produced under
  different conditions (GPU-accelerated, 12 cores) — the success rates here are
  **not** directly comparable to it, and the CI widths (±19 pp at n=20) dominate
  the run-to-run variance.
- **Dominant failure mode of the machine (not a code defect)**: the carry servo
  intermittently fails to lift the box — `box_rise_m ≈ -0.001..-0.004` →
  `ERR_GRASP_FAILED` → (with budget 1) `ERR_RECOVERY_EXHAUSTED`. Confirmed
  _physical_, not injected, from `pick.jsonl` (`inj=None`). This is the declared
  teleport-servo compromise ("magnetic ≠ contact grasping") showing up as a
  measurable success-rate ceiling, and it is the honest headline number for S1/S2
  on this machine. Idle CPU profile (6 s `/proc` deltas, not a `top` snapshot):
  each of the 6 skill servers ~70-92 % (each holds a persistent Python subscriber
  to the high-rate gz `dynamic_pose/info` topic), gz sim 103 %, move_group 25 %
  → 7.15 of 16 cores busy.
- **NOT_RUN / explicitly out of this session's scope**: S3 (absent from the
  runner entirely), S4 (`RunPickPlace` records no episode and is off the policy
  seam — see `docs/ISSUE_DRAFTS_20260929.md` A), the Day-2 battery
  (`setup/32_day2_acceptance.sh`), the independent referee run
  (`setup/92_referee.py`), any Jev/LLM arm, and the M2.3 flood gate (see B).
- **Open integrity findings** (not fixed here, evidence in
  `docs/ISSUE_DRAFTS_20260929.md` B/C): the `gate_flood` zero-traceback gate has
  **never** been green — the committed delivery-host reset artifacts carry the
  same ~1000-count `gz.msgs.Pose` flood (1016 / 1030 / 964 / 963), so the M2.3
  "pb2 registration fix in place" claim is unsupported; and `flexcell_admin.py
reset` does not restore the canonical world after an abort-while-carrying
  (`scene_cleared: false`, `target_box_a: DRIFT [0.282, 0.001, 0.028]`), which is
  why the batch was gated on a verified-canonical world before starting.

### E-010 — T6 hardening: gate_flood, injection lifecycle, reset determinism (2026-09-29)

- **Purpose**: chief ruling 2026-09-29 — _"otherwise stop citing benchmark
  numbers"_. Three P0 items had to be fixed and measured before any cell number
  could be quoted: the never-green `gate_flood`, the unverified injection
  lifecycle, and the non-restoring reset. E-009 is demoted to **not citable**
  because all three measurement-path defects were live during it.
- **Offline baseline**: `colcon test` **130 → 153 tests, 0 failures**
  (+7 `test_gz_stream.py`, +16 `test_injection.py`).

#### ① gate_flood — the `gz.msgs.Pose` traceback flood

- **What it was**: `for ent in msg.pose` inside the gz Pose_V callback raised
  `TypeError: No message class registered for 'gz.msgs.Pose'`, and
  gz-transport's python shim prints a **full traceback per message**. Measured
  4-reset baseline: **954 / 895 / 896 / 899** lines on _stdout_ (fd 2 was
  /dev/null — the shim's `sys.stderr` is a wrapper on fd 1 in this process), and
  3 of 4 runs also **segfaulted at exit** (rc=139).
- **Root cause work**: only `gz.msgs10` + `gz.transport13` exist in this
  environment, so the "version pairing" theory was wrong; the pb2 registration
  import (`common.py:67`) was already present and, tested in isolation, made no
  difference (4 import combinations, and transport-before-msgs ordering, all
  clean). It reproduces only after the first `set_pose` round-trips, i.e. in the
  reset process. **The precise trigger was not isolated** — reported as such
  rather than guessed at.
- **Fix**: the callback can no longer raise. `_on_pose_v` folds a message and
  **counts** any failure (`cb_errors` / `cb_error`, exposed via
  `gz_stream_health()`), a failing stream never updates `last_rx` so the
  existing staleness self-heal rebuilds it, and the previous gz node is
  unsubscribed on rebuild instead of leaking. Registration moved to module
  import (main thread, once) so it is deterministic.
- **Result — same 4-reset baseline: flood 954/895/896/899 → 0/0/0/0, exit
  139×3 → 0×4, stdout 407–433 kB → 623 B and now parseable JSON.** A bonus
  effect: the admin's "JSON" output was never valid JSON before, because the
  tracebacks shared the stream.

#### ② Injection lifecycle — requested / armed / applied / cleared

- **What it was**: fire-and-forget on a topic. A request that never landed was
  invisible (1 S5 episode of 20 SUCCEEDED with `error_code 0` and an all-OK
  `fsm_trace`, because its `always` injection never armed), and a request that
  _did_ land was never cleared (E-009 S7 0/10).
- **Fix**: new pure contract `contracts/injection.py` (`InjectionLifecycle`,
  `parse_request`) — four states, per-`(scenario, object)` attempt counting with
  the frozen `once` semantics, a bad payload stays `requested` with a recorded
  `error` instead of being ignored, and a clear resets the counters. The pick
  server publishes a latched snapshot on every transition;
  `w1_client.py --expect-inject-state … --inject-request-id …` **seals** the
  step and exits 3 if the transition is not observed; the runner now checks that
  exit code, records `inject_arm`/`inject_clear`/`harness_error` per row, and
  turns an unarmable request into a `HARNESS_ERROR` episode that is excluded
  from the success denominator but fails the batch.
- **Result (live)**: arm → `state=armed` rc 0; clear → `state=cleared,
live=false` rc 0; **negative** `bogus:sometimes` → seal fires, **rc 3**;
  `S5:3` → 3× FAILED as expected with `arm=armed sealed clear=cleared sealed`,
  **0 HARNESS_ERROR**, RUNNER PASS; `S1:2` immediately after → 2/2 SUCCEEDED,
  RUNNER PASS (the cross-cell leakage of E-009 S7 is closed).
- One bug was caught _by the seal itself_ during acceptance: the status
  publisher was VOLATILE while requesters subscribe TRANSIENT_LOCAL →
  "incompatible QoS … DURABILITY", so no transition was ever observable. Fixed
  by latching the publisher.

#### ③ Reset determinism — `scene_cleared: false` / `DRIFT`

- **What it was**: the stop was published only `if engaged`, and `engaged` came
  from the latched `CarryState` — a topic that goes **silent** when the state
  never changes. A wedged carry servo (logged `ENGAGED`, publishing nothing)
  therefore read as "not engaged": the stop was never sent, the reset reported
  `carry_disengaged: true`, and every `set_pose` was overwritten at 10 Hz.
  Measured: `target_box_a` stranded at **[0.2782, 0.0028, 0.0222]** = EE +
  logged offset, with `set_pose` returning `True` three times and the box never
  moving.
- **Fix**: publish the carry stop **unconditionally** and confirm it; decide
  `carry_disengaged` on **behaviour** (a pinning servo cannot let a box hold a
  commanded pose) with the latched state as corroboration only; retry the stop
  and the pose once when a box refuses its commanded pose; decide
  `scene_cleared` by **re-querying the scene** instead of trusting the
  `ApplyPlanningScene` response flag (a REMOVE naming an already-absent id makes
  move_group answer `success=false`); and widen the `task_idle` wait from 5 s to
  15 s while distinguishing "never received" (DDS discovery; measured 1.54 s) from
  a genuinely busy task.
- **Result**: the stranded box was restored to canonical `[0.2200, 0.0000,
0.0175]`, and **3× abort-while-carrying → reset plus 3 plain resets all
  `ok=true`** with both boxes canonical, `scene_cleared: true`, carry disengaged
  (previously `ok=false` + DRIFT every time).

- **Not done here**: the underlying reason a PLACE failure leaves the box grasped
  is _correct_ behaviour (the box is still in the gripper); the reset releasing
  it is the fix. Making the executor release on abort is a separate change and is
  left open. S3/S4 (P1) and the n≥20 re-run are the next steps.

## Evidence locations

- Delivery host: `F:\flexcell-stage\setup\acceptance\{day1,day2,week1,week15}\`
- Per-request structured logs: `~/.ros/flexcell/*.jsonl` (WSL; `evidence_id` per record)
- Lifecycle transcripts: flexcell CLI outputs (same acceptance dirs)
- Repo-side records: [DAY1_REPORT.md](../DAY1_REPORT.md),
  [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)

> **Open (infra)**: acceptance evidence currently lives only on the delivery host. Decide
> whether key evidence bundles are copied into the repo (or an evidence branch) so the
> repository is fully self-contained — chief decision.
