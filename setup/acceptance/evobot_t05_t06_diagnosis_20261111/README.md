# T05 relay / T06 revisit — 为什么 0/19

**诊断对象**：Baseline A（确定性 composite 执行器，无 agent 规划）
**证据根**：`ci-public-window/evidence/baseline_a_v0_full_20261111/`
**日期**：2026-11-11 · **只诊断，不修复**

> ⚠️ **重要：诊断期间该批次仍在运行。**
> 证据目录的 mtime 在持续前进（最早 episode 09:19Z，最新 11:05Z）。
> 本次分析首扫到 100 个 episode 文件，结束时为 102 个；T06 从 7 个实例增长到 9 个。
> **下列计数是快照，不是终值**；但每一个核心结论在增长前后都成立（见 §6 稳定性检查）。

---

## 结论（一句话）

**T05/T06 不是"计划不可执行"，也不是"任务超出技能能力"，而是执行栈的
velocity-servo 载具（carry）在高系统负载下被自己的"连续 3 次失败即自杀"规则 abort 掉，
导致 PICK 阶段就失败，从未进入 PLACE。**

计划层 72/72 全部被接受（error 60 拒绝数 = 0）。T05 的 11 个实例中
**没有任何一个执行到第二阶段**；T06 的 9 个实例中**没有任何一个执行到 PLACE**。
失败点全部集中在 `PICK_A(attempt=1)`。

归因主类：**Runtime**（宿主负载 → 实时性 → servo 自 abort）。
次类：**State Management**（error 64 的 carry 状态查询链路）。

---

## 1. native FAILED 的具体阶段与 error_code

从 `sim/episodes/*.json` 的 `final_state` 逐条统计（T05 11 个 + T06 9 个 = **20 个 episode**）：

| native error_code | 数量 | legacy_error_code | 含义 |
|---|---|---|---|
| 51 (BUDGET_EXHAUSTED) | 14 | 23 ×13 / 30 ×1 | pick attempt 2 失败，恢复预算耗尽 |
| 50 (NON_RECOVERABLE) | 5 | 3 ×2 / 23 ×2 / — | policy abort / internal failure |
| 0 (SUCCEEDED) | **1** | — | 仅 T05-seed1000 |

→ **19/20 native FAILED**（与任务卡的 17/19 同性质，只是批次还在长）。

**首次失败所在的 FSM 步骤（20 个 episode）：**

| 次数 | 步骤 |
|---|---|
| 13 | `PICK_A(attempt=1):FAIL:ERR_GRASP_FAILED` |
| 5 | `PICK_A(attempt=1):FAIL:ERR_MOTION_FAILED` |
| 1 | `PICK_A(attempt=1):FAIL:ERR_INTERNAL` |
| 1 | （无失败 = T05-seed1000） |

→ **19/19 的失败都发生在 PICK 的第一阶段，从未进入 PLACE。**
关键证据：全库只有 `T05-train-seed1000` 一个 episode 的 fsm_trace 里出现过 `PLACE_A`。

### 直接机制：box 没有跟随抬升

`T05-train-seed1001/sim/skills/pick.jsonl:1`（attempt 1）与 `:2`（attempt 2）：

```
"carry_engage_confirmed": true,
"box_rise_m": -0.0012425435643303173,
"error_code": 23, "status": 2,
"detail": "box did not follow the lift (rise=-0.001m < 0.030m); carry release requested"
```

门限来自 `sim/params.yaml:49` `box_follow_min_m: 0.03`。
夹爪本身是成功的（`"classification": "GRASPED_AT_GOAL"`，`aperture_error≈0.0097`），
**载具 pin 没有把 box 抬起来**。

### 载具为什么没抬起来：servo 自己 abort 了

`T05-train-seed1001/sim/skills/carry.jsonl`：

```
13: {"event": "set_pose_fail", ..., "consecutive": 1, ...}
15: {"event": "set_pose_fail", ..., "consecutive": 2, ...}
17: {"event": "servo_abort",   ..., "consecutive": 3, ...}
```

`stack.log:361-363`：
```
[carry_server]: set_pose rejected (1 consecutive)
[carry_server]: set_pose rejected (2 consecutive)
[carry_server]: set_pose rejected (3 consecutive)
```

代码路径 `src/flexcell/flexcell_skills/flexcell_skills/carry_server.py:571-578`：
连续 3 次 pin 失败 → 写 `servo_abort` → `stop_evt.set()`，servo 线程退出。
之后 box 就再也没有人推，抬升自然为 0。

**这是一个"3 次连续失败即自杀"的硬门限，没有退避、没有重试预算、没有降频。**

