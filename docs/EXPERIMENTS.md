# EXPERIMENTS — log

> 2026-10-07 CORE-001: bounded RunComposite action uses the existing policy/Skill
> seam and one common arm admission lease throughout all stages. One registered
> Hybrid swap and one S1 regression completed; 4 native episodes, Clef 9/0 on the
> target and 6/1 on S1, 30 confirmed controller terminals. 300 skills and 42
> instrument/audit tests passed. The original driver exited 1 at exact float
> comparison; its failure and auditor are retained, with a read-only nine-decimal
> serialization correction and completion of the single already registered S1.
> No target resampling, prompt/calibration change or large-batch unfreezing.
> [API receipts and limits](../setup/acceptance/composite_api_20261007/README.md).

> 2026-10-06 TransferBench T3 (TB-003): registered one buffer-assisted B/A/B swap
> and one S1 regression per arm. FSM and Hybrid each completed 1/1 + 1/1; 8 native
> episodes, 60 successful controller goal terminals, no quarantine or resampling.
> Clef selected all 9 target decisions; S1 used Clef 6 / DeepSeek 1. A common fixed
> outer dependency executor was added (352 code lines + 59 registration-time test
> lines); partial development elapsed is not full human engineering cost. 36
> instrument tests passed. [Composite/native receipts and cost boundaries](../setup/acceptance/transferbench_t3_20261006/README.md).
> AC@90, physical safety and n≥50 remain frozen.

> 2026-10-06 school startup health (NET-001): actual DERP(tok) relay; legacy 2s
> TCP probe failed while explicit 10s probe completed in 2.337s. A deployment-scoped
> helper and manifest field preserve unchanged prompt/calibration identity; 12
> targeted tests and 260 skills pytest passes. Mirrored networking and proxy config
> retained; direct-connect root cause UNKNOWN and network stability NOT_ACCEPTED.
> [Diagnostics, failure preservation and runtime activation](../setup/acceptance/startup_health_20261006/README.md).

> 2026-10-06 TransferBench T1 pilot (TB-002): pre-registered two new layouts and
> one S1 source regression per arm, from d58f4f1; FSM 2/2 + 1/1, Hybrid 2/2 + 1/1.
> Frozen task/Skill sources were reused by both arms. Hybrid selected Clef 18 times
> and DeepSeek twice; paid peak-uncached upper bound ¥0.007024, invoice UNKNOWN.
> Human effort and common harness authoring cost NOT_RUN. The v1 scorer misread
> serialized outcome "0" as failure; all six raw FAILED receipts remain, with a
> separate post hoc schema-correction report and no resampling. 30 targeted tests
> passed. Startup/follow-up TCP timeouts retained, cause UNKNOWN; AC@90, physical
> acceptance and n≥50 remain frozen. [Plan, raw receipts and v2 correction](../setup/acceptance/transferbench_t1_20261006/README.md).

> 2026-10-06 TransferBench instrumentation (TB-001): official methodology review,
> layered migration-cost design, and an offline cost ledger; 18 targeted unit tests
> passed. The CLI fixture is SYNTHETIC_TOOL_FIXTURE, with no robot/API invocation.
> Migration experiments, AC@90 and physical safety acceptance are NOT_RUN; n≥50
> remains frozen. [Design](TRANSFER_BENCHMARK.md) and
> [immutable receipt](../setup/acceptance/transferbench_foundation_20261006/README.md).

> 2026-10-05 Gazebo 退出与 reset RPC 修复（E-020）：core 确认 callback 析构/GIL
> 与 Python finalization 竞态；引用释放屏障后启停 100/100、reset 20/20。
> 另一个 RPC 进程卡住经新进程对照定位，隔离恢复后 reset 再次 20/20
> （80 命令/81 请求、1 次恢复均留记录），全量 226 tests passed。
> 新指纹 τ=0.03 smoke 5/5、先导 18/20；τ=0.85 smoke 4/5，n=20 阻断。
> 新执行 30 回合无 harness/来源错误，3 次 B 抓取失败保留；n≥50 冻结。
> [故障范围、对照与新指纹资格结果](Q8_TEARDOWN_20261005.md)。下条为修复前历史。

> 2026-10-05 Q8 路由先导（E-019）：实际校准加载与逐决策证据门禁通过，215 tests passed；
> τ=0.85 smoke 5/5，计划 n=20 的先导实际 14/17 + 1 reset HARNESS_ERROR 后停批；
> τ=0.03 smoke 实际 3/3 + 1 reset HARNESS_ERROR 后停批，先导未解锁。
> 两组均保留原始失败，n≥50 冻结；独立回归修复 EXPECT 行误放行后实测通过。
> [假设、逐回合统计、失败与证据](Q8_PILOT_20261005.md)。