---

## 2. T05 两阶段计划：在 prepare_plan 就被拒，还是第二阶段失败？

**两者都不是。计划被接受，第一阶段就失败了。**

- `contracts/composite.py:73-86` `prepare_plan` 的拒绝码是 **60**。
  全库 72 个 composite PLAN 事件中，**error 60 拒绝数 = 0**。
- 每个 T05 实例的 PLAN 事件都完整带 2 个 stage
  （如 `T05-train-seed1001/sim/skills/composites/composite-b62bbf6c5acc4659.jsonl:1`，
  stages = `target_box_a-relay-0` → `target_box_a-0`）。
- 但 `STARTED` 事件**只出现过第一阶段**：
  `T05-seed1000..1010` 全部只有 `*-relay-0` 一个 STARTED；`T05-seed1011` 连 STARTED 都没有。

→ **没有任何一个 T05 实例进入过第二阶段。** 所以"两阶段计划被拒"是错的，
"执行到第二阶段才失败"也是错的。真正的断点在**第一阶段的 PICK**。

T05-seed1000 是唯一走完全程的：native SUCCEEDED、`object_at_place=true`，
但 `final_position_error_m = 0.0497` > plan 的 `position_tolerance_m = 0.02`，
被 `contracts/composite.py:136` 的 `0 <= v <= tolerance` 判为 native 未成功 → composite **62**。
最终 box 停在 `[0.1669, -0.1665]`，距 zone_2 中心 0.2319m（radius 0.06），placement 子句失败。

---

## 3. T06 的 error 64 "released carry unconfirmed" 是什么

**不是 carry 没正确释放，也不是观测桥坏了——是 observe 拿不到 carry 的 native 状态。**

抛错点：`contracts/composite.py:97`
```python
raise CompositeError(64, 'fresh observation or released carry unconfirmed')
```
触发条件是 `positions()` 对 observation 的校验失败（outcome≠0 或 error_code≠0 或
source≠SIMULATION_GROUND_TRUTH 或 carry.engaged≠False ...）。

根因在上一层。error 64 实例的 `sim/skills/observe.jsonl` 都只有一条记录：

`T06-train-seed1000/sim/skills/observe.jsonl:1`
```json
{"request_id": "auto-1-31682d27", "error_code": 3, "status": 2,
 "detail": "native carry status timed out after 3 attempts", "elapsed_ms": 4894}
```
（`T05-train-seed1011`、`T06-seed1008`、`T06-seed1009` 同形，elapsed 2.5–4.9s）

链路：
`observe_server` 要查 carry 状态 → `carry_server.py:168-174` 对 Gazebo 的
`/flexcell/carry/status` 服务做 **3 次 × 400ms** 重试 → 全超时 →
抛 `native carry status timed out after 3 attempts` →
observe 返回 `ERR_WORLD_STATE_UNAVAILABLE (3)` →
composite 的 `positions()` 校验失败 → **error 64**。

对应 composite 记录（`T06-train-seed1000/sim/skills/composites/composite-61a5826593224036.jsonl`）：
```
seq1 OBSERVATION  revision=0  source=""  error_code=3  objects=0
seq2 TERMINAL     error_code=64  completed_stage_ids=[]
```
`revision=0 / source=""` 说明**这一次观测根本没成功返回过任何世界状态**。

配套证据：`observation.json` 的 `_ever_seen: []`、`move_sequence: []` —— 机器人一次都没动。

→ 所以 error 64 = **carry 状态查询链路在负载下超时**（State Management / Runtime），
**不是** carry 释放逻辑的语义 bug。注意 `carry.engaged` 在超时场景下压根没被读到，
"released carry unconfirmed" 这个措辞会误导人以为 carry 卡住了。

---

## 4. 归因：计划器 / 执行栈 / 任务定义

### 排除计划器

- 72/72 PLAN 被接受，error 60 = 0。
- T05 两阶段计划结构正确（relay → final），T06 单阶段计划与 T02 同构
  （`T06-train-seed1000/plan.json` stages=1，place_pose=[0.12,-0.15]；
  `benchmark/tasks/train/T06-train-seed1000.json` expected_goal.placement=zone_1）。
- 对照组：**同样的 T05 计划在 n=6 干净批次里 6/6 PASS**
  （`setup/acceptance/evobot_t05_n6_clean_20261111/summary.txt`，
  两阶段全部走完，fpe 0.002–0.013，每段 14s，load 0.8–5.6）。
  → 计划本身可执行，被证明过。

### 排除"任务定义超出技能能力"