> 2026-10-02 主线修复（E-016）：仓内启动路径、typed 控制器就绪探测和
> carry 权威快照已落地；冷启动 FSM 双物体 S1 成功，真实旧 A carry 注入
> 探针通过。Jev 已有真实校准，快路径不具备 0.7 路由资格；离线冻结模型
> 重放实际 FAIL，Hybrid 在线 smoke 未通过。最终部署 FSM/IDLE。
> [实现、失败证据及剩余门槛](HARDENING_20261002.md)。

> 2026-10-01 主线接入（E-015）：速度约束 magnetic carry、engage 确认和
> PLACE 内部依赖门禁已上线；最终单物体闭环 2.86 mm。不同指纹的首批
> S1×5=4/5、确认后 S1×2=1/2，均未解锁统计基线。
> [实现、全部失败和最终部署](CARRY_VELOCITY_20261001.md)。

> 2026-10-01 机制调查（E-014）：Fast DDS localhost IP 分片接收失效可复现；
> 1400 字节 transport 对照两轮 16/16 成功。Servo 位置传送保留速度的机制
> 获得重力/碰撞/更新率/速度控制对照支持。当前是机理证据，不是新基线。
> [调查报告、重现范围和证伪实验](MECHANISM_20261001.md)。

> 2026-10-01 主线更新（E-013）：官方 DeepSeek 真实决策与 5 元持久预算已
> 上线，单物体闭环成功；独立 S1:5 完整执行，结果 3/5 成功。
> 运行指纹区分客户端、释放确认和内部结果读取补丁，失败与未关联记录均保留。
> 最新 S3 的 B-only 注入恢复成功，S4 按预期实际进入 PLACE 失败并入库（各 n=1）。
> 当前结论是在线接入和控制闭环，统计比较与模型重放仍未完成。
> [实现、证据及交接](DEEPSEEK_20261001.md)。

> 2026-09-30 主线更新（E-012）：单物体 policy 闭环与 Jev/LLM/Hybrid 运行
> 接入已实现，真实快/慢模型已运行，LLM 单物体闭环在线完成。E-011 按
> protocol v1 冻结存档，v2 小批另存。旧批次 metric 3 因整数毫秒截断重分类
> NOT_RUN，三个派生报告已更正，原始记录保留。E-010 的 flood-clean 证明
> 症状被抑制，不证明触发根因已定位。
> S3 已在线执行仅 B 的首次失败恢复，S4 已在线进入 PLACE 失败并入库；
> 早期小批存在模型推进和 ROS 应答失败，完整 benchmark 与大样本仍未运行。
> [实现、运行入口和剩余主线](MAINLINE_20260930.md)。