- T06 的单阶段计划与 T02（12/12 通过）**结构完全相同**：同一对象、同一 zone_1、同一 tolerance。
- T05 在干净批次 6/6 通过。
- → 不是能力边界问题。

### 定位到执行栈 / 运行时

**剂量-反应关系（这是最硬的证据）。** 按 episode 的 `env.load_1m` 分桶，
统计"box 未跟随抬升"（`box_rise_m < 0.03`）的比例：

| load_1m | pick 尝试数 | 抬升失败率 |
|---|---|---|
| 0–10 | 7 | 0% |
| 10–50 | 26 | 0% |
| 50–100 | 22 | 0% |
| 100–200 | 27 | 11% |
| 200–300 | 14 | **79%** |
| 300–500 | 11 | **100%** |

按 episode 的成败看：

| 阈值 | load < 阈值 失败率 | load ≥ 阈值 失败率 |
|---|---|---|
| 100 | 2/31 = 6% | 20/36 = 56% |
| 150 | 2/40 = 5% | 20/27 = 74% |
| 200 | 3/47 = 6% | 19/20 = **95%** |
| 250 | 4/48 = 8% | 18/19 = **95%** |

**模板与负载几乎完全共线**（整套实例顺序跑，负载单调累积）：

| 模板 | load_1m 范围 | native 失败 |
|---|---|---|
| T01 | 4.7 – 76.5 | 0/12 |
| T02 | 4.8 – 168.2 | 0/12 |
| T03 | 3.9 – 78.8 | 2/12 |
| T04 | 82.7 – 234.3 | 2/12 |
| **T05** | **256.4 – 377.3** | **10/11** |
| **T06** | **364.5 – 569.9** | **9/9** |

`corr(load_1m, uptime_s) = 0.88` —— 负载就是运行时长，两者不可分。

**延迟证据**：carry pin 的往返延迟（`reply_mono_ns - request_mono_ns`）随负载单调恶化：

| 实例 | load | pin p50 | pin max | set_pose_fail |
|---|---|---|---|---|
| T01-seed1000 | 4.7 | 3.0 ms | 11 ms | 0 |
| T02-seed1000 | 74.7 | 29.9 ms | 82 ms | 0 |
| T04-seed1000 | 82.7 | 32.3 ms | 94 ms | 0 |
| T05-seed1000 | 256.4 | 149.8 ms | 416 ms | 6 |
| T05-seed1001 | 278.3 | 128.9 ms | 662 ms | 6 |
| T06-seed1002 | 436.2 | 324.3 ms | 855 ms | 6 |
| T06-seed1004 | 474.4 | 812.3 ms | 847 ms | 3 |
| **T06-seed1011** | **569.9** | **1008.0 ms** | **1235 ms** | — |

`corr(load_1m, pin_p50) = 0.85`。

**为什么 pin 延迟会导致 abort：** `carry_server.py:548-549` 对 pin 请求设了
**1000ms** 超时，servo 周期是 0.1s；而 `world.sdf:14` 的 `<lease_ms>500</lease_ms>`
是载具租约。T06-seed1011 的 pin p50 已经达到 **1008ms**，即**中位数就已经打满超时**；
pin 间隔实测 T01 p50 = 0.105s（≈ 标称 0.1s），T06-seed1004 p50 = 0.978s（≈ 10 倍超期）。
pin 一旦被拒，`carry_server.py:571` 的"连续 3 次即 abort"没有退避，servo 直接死掉。

### 归因分类（mission 十类）

| 类别 | 判定 | 依据 |
|---|---|---|
| **Runtime** | **主因** | load_1m ≥200 时失败率 95%；pin 延迟 corr 0.85；servo 3 次连续失败即自杀且无退避 |
| **State Management** | **次因** | error 64 全部源于 carry status 3×400ms 超时（`carry_server.py:168-174`），observe 拿不到 revision/source |
| Control | 参与 | pin 是 velocity_servo 闭环；负载下 0.1s 周期无法维持（T06 实测 p50 0.98–1.01s） |
| Grasp | **不成立** | 夹爪全部 `GRASPED_AT_GOAL`，aperture_error 稳定 0.0097，夹持本身没问题 |
| Planning | **不成立** | 72/72 PLAN 接受；同计划在干净批次 6/6 通过 |
| Perception | **不成立** | `source=SIMULATION_GROUND_TRUTH`，无相机依赖；失败时 objects 读不到是 carry 查询超时连带，不是感知 |
| Kinematics | **不成立** | `move_to_pose` 全部 error_code=0；IK/规划无失败记录 |
| Tooling | 部分 | 顺序跑 68+ 实例累积负载至 load_1m 570，无隔离/冷却；属实验设计缺陷 |
| Model Reasoning | 不适用 | Baseline A 无 agent 规划 |
| Environment | UNKNOWN | 无法区分"宿主机器本身慢"与"本套件累积负载"；无独立基线测量 |

---

## 5. 一条最小修复建议（不要实施）

> **把 `carry_server.py:571` 的"连续 3 次 pin 失败即 servo_abort"改为有界退避重试，
> 并让 pin 超时与 `lease_ms` 对齐。**

具体到最小改动面（一处文件、一个循环）：

1. `carry_server.py:548` 的 pin 请求超时从写死 1000ms 改为由 `lease_ms`（500ms）推导，
   例如 `lease_ms/2`，保证一次 pin 往返不会吃掉整个租约。
2. `carry_server.py:571` 的 `consecutive_fail >= 3` 门限保留语义，但加入
   指数退避 + 总时长预算（例如 3 次失败后退避到 0.3s 再试，累计不超过
   `skill_wait_s` 的一部分），**abort 只在预算真正耗尽时触发**。
3. 顺带把 `carry_server.py:174` 的 3×400ms 提到与 pin 超时一致的量级，
   避免 observe 在负载下先于 carry 崩掉（这是 error 64 的直接来源）。

**为什么这是最小且正确的**：Grasp 已被证明可靠（20/20 夹爪 GRASPED_AT_GOAL），
Planning 已被证明正确（72/72 接受 + 干净批次 6/6 PASS）。
唯一坏掉的是"pin 在慢的时候被立即放弃"这一个判断。
**不要**去改验收器、tolerance（0.02/0.06）或 zone 半径——T05-seed1000 的
0.0497m 误差是负载导致的真失败，不是阈值定得太严。

---

## 6. 稳定性检查（诊断期间批次仍在跑）

核心结论在证据增长前后都成立：

| 结论 | 首扫（100 ep） | 末扫（102 ep） |
|---|---|---|
| T05 native 失败 | 10/11 | 10/11 |
| T06 native 失败 | 8/8 | 9/9 |
| T05/T06 失败集中在 PICK_A | 是 | 是 |
| 只有 T05-seed1000 到过 PLACE | 是 | 是 |
| composite error 60 拒绝 | 0 | 0 |
| load ≥200 失败率 | 95% | 95% |

新增的 T06 实例（seed1011）**继续落在同一模式**（err 51、PICK_A 失败、
pin p50 1008ms），是结论的加强而非反例。

**建议**：等批次跑完后再取一次终值；本报告的**因果结论不需要改**，只有分母会变。

---

## 附：证据索引

| 结论 | 证据位置 |
|---|---|
| PICK 阶段失败 19/20 | `T0[56]-*/sim/episodes/*.json` → `final_state.fsm_trace` |
| box 未跟随抬升 | `T05-train-seed1001/sim/skills/pick.jsonl:1-2` |
| servo 自 abort | `T05-train-seed1001/sim/skills/carry.jsonl:13,15,17`；`stack.log:361-363` |
| abort 代码路径 | `src/flexcell/flexcell_skills/flexcell_skills/carry_server.py:571-578` |
| pin 超时写死 1000ms | `carry_server.py:548-549` |
| 租约 500ms | `T05-train-seed1000/sim/world.sdf:14` |
| box_follow 门限 0.03 | `T05-train-seed1001/sim/params.yaml:49` |
| 计划未被拒（error 60 = 0） | 72 个 `sim/skills/composites/*.jsonl` 的 PLAN 事件 |
| T05 第二阶段从未 STARTED | 各 T05 `composites/*.jsonl` 的 STARTED 事件 |
| error 64 链路 | `T06-train-seed1000/sim/skills/observe.jsonl:1`（error 3）+ `composites/composite-61a5826593224036.jsonl` seq1-2 |
| error 64 抛错点 | `contracts/composite.py:97` |
| carry status 3×400ms | `carry_server.py:168-174` |
| T05-seed1000 被 tolerance 拦 | `contracts/composite.py:136`；`plan.json` position_tolerance_m=0.02；fpe=0.0497 |
| 干净批次 6/6 PASS 对照 | `setup/acceptance/evobot_t05_n6_clean_20261111/summary.txt` |
| T06 计划与 T02 同构 | `benchmark/tasks/train/T06-train-seed1000.json`（zone_1, 单阶段） |

**本目录产物**：
- `README.md` — 本报告
- `native_evidence.csv` — 72 个实例的逐条证据（native error / FSM 步骤 / pin 延迟 / composite 码 / stage 进度）
- `load_vs_failure.csv` — 负载-失败剂量反应、阈值分析、pin 延迟全表