> One entry per experiment: purpose / scenario / configuration / result / evidence
> location. **Chat history is not experiment memory** — if a result is not recorded here
> (or linked from here), it did not happen. Benchmark (M3) numbers must regenerate from
> the replay store (#7/#8) — no hand-written PASS lines.

## Index

| ID    | Experiment                                                              | Outcome                                                                                                | Evidence                                                              |
| ----- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| E-001 | Day-1 environment verification                                          | PASS                                                                                                   | acceptance/day1 (delivery host) + [DAY1_REPORT.md](../DAY1_REPORT.md) |
| E-002 | Day-2 MoveToPose acceptance                                             | PASS 10/10                                                                                             | acceptance/day2 + [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)            |
| E-003 | Week-1 deterministic skills battery                                     | PASS                                                                                                   | acceptance/week1                                                      |
| E-004 | Week-1.5 demo hardening — delivery acceptance (att3)                    | PASS                                                                                                   | acceptance/week15/delivery_20260926/                                  |
| E-005 | Week-1.5 cold-start re-verification                                     | PASS                                                                                                   | acceptance/week15/cs_20260926/                                        |
| E-006 | M2.3 audit remediation — runtime acceptance                             | PASS (gated)                                                                                           | acceptance/sessions/ (FLEXCELL_STAGE) + ~/.ros/flexcell/referee.jsonl |
| E-007 | Scenario runner batch (S1×2 + S2 + S5), episode replay                  | PASS                                                                                                   | ~/.ros/flexcell/episodes/batch_20260928_051219.jsonl                  |
| E-008 | Metrics report over real store + S7 adaptation probe                    | PASS                                                                                                   | ~/.ros/flexcell/episodes/batch_20260928_124615.jsonl                  |
| E-009 | New-machine (RTX 4060 laptop) bring-up + first official benchmark batch | SUPERSEDED (not citable)                                                                               | setup/acceptance/m3_seed_batch_20260929*/                             |
| E-010 | T6 hardening: gate_flood + injection lifecycle + reset determinism      | PASS                                                                                                   | this entry (measurements inline)                                      |
| E-012 | Shared task policy seam + distinct models + protocol v2 online smoke    | ONLINE PARTIAL; BASELINE FROZEN                                                                        | [MAINLINE_20260930.md](MAINLINE_20260930.md)                          |
| E-013 | Official DeepSeek policy + persistent RMB 5 budget + action handoff     | ONLINE PARTIAL; S1 3/5; BASELINE FROZEN                                                                | [DEEPSEEK_20261001.md](DEEPSEEK_20261001.md)                          |
| E-014 | DDS fragment-path diagnosis + servo velocity controls                   | MECHANISM PROBES; NOT BENCHMARK                                                                        | [MECHANISM_20261001.md](MECHANISM_20261001.md)                        |
| E-015 | Leased velocity carry + engage receipt + PLACE dependency readiness     | DEPLOYED; FINAL SINGLE PASS; SMOKE INCOMPLETE                                                          | [CARRY_VELOCITY_20261001.md](CARRY_VELOCITY_20261001.md)              |
| E-016 | Lifecycle paths + authoritative carry + local calibration/replay        | FSM CONTROL PASS; HYBRID/REPLAY FAIL; NOT BENCHMARK                                                    | [HARDENING_20261002.md](HARDENING_20261002.md)                        |
| E-017 | Desktop revival; hybrid online n=5 at one fingerprint                   | 5/5 SUCCEEDED; E-016 hybrid hang modes absent on the NAT host; NOT BENCHMARK                           | staging `hybrid_n5_desktop_20261004/`                                 |
| E-018 | Clef-flash fast arm — offline calibration on the desktop                | GPU: 17/30, TOP BIN 8/8 (LB 0.676), 1.9 s, 35/35 SUCCESS; τ=0.5 ELIGIBLE                               | desktop `jev_calibration_clef_gpu.json`; code pending feat branch     |
| E-019 | Q8 per-decision provenance + two-regime pilot                           | 215 TESTS PASS; HIGH 14/17 + RESET ERROR; LOW SMOKE TRUNCATED; n>=50 FROZEN                            | [Q8_PILOT_20261005.md](Q8_PILOT_20261005.md)                          |
| E-020 | Pose callback finalization barrier + bounded fresh-process reset RPC    | 226 TESTS PASS; LIFECYCLE 100/100; RESET 20/20 EACH; LOW 18/20; HIGH SMOKE 4/5; n>=50 FROZEN           | [Q8_TEARDOWN_20261005.md](Q8_TEARDOWN_20261005.md)                    |
| E-021 | Three-arm S1 comparison, same machine, same night, unattended           | FSM 19/20 · hybrid τ=0.03 18/20 · hybrid τ=0.85 17/20; CIs OVERLAP; grasp-physics noise ~15% cross-arm | `setup/acceptance/tau_sweep_desktop_20261005/`                        |
| M3-*  | Hybrid Agent Benchmark (cells A-D × S1-S7)                              | NOT RUN                                                                                                | — (RFC #15; harness #7/#8/#9)                                         |

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

### E-011 — First M3-baseline candidate batch, n=20 per cell (2026-09-30)

**Current disposition (2026-09-30): archived as protocol v1, not an active v2
baseline.** The frozen bundle contains the corrected derived metrics reports
(legacy integer timing reclassified NOT_RUN), original reports from Git HEAD,
and unchanged raw episodes. Protocol v2 changes object-scoped injection;
v1 and v2 results must not be pooled or treated as appended baseline cells.
See [the freeze record](MAINLINE_20260930.md). The following is the original
experiment narrative, including its then-open work.

The n≥20 re-run that E-010 called the next step. Four cells, 80 episodes, run in
resumable per-cell segments because the WSL VM had restarted mid-batch twice
(`/tmp` is tmpfs; the driver therefore banks each cell as its own row file and
merges at the end). Head commit `d03d06c`.

| cell | success      | Wilson 95%   | E-009 for comparison   |
| ---- | ------------ | ------------ | ---------------------- |
| S1   | 15/20 = 0.75 | [0.53, 0.89] | 0.90 (n=20)            |
| S2   | 11/20 = 0.55 | [0.34, 0.74] | 0.40 (n=20)            |
| S5   | 0/20 = 0.00  | [0.00, 0.16] | 0/20, correctly FAILED |
| S7   | 16/20 = 0.80 | [0.58, 0.92] | 0.60 (n=10)            |

`REPORT: PASS (80 episodes, 0 replay-dirty)`; 20/20 episodes clean in every cell
(0 diverged steps, 0 safety-rejection exclusions); **0 harness errors** across
all 80 episodes, which is the T6 injection-lifecycle change doing its job on real
data rather than only in the unit tests.

- **What moved and why it is believable**: S2 and S7 are the two cells that
  E-010 identified as capped by harness defects — S2 by the carry-servo lift
  failure that stranded the box and made `reset` report `ok=false`, S7 by
  leftover injection that the `if payload:` guard had turned into a no-op. Both
  rose after the fixes (+0.15 and, at n=10→20, +0.20). S1 fell 0.90→0.75 and S7
  is now measured at n=20 instead of n=10, so neither comparison is
  like-for-like; with 20 episodes the Wilson interval is ±0.18 wide, which is wide
  enough that S1's move is **not** evidence of a regression.
- **S5 stays 0/20 by design**: that cell expects exhaustion to fail. A non-zero
  rate there would be the bug.
- **NOT_RUN — decision latency (metric 3)**: p50/p95/p99/max all report `0.0 ms`
  across 177-207 evaluated decisions per cell. A maximum of exactly zero across
  hundreds of decisions is not a measurement, it is an unpopulated field. The
  numbers are carried in the report because the generator emits them
  unconditionally, but **nothing here supports any latency claim**, and none is
  made. Instrumenting it is open work.
- **Open**: this is a _candidate_ baseline. Freezing it as the M3 baseline is a
  human decision; nothing here is tagged or released.

Evidence: `setup/acceptance/m3_baseline_t6_20260929/` (per-cell `seg_*.jsonl`,
`batch_merged.jsonl`, `95_metrics_report.md`, `gate_reset.json`,
`baseline_rerun.log`). Copied off the execution host and md5-verified.

### E-013 — Official DeepSeek and bounded online control (2026-10-01)

- **Purpose**: make the remote slow policy exercise actual Gazebo skills through
  both task APIs; keep the user's RMB 5 allowance across processes and restarts.
- **Configuration**: protocol v2; teleport-servo; official `deepseek-flash`,
  JSON object, thinking disabled, output cap 512, production timeout 30 s;
  persistent overlay and Cyclone DDS. Different runtime fingerprints remain
  separate. The previous OpenCode gateway attempt returned HTTP 402 and is
  not counted as a model decision.
- **Change**: persistent client executor and same-goal GetResult retries;
  acknowledged carry release before PLACE detach/open; the same result-read
  recovery at task/skill/motion boundaries. No repeated physical SendGoal.
- **Result**: one accepted single-object success (8.95 mm). An independent
  S1:5 batch completed all five tasks: 3 succeeded, 2 failed (servo grasp and
  skill reply/motion discovery failures). After the internal result-read fix,
  S3:1 succeeded with B-only injected recovery, and S4:1 produced the expected
  actual PLACE/NO_IK_SOLUTION failure. S4's model abort reason was imprecise;
  expected task failure does not validate every model rationale.
- **Cost**: 95 authorized official requests, conservative upper bound RMB
  0.330258 / 5; all settled from usage. Final reset exited 0 with `ok:true`,
  carry disengaged, scene cleared and arm home.
- **Limits**: online smoke, not statistical comparison; S3/S4 each n=1;
  model replay NOT_RUN, so metrics reports INCOMPLETE. MTC, Jev/APUS and
  calibrated Hybrid remain open; large sample plan stays frozen. Offline
  executor checks validate contracts/control flow, not grasp reliability.
- **Evidence**: [implementation and handoff](DEEPSEEK_20261001.md),
  [full artifact manifest](../setup/acceptance/m3_deepseek_20261001/manifest.json).

### E-014 — DDS fragment path and servo momentum (2026-10-01)

- **Scope**: isolated real ROS/RMW two-process probes and Gazebo box controls;
  no new robot baseline, fleet switch or large benchmark batch.
- **DDS**: localhost routes through MTU 1500 loopback0. Full capture shows
  complete outgoing fragmented UDP and missing incoming noninitial fragments.
  Default transport fails discovery; changing only maxMessageSize to 1400
  passes 8 + 8 queries/goals, with no fragments in the captured repetition.
  Historical Cyclone result loss remains unreproduced within 352 completed
  virtual goals. First GetResult response-drop injection recovers 8/8 with one
  execution per goal; one valid all-response-drop case times out. Another
  all configuration never reaches injection and is excluded from that claim.
- **Servo**: 12 gravity/collision/cadence controls plus four completed
  zero-velocity interventions support pose-only reset preserving momentum.
  Gravity stays enabled during the intervention. A permanent velocity plugin
  is not a release-capable production fix.
- **Inference**: three official thinking/max reviews, one truncated final
  answer retained; cumulative 98 requests, RMB 0.761626 upper bound against
  the same RMB 5 ledger. Model hypotheses are separate from measured evidence.
- **Evidence**: [report](MECHANISM_20261001.md),
  [manifest](../setup/acceptance/mechanism_20261001/manifest.json).

### E-015 — Bounded velocity carry deployed to the robot stack (2026-10-01)

- **Change**: native Gazebo pose/velocity command constraints with a 500 ms lease,
  session ownership and release after a physics step. Typed engage receipt blocks
  lift until acknowledged; PLACE exposes its own release discovery readiness.
- **Online evidence**: lifecycle PASS; initial single 12.70 mm; first S1×5 4/5,
  with a lost/unobserved topic start, a policy gate rejection and a lift planning
  failure retained. After engage receipt, S1×2 1/2: first PLACE cannot discover
  release, second complete. After readiness gating, final single 19.012 s /
  2.86 mm. These stages use different runtime fingerprints and are not pooled.
- **Validation**: native/interface/skills builds; eight carry contract tests;
  final reset RC=0 / ok=true, health 19 checks / IDLE, native carry off.
- **Limits**: magnetic simulation, final-fingerprint dual-object batch pending;
  model replay NOT_RUN; no statistical baseline or large batch. Historical DDS
  result-loss, reset139, rosdep and MTC gaps retain their prior status.
- **Budget**: same persistent RMB 5 ledger, 152 request records, RMB 0.987406
  conservative upper bound including one historical unknown reservation.
- **Evidence**: [report](CARRY_VELOCITY_20261001.md),
  [manifest](../setup/acceptance/carry_velocity_20261001/manifest.json).

### E-016 — Mainline carry authority and model evaluation (2026-10-02)

- **Change**: workspace lifecycle paths, typed controller readiness, authoritative
  carry query checked against native ownership; bounded status reply retries,
  isolated pose worker, and admin success contingent on child exit.
- **Online**: cold FSM S1 double-object passed (A 2.11 mm / B 14.81 mm, 8 replay
  decisions). Four Hybrid attempts retain failures/timeouts and distinct
  fingerprints. Final FSM deployment reset, strict health and stale-A injection
  probe pass; no final-fingerprint S1 batch claim.
- **Models**: real local Jev calibration 4/30 FSM agreement, heldout 1/5; calibrated
  lower bound 0.0531 disallows the 0.7 fast route. Local counterfactual 5 episodes /
  41 steps has 15 semantic agreements; one same-frozen-model fixture replay fails
  with 6 divergent/unavailable steps. No fixture claims robot execution or
  historical DeepSeek same-model replay.
- **Validation**: 193 skills tests pass; 5 targeted carry tests pass including two
  new reply-loss cases; build passes; actual crashing admin child is rejected.
  Historical evidence 454 manifest items retain exact Git/worktree bytes.
- **Budget/limits**: same RMB 5 ledger, 163 records / RMB 1.168980 conservative upper
  bound, including 6 unknown reservations. Minimal official completion requests
  time out through proxy and direct. Historical reset/flood roots remain UNKNOWN;
  large batch NOT_STARTED, rosdep NOT_VERIFIED, MTC pending. Local commits, no push.
- **Evidence**: [report](HARDENING_20261002.md),
  [manifest](../setup/acceptance/hardening_20261002/manifest.json).

### E-017 — Desktop revival: hybrid online n=5 at one fingerprint (2026-10-04)

- **Setup**: the original delivery desktop (RX 6800 / Ryzen 5 5600 / 32 GB) was revived
  to `main` `424ad43` following ONBOARDING, with one deliberate deviation: **NAT, not
  mirrored** networking — under mirrored mode both gz transport and the DDS mesh broke
  on this host (see issue #25). `rmw_cyclonedds_cpp` was installed (the 9/30 mainline
  requirement). Sha-pinned local models were provisioned via `118` (Qwen2.5-1.5B/3B
  Q4_K_M + llama.cpp b11284; fast:18081 / slow:18082), and calibration was reproduced
  on-machine from the recorded inputs: reported confidence sits at 0.9–1.0 while
  FSM-action agreement stays far below any sweep τ, so the router **bypasses the fast
  route by design** (`calibration_unavailable_or_threshold_unattainable`).
- **Result**: `102 cold hybrid` DEPLOYED — fingerprint `20261004_194901`, protocol v2,
  slow arm = official deepseek-flash. Single-object episodes **n=5/5 SUCCEEDED**
  (errors 10.2 / 1.3 / 6.3 / 10.2 / 1.4 mm; wall 16.3–30.1 s); strict health 19/19
  `hard_fail=[]` afterwards. **None of the four E-016 hybrid hang modes reproduced**
  (planning service unavailable / client 150 s timeout / carry query timeout / official
  request timeout) on the same code and the same API with a different network stack
  (NAT vs the laptop's mirrored mode). Environment attribution is supported, not proven.
- **Validation**: client evidence + deployment fingerprint archived as
  `setup/acceptance/hybrid_n5_desktop_20261004/{deployment.json,ep1..ep5}` (staging
  copy); replay-store rows under `~/.ros/flexcell/episodes/`. This is the E-016 next
  gate ("hybrid same-fingerprint n=5") executed, **not** a statistical baseline: one
  task shape (S1-style), fast path absent, n=5.
- **Budget/limits**: desktop ledger ¥5 limit; ¥0.066 committed upper bound total
  (1 wiring probe outside the ledger + 3 LLM-arm decisions + the n=5 decisions).
  τ sweep deferred: with the current fast arm every τ ∈ {0.5, 0.7, 0.9} bypasses fast,
  so a sweep would degenerate to LLM-only. The #12 critical path is fast-arm
  qualification: the 160-token output cap truncates/derails parsing, and
  FSM-action agreement is 4/30.
- **Evidence**: staging `hybrid_n5_desktop_20261004/`; ledger on the desktop machine.

### E-018 — Clef-flash as the fast arm: offline calibration on the desktop (2026-10-05)

- **Setup**: Cloudflare's open decision model `clef-flash` (9B, Apache-2.0, base
  Qwen3.5-9B) served by **Ollama 0.35.1 Linux inside WSL**. The Windows 0.35.1 build
  fails every `/v1/systemone` request with `Clef: non-finite logit` on CUDA, ROCm,
  Vulkan AND CPU (upstream issue ollama#18769; the Linux build works — the issue
  reporter measured 0.1-0.3 s on GPU). Model blobs were reused from the Windows pull
  (no re-download). New `ClefBackend` (typed `/v1/systemone`:
  `questions={type: choice, instructions, criteria}`; response `answers.<id>.
{choice, probabilities}`) + `make_backend('clef')` + `119 --backend clef`; the
  routing signal is the chosen option's own probability — the API's `confidence`
  field is probability-mass CONCENTRATION, not accuracy. Full test suite green.
- **Result**: calibration over the same 35 recorded inputs:
  **12/20 calibration agreement (Qwen1.5B baseline: 4/30, Wilson lower 0.053)** and
  the bins are MONOTONE — [0,0.5): 1/8 (LB 0.02), [0.5,0.8): 3/4 (LB 0.30),
  **[0.8,1.0): 8/8 (Wilson lower 0.676)**; heldout 2/5. Reported confidence is a
  usable routing signal for the first time: low-confidence picks fail, the top bin
  is clean. `output_tokens: 0` on every call — the no-generation no-parse claim is
  real, so E-016's truncation/parse failure mode is structurally absent.
- **Limits (CPU interlude, superseded the same day)**: the first calibration ran
  CPU-only in WSL (ROCm-WSL not wired): median 109 s/decision, 10/35 rows timed out
  at the 120 s cap — unusable live. Root-caused to the Ollama runner, not the
  weights: upstream llama.cpp b11389 `llama-server` with `ggml-org/Clef-Flash-GGUF`
  returns finite, calibrated probabilities on the same machine (see ollama#18769
  comments), so the GPU path bypasses Ollama entirely.
- **Result (GPU, final)**: upstream `llama-server` b11389 (Vulkan build) on the
  RX 6800, `Clef-Flash-Q4_K_M.gguf`, `-ngl 99 -ub 32768 -c 16384`, bound
  `0.0.0.0:11435` (WSL reaches it via the NAT gateway — no firewall change). Full
  recalibration over the same 35 inputs: **model_success 35/35 (zero timeouts, zero
  parse failures)**, **calibration agreement 17/30 (Qwen baseline 4/30)**, bins
  monotone — [0,0.5): 0/11 (LB 0.000), [0.5,0.8): 9/11 (LB 0.523),
  **[0.8,1.0): 8/8 (LB 0.676)**; heldout 2/5. **Latency median 1.9 s, max 6.8 s**
  (~56× vs the CPU run). The arm is LIVE-QUALIFIED: the top bin clears τ=0.5, so
  high-confidence decisions route locally for free; τ=0.7 misses by 0.024 (more
  calibration samples may close it), τ=0.9 escalates everything.
- **τ sweep, first pass (2026-10-05, single-object task, n=5 per τ)**: with
  `mainline_jev.sh` on the GPU endpoint and `jev_backend: clef`:
  **τ=0.5 → 5/5 SUCCEEDED, decisions jev 11 / llm 6 / fsm 5 (bootstrap) — 55% of
  decisions on the free local arm, escalation rate 30%; τ=0.7 → 5/5, jev 0
  (full bypass, LB 0.676 < 0.7), escalation 100%; τ=0.9 → 3/5 (2 failed on the
  known reset-flakiness family before decisions, not τ-caused), escalation 100%.**
  Same success rate at τ=0.5 with ~55% of decisions free — the sweep is
  non-degenerate and the escalation/success-per-τ AC of #12 is now measurable at
  scale. (First sweep attempt was invalid: a branch checkout had reverted the WSL
  working tree to pre-Clef code, sending fast calls to a dead endpoint — all
  "backend error"; re-run on the correct tree. Lesson recorded.)
- **Prompt v2 + Q8_0 (2026-10-05 evening)**: two upgrades:
  ① prompt v2 folds the frozen FSM cycle semantics into the ClefBackend
  instructions and enriches per-option criteria (backend-scoped; the shared
  _choice_options contract text untouched);
  ② Q8_0 weights replace Q4_K_M on the same Vulkan server.
  In-sample 35: agreement 26/30, top bin 23/23 (LB 0.857).
- **⚠ CORRECTION (2026-10-05, chief counter-audit)**: three claims in this
  entry were wrong and are retracted/downgraded:
  1. The "fresh S7 blind set" was **not S7 and not blind** — forensics on the
     six episode files: `scenario_id=week1_demo_v1` (×3, policy=fsm) and
     `pick_place_v1` (×3, **policy=hybrid** — recorded on the τ=0.5 sweep arm,
     not the FSM arm as this journal previously stated); zero perturbation
     records; the earlier journal wording is a factual error. The 18/20 number
     is a mixed-policy, same-distribution number, not a generalization result.
  2. **Statistical basis**: those rows come from 4 episodes (7+7+3+3), not 20
     independent trials — the episode-level Wilson lower bound is ≈0.510 even
     at 4/4, not 0.824/0.857. All binned LBs in this entry are step-level and
     optimistic; per-episode accounting is required before any benchmark claim.
  3. **The τ=0.7 "crossover" is misattributed**: routing eligibility is decided
     by the bin's Wilson LOWER BOUND, so with the three fixed bins the arms
     τ=0.5 and τ=0.7 are the SAME operating point (only the top bin clears
     either). The jev 0→16 change was caused by the profile swap
     (Q4+v1 → Q8+v2, bins 0.000/0.523/0.676 → 0.342/0.036/0.857), not by τ.
     The `threshold=0.7` rows in decisions.jsonl are a MIXTURE of two
     calibration profiles (34 skipped + 17 routed across the swap) and must
     not be pooled. A valid τ sweep needs bin LB breakpoints
     (≈0.036 / 0.857 today) or finer bins — pending a design decision.
- **τ=0.7 live run (as-measured, no τ attribution)**: Q8+v2 profile, 5 episodes
  5/5 SUCCEEDED, decisions jev 16 / llm 1 / fsm 5 (bootstrap) — escalation
  5.9% of model decisions; ledger total after all of the day's runs
  ¥0.234/¥5. Also observed: 15/41 fast proposals in the earlier τ=0.5 arm ran
  with the calibration NOT loaded (`calib_sha='-'`, silent) — the runner gate
  passed regardless; per-decision `source=='jev'` + expected calibration sha
  assertions are REQUIRED harness work before n≥50.
- **Next**: (1) scale the sweep to the S-cell runner for n≥50 per-τ statistics
  (#12 AC), (2) S7 differentiation track at τ=0.7 (hybrid vs FSM where the
  deterministic baseline is weakest), (3) land the feat branch docs.
- **Evidence**: desktop `~/.config/flexcell/jev_calibration_clef{,_gpu,_v2,_fresh,_q8,_q8_fresh}.json`
  (Q8 digest `8754b06f…b05593d9`); ClefBackend + harness changes on the
  `feat/clef-fast-arm` branch (pushed).

### E-021 — Three-arm S1 comparison on one machine in one night (2026-10-05, unattended)

- **Setup**: desktop as the only fully-qualified executor (shutdown race repaired,
  per-decision routing gates live, 7-day unattended hardening: updates disabled at
  three layers, sleep structurally impossible on this firmware, Storage Sense off —
  service snapshot + rollback script on `F:\flexcell-models\`). Three arms, S1
  single-object, n=20 each, sequential deployments (one fingerprint per arm; no
  pooling across arms). τ=0.85 unlock used the runner's fingerprint-scoped smoke
  rule: attempt 1 (3/5, two grasp-physics failures) + attempt 2 (5/5, all routing
  audits green) = **8 pooled valid rows**, BOTH batch files archived and disclosed.
- **Result**:
  | arm                                                                              | S1 n=20      | Wilson 95% CI | paid slow fraction | cost ceiling |
  | -------------------------------------------------------------------------------- | ------------ | ------------- | ------------------ | ------------ |
  | FSM control                                                                      | 19/20 (0.95) | [0.76, 0.99]  | 0%                 | ¥0           |
  | hybrid τ=0.03                                                                    | 18/20 (0.90) | [0.69, 0.98]  | ~0%                | ~¥0.02       |
  | hybrid τ=0.85                                                                    | 17/20 (0.85) | [0.64, 0.95]  | ~20%               | ~¥0.3        |
  | All CIs overlap: **no significant success-rate difference at n=20**. Every model |
  | decision passed the routing provenance audit (139 decisions in the τ=0.85        |
  | baseline, zero violations). Night total ¥0.576 / ¥5 upper bound.                 |
- **The dominant confounder**: 6 of tonight's 7 non-success episodes (FSM run20,
  hybrid τ=0.85 runs 3/10/13, hybrid smoke ×2) are the SAME grasp-physics family —
  `PICK_B`/`PICK_A` fails twice with ERR_GRASP_FAILED (23) → recovery exhausted
  (51); cross-arm, ~15% episode incidence, root cause UNKNOWN. It caps every
  arm's success rate equally and swamps arm-to-arm success comparison below n≈50.
  Runner "FAIL (N)" labels here mean the strict expected-outcome gate, not
  harness faults.
- **Reading (cost hypothesis)**: hybrid at τ=0.03 delivers 0.90 at near-zero paid
  cost vs FSM 0.95 at zero cost — FSM remains the free control; the hybrid's
  saving is measured against a PURE-LLM arm (≈3-5× the slow-arm spend), not
  against FSM. τ=0.85's ~20% slow fraction ≈ 80% paid-call reduction. These are
  n=20 descriptive results with correlated steps and sequential arms (no
  time-drift interleaving) — NOT a benchmark.
- **Next**: B-grasp root cause (the single highest-value open item), batch-level
  fast-arm presence gate for unattended batches, S7 differentiation design,
  n≥50 freeze maintained.
- **Evidence**: `setup/acceptance/tau_sweep_desktop_20261005/` (12 batch files
  incl. both τ=0.85 smoke attempts, pooled summary, two hybrid deployments,
  campaign log `F:\flexcell-models\campaign_20261005.log`).

## Evidence locations

- Delivery host: `F:\flexcell-stage\setup\acceptance\{day1,day2,week1,week15}\`
- Per-request structured logs: `~/.ros/flexcell/*.jsonl` (WSL; `evidence_id` per record)
- Lifecycle transcripts: flexcell CLI outputs (same acceptance dirs)
- Repo-side records: [DAY1_REPORT.md](../DAY1_REPORT.md),
  [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)

> **Open (infra)**: acceptance evidence currently lives only on the delivery host. Decide
> whether key evidence bundles are copied into the repo (or an evidence branch) so the
> repository is fully self-contained — chief decision.
