# 24H RESEARCH REPORT — FlexCell Autonomous Sprint（2026-11-09 22:54 → 2026-11-10）

## 0. 一句话结论

**本轮在真实 Gazebo 中达成了 W5 的源码级自主修复：Level B（点名文件）2/2，
Level C（无文件名、无行号、无修复方向，由失败证据自带定位）3/3，
三项门全部 PASS，验收器全程未改。**

同时首次测出"经验复用"的成本收益：agent 读取归档经验并在**不同缺陷**上成功应用，
比无经验的对照臂少 **18.2% 轮次 / 24.6% token / 69% 目录遍历**。

**但有两件事必须同时说清，否则结论会失真：**
1. **我在本轮更正过自己两次**——最初把 Level C 的失败归因为"能力边界"，
   实验证明是 **40k token 预算截断**（P3：给 150k 后无定位也能修好，只是更贵）；
2. **P2 第 ② 项（agent 自主归纳经验）三次尝试全部未达成**，机制已查明：
   它会在任务完成后继续取证，而不是沉淀结论。**它会用经验，但不会写经验。**

工程侧：整改 **13/14 DONE**（1 项缺硬件 BLOCKED），并定位修复了 **6 个工具链缺陷**——
它们正是此前"只读不写"的真正原因。

---

## 1. 完成的内容

### 1.1 W5 Level B — 真实源码修复（本轮最重要结果）

| 维度 | 结果 |
| --- | --- |
| 模型 | `deepseek-flash`（请求 ID = 返回 ID，指纹 `2caaf9b9`） |
| 成功次数 | **2 / 2** |
| 迭代 | 5 / 6 |
| Token | 23,754 / 31,586 |
| 目标 `dual_object` | PASS / PASS |
| 回归 `normal` / `regrasp` | PASS,PASS / PASS,PASS |
| `claim_success` | false / false（结果由验收器测量） |
| 验收器 | **未修改** |

**Agent 实际做的事**：`run_execution` 拿到真实失败 → `read_file` 定位 →
`edit_file` 把 `zones[zone_of[self._obj_a]]` 改回 `zones[zone_of[decision.target]]` → 构建 → 三门 PASS。
`verify.py` 独立断言"先观测失败、后编辑"。

证据：`setup/acceptance/w5_levelb_20261110/`、`setup/acceptance/w5_levelb_n2_20261110/`。

### 1.2 W5 Level C — 去提示对照（单独上报，**不与 Level B 合并**）

| 项 | #1 | #2 |
| --- | --- | --- |
| 成功 | **FAIL** | **FAIL** |
| 迭代 / Token | 8 / 40,307 | 8 / 43,135 |
| 是否运行场景 | 否 | 否 |
| 是否编辑源码 | 否 | 否 |
| 迭代消耗在 | `list_dir`×12、`task.md`、`week1.yaml` | 同 + `run_checks`、`test/`、`launch/` |

**机制**：Level B 的任务文本点名了文件，省下约 4 轮定向；去掉后 agent 在**导航**上耗尽预算，
从未进入"运行场景 → 看证据"的阶段。**它不是诊断错误，是没有机会诊断。**
归因：**任务设计（预算/探索成本）**，n=2 但仍是探索性，标记 **UNKNOWN（不支持更强断言）**。

证据：`setup/acceptance/w5_levelc_20261110/`、`w5_levelc_n2_20261110/`。

### 1.3 P0-2 — E2d / E2e 的 Flash 独立复现（已完成）

| 实验 | 模型 | 迭代 | Token | 三门 | `false_success` |
| --- | --- | --- | --- | --- | --- |
| E2d（可达性配置） | deepseek-flash | 2 | 2,573 | PASS/PASS/PASS | false |
| E2e（对象注册） | deepseek-flash | 5 | 6,952 | PASS/PASS/PASS | false |

证据：`setup/acceptance/w5_e2_flash_20261110/`。两项均为**新模型下的独立复现**，
与历史 chat4/v4pro 运行分开记录，不合并统计。

### 1.4 工程整改（FLEXCELL-REMEDIATION-2026-01）

**13/14 DONE，1 BLOCKED（缺硬件）**。详见 `docs/remediation/FINAL_REMEDIATION_REPORT.md`。

关键项：停止确认 + 运动隔离（P0-A/B）、世界新鲜度（P1-A）、拒绝码分类（P1-B）、动作顺序（P1-C）、
夹爪反馈（P1-D）、对象注册表解耦（P1-E）、日志完整性（P1-F）、预算生命周期（P2-A）、
决策记录（P2-B）、几何工具（P2-C）、时间域（P2-D）、感知边界（P2-E）。

新增测试 **13 文件 / 119 项**，全仓 **0 failed**；真实栈三场景多次 PASS。

### 1.5 工具链缺陷（解释此前"只读不写"的真正原因）

| # | 缺陷 | 后果 |
| --- | --- | --- |
| T1 | `search_code` 对**文件路径**用 `rglob` | 恒返回 `(no matches)`，agent 无法定位代码 |
| T2 | `export/_wsl` 对 POSIX 路径 `split(":")[1]` | 每次 `run_execution` 抛 `IndexError`，**从未拿到失败证据** |
| T3 | 无条件调用 `wsl` 可执行文件 | WSL 内 `FileNotFoundError` |
| T4 | 进度提示未显示已执行次数 | agent 反复阅读而不运行 |
| T5 | `T-W5S` 预算 10 轮 / 文件 1436 行 | 预算不足 |
| T6 | 工具**参数**未记录 | 失败不可诊断 |

**研究问题的回答**（E2c"只读不写"）：
本轮证据支持 **"是 Agent 任务组织与工具可用性问题，而非特定模型的固有行为"**：
同一模型在 T1–T4 修复后**立刻**开始运行场景并写入源码。
但**不能**说"模型一定能做好"——Level C 显示定向成本仍是真实瓶颈。

---

## 2. 失败的内容

| 项 | 状态 | 原因 |
| --- | --- | --- |
| Level C（2 次） | **FAIL** | 预算耗尽截断（40k），**非能力结论** |
| Level C′（作废 3 次） | **INVALID** | 判分 `HARNESS_ERROR` / Windows 无法启动 `wsl` |
| **Level C′（有效 1 次）** | **FAIL** | 预算耗尽截断（+28%）；**P3 已证明给足预算可成功** |
| **C14 工具清单（1 次）** | **FAIL** | 预算耗尽截断（+33%）；`search_code` 仍 0 次 |
| **P2 旧实验（1 次）** | **INVALID** | 预算截断（54k），结论作废，已在 150k 下复做 |
| Track B Hybrid 新实验 | **NOT_RUN** | 优先级低于 W5 |
| Track C 机制问题（C11 之后） | **BLOCKED** | C13 已预注册并尝试 3 次：受约束世界需改动冻结的 `world_sha256`，与"不放宽验收"原则冲突 |
| 真机安全 | **NOT_RUN** | 无硬件 |
| 隔离态仿真实测 | **DONE（本轮）** | 通过 `stop_cancel_timeout_s=0.0` 在真实图中触发 |

> **关于"失败"的更正**：Level C′/C14/P2 旧实验的失败**全部由预算截断造成**，
> P3 实验已证明同一缺陷在 150k 预算下可被修复。因此这些运行**不构成能力结论**，
> 只证明"在 40k 预算下不够"。详见 §11。

**前 6 次 Level B 尝试全部失败**，全部归因于工具链缺陷（T1–T3），不是模型能力。
这段失败记录完整保留在 `events.jsonl` 与本文档中。

---

## 3. 研究发现

1. **验证工具本身就是研究变量**。前 6 次"agent 不写代码"的结论是**错的**——真正的阻塞是
   `run_execution` 从未成功返回过一次。任何"agent 不行动"的观察，必须先证明工具返回了有效反馈。
2. **位置提示贡献显著**。Level B 点名文件 vs Level C 不点名：2/2 vs 0/2，
   差异体现在**前 4 轮的定向成本**上。这是能力边界的直接测量，不是模型的失败。
3. **"不谎报"是可验证的**。四次运行 `claim_success=false` 且 `false_success=false`，
   成功完全由外部验收器判定。
4. **真实栈能发现单测发现不了的问题**。整改过程中两次：新鲜度上界与 7 s 腿时长冲突、
   刷新写入 history 打断策略顺序——单测全绿时仍然会崩。

---

## 4. W5 能力成熟度与严格边界

| 等级 | 定义 | 状态 |
| --- | --- | --- |
| Level A | 配置参数修复 | **已达成**（历史 E2d 6/6、E2e 3/3） |
| **Level B** | **源码级修复，有位置提示** | **已达成（2/2，本轮首次）** |
| **Level C** | 源码级修复，无位置提示（**证据自带定位**） | **已达成（3/3）** |
| **P2 经验复用** | 读取归档经验并跨缺陷应用 | **已达成，且有成本收益**（n=1/臂） |
| Level D | 跨任务经验迁移 | 未开始 |

**严格边界**：
- n=2（B）/ n=3（C）/ n=1（P2 双臂），**探索性，不是统计证据**，不得计算置信区间；
- 单一缺陷类型（阶段转换/目标对象选择），**不代表任意缺陷**；
- 成功依赖充足预算（40k 不够、150k 足够）与工具修复——**预算是本轮最关键的混淆变量**；
- 仅在仿真，无真机；
- Level C 结果**不得**与 Level B 合并统计；
- **P2 第 ② 项未达成**，不得宣称"agent 能自主归纳经验"。

---

## 5. Track A / B / C 进展

| Track | 本轮进展 | 阻塞 | 下一步 |
| --- | --- | --- | --- |
| **A**（执行安全/整改） | **13/14 DONE**；隔离态**首次在真实图触发并复位**；最终回归离线 0 failed、Gazebo 3/3 PASS | P0-C 缺硬件 | 真机安全链；PLACE 超时路径单独验证 |
| **B**（Hybrid Runtime） | **完成证据审计**（`docs/TRACK_B_ASSESSMENT.md`）：协议可运行、**69 项路由测试通过**；E-021 三臂 CI 全重叠，成功率负向、成本更高 | 缺"两策略会分歧"的场景 | 构造判别场景（必须保留 FSM 对照）；构造不出则记负结果 |
| **C**（FSM/MTC） | C13 **预注册后 BLOCKED**（3 次尝试） | 受约束世界需改动冻结的 `world_sha256` | 以新 scenario id 注册并**重算哈希**，先离线证明 legacy 必失败 |

**三条主线都没有"没做"**：A 有结论，B 有审计结论，**C 本轮解封并拿到首个机制差异证据**。

## 6. 本地提交（**37 个，已推送到 origin 分支，未合并**）

分支 `autonomous/flexcell-remediation`，基线 `ebe27f07881200ab0fc74dfaa5490208023bf9d9`。
**远端可见**（按用户要求推送，未合并、未开 PR）：

- 提交列表：https://github.com/Yenefa/flexcell/commits/autonomous/flexcell-remediation
- 与 main 对比：https://github.com/Yenefa/flexcell/compare/ebe27f0...autonomous/flexcell-remediation

| SHA | 内容 |
| --- | --- |
| `70d7dc0` | research: 24h sprint - Flash default, Level B harness, tooling root cause, C12 |
| `fefd628` | fix(safety): verified skill cancellation and motion quarantine (P0-A) |
| `1dd4543` | fix(execution): real world freshness and a physical safety readiness report |
| `64136eb` | fix(safety): a gate rejection keeps its typed cause (P1-B) |
| `ec2ee41` | fix(safety): reject out-of-order actions before dispatch (P1-C) |
| `da06b2a` | fix(skills): a completed GripperCommand is not evidence of a grasp (P1-D) |
| `43f5e27` | fix(execution): refresh a stale world instead of widening the freshness gate |
| `3273a65` | test(p0a): cancel a live PICK on the real stack and check the safety contract |
| `81a4c47` | refactor(skills): scope the object registry to its node (P1-E) |
| `25c3216` | fix(execution): episode and log integrity, one decisive finish (P1-F) |
| `1ba8db8` | fix(budget): release provably-unsent reservations, never crash on anomalies (P2-A) |
| `5f1eec9` | fix(time): a joint state that never arrived must not look fresh (P2-D) |
| `4e3577e` | docs(perception): pin the ground-truth / camera boundary, plan the real one (P2-E) |
| `768e54b` | refactor(fsm): one builder owns the decision-log record (P2-B, first slice) |
| `72963a5` | refactor(move): extract the pure quaternion helpers (P2-C, first slice) |
| `f6a074d` | research(w5): first real Level B source repair, and the tool defects that blocked it |
| `d091d53` | research: Level B replication, Level C negative result, 24H report |
| `18d406f` | research: Level C-prime attempted twice, both invalidated by the judge harness |
| `2c35b29` | research(p0-2): reproduce E2d and E2e with deepseek-flash |
| `29c4cf6` | test(p0a): make the motion quarantine actually engage in a live ROS graph |
| `49a19c1` | research(track-c): pre-register the MTC capability test, then record it BLOCKED |
| `26b7d3a` | docs: close the 24h sprint report with the full commit trail and final regression |
| `6f7850d` | research(track-w5): Level C-prime now has a VALID verdict - and it is a negative one |
| `7fd0e82` | research(w5): a visible tool inventory does not change tool choice (C14, H0) |
| `e871e18` | research(w5): Level C achieved - evidence that carries its own location |
| `7f27b76` | research(w5): Level C repeats - evidence-localised repair passes twice |
| `bd7e7fc` | research(p2): machine-readable failure reports and experience records, built from the archived runs - and what they still do NOT establish |
| `8fccfa4` | docs: experiment ledger extracted from origin/main, plus the version reconciliation |
| `1430be6` | correct(evidence): the Level C failures ended at the token budget, and that changes what they support |
| `5bdbc64` | research(w5): third Level C replicate passes; branch now visible on the remote |
| `f784dc4` | research(p3): the Level C failures were budget truncation, not a capability limit - and this overturns my own attribution |
| `69fba98` | research(p2): at a workable budget the agent reads a stored experience and applies it to a DIFFERENT defect - first evidence for item (3) |
| `505f019` | research(p2): a control arm turns the reuse result into a measured cost saving |
| `81edb30` | docs: reconcile the 24h report after three rounds of correction, and record the final regression |
| `0e55c1a` | test(evidence): every sprint result now has a verifier that can be run independently |
| `81b9a69` | research(p2): asking the agent to write its own lesson failed three times - recorded as a negative, with the harness bug separated out |
| `986eba6` | research(track-b): the hybrid runtime audit the sprint asked for - and why I did not add samples |

> 本表由 `git log origin/main..HEAD` 生成，非手工抄写。

## 6b. 最终回归（收口实测，2026-11-10 18:00）

| 项 | 结果 |
| --- | --- |
| `flexcell_interfaces` 构建 | **OK** |
| `flexcell_skills` 构建 | **OK** |
| 全仓离线套件（排除 `test_parity_report.py`） | **PYTEST_RC=0，0 failed** |
| 真实 Gazebo `normal` | **PASS** 14.2 s |
| 真实 Gazebo `dual_object` | **PASS** 28.9 s（两条腿 6 步） |
| 真实 Gazebo `regrasp` | **PASS** 14.3 s |
| Git 工作区 | **干净** |

> 注：首次回归出现 `ImportError: RunComposite`，原因是只构建了 `flexcell_skills` 而未重建
> `flexcell_interfaces`（Action 生成的 Python 模块缺失）。补建后全部通过——**环境问题，非代码回归**。

## 7. 资源与合规

- Gazebo 并发：始终 **1 个**高负载实验；每个实验独立 `GZ_PARTITION` + `ROS_DOMAIN_ID`；
- 付费运行：本轮 **20 次**（含 4 次经验写作尝试），归档运行为 **721,798 tokens**（实测加总），
  按峰值未缓存上界 ≈ **1.5–5.8 RMB**，远低于 20 RMB 上限；**未充值、未购买硬件或云服务**；
- FlexCell 内部推理账本：173 次调用，`committed_upper_bound` **0.60 RMB / 5 RMB（11.97%）**——
  注意该账本只覆盖产线推理路径，**不含 pilot 直连 API 的用量**，两者不可混淆；
- 未连接真实机械臂，未做任何真实硬件动作；
- **未修改冻结验收器**：`gate/acceptance.py` 在全部 16 次运行中内容不变（1488 B）。

---

## 8. 下一轮 24 小时建议（不自动开启）

本轮已完成的，不再列为"下一轮建议"：Level C′（有有效结论）、E2d/E2e Flash 复现、
隔离态真实触发、P2 经验复用（双臂对照）。

### 建议 1（最高信息价值）：让 agent 写得出经验

第 ② 项三次尝试全部失败（§14），机制已查明：**任务完成后持续倾向继续取证，而非沉淀结论**。
可证伪命题：把 write-up 做成**任务成功的必填字段**（不填则任务不判完成），
或改用独立"复盘 agent"读取执行记录，若仍无记录，则"自主归纳"在本模型上不成立。

### 建议 2：Track C 的机制实验（已解封，下一步缩小顶板重跑）

已完成：`constrained_approach` scene 以**增量**方式注册，默认世界哈希实测未变，
同一世界下 legacy 卡在 `PLACE_A`、MTC 通过 `PLACE_A`+`VERIFY_A`。
下一步：把顶板缩小到只覆盖 box A（或抬高到 z=0.20）后重跑两臂，才能判断完整任务上是否成立。

### 建议 3：Track B 的判别场景

E-021 三臂 CI 全重叠（§Track B 评估）。需要一个**两种策略会给出不同决策**的场景
（观测噪声使 FSM 规则选错、模型能纠正），且**必须保留 FSM 对照臂**。
若构造不出，如实记为负结果并把资源转回 FSM 可靠性。

### 建议 4：真机安全链（BLOCKED，需硬件）

P0-C 的清单与评估已交付，但所有"真机行为"项目均为 **NOT_VERIFIED**。
在获得硬件与急停装置前，**不得在真机上运行本仓库任何运动代码**。

---

## 9. 三个负结果的机制区分

| 实验 | 看到证据 | 编辑 | **终止原因** | 失败机制 |
| --- | --- | --- | --- | --- |
| Level C（2 次） | 否 | 否 | 预算耗尽 | 探索成本 |
| Level C′（1 次有效） | **是，9 次** | 否 | **预算耗尽（+28%）** | 定位成本吃光预算 |
| **C14（1 次）** | **是，8 次** | 否 | **预算耗尽（+33%）** | **工具选择：只 `list_dir` 28 次** |
| **C15 对照（2 次）** | 是，4–5 次 | **是** | 正常结束（用 42–55%） | 定位信息把成本降到 1/3–1/2 |

> **更正（2026-11-10 晚）**：此前写成"agent 看到证据但不编辑"属**解释**而非事实。
> 复核 `events.jsonl` 发现三次失败均触发 `budget_exceeded`（`runner.py:107`，上限 40k），
> 即被**强制截断**。因此不能断言"再多给预算也修不好"。
> 详见 `docs/experiments/CORRECTION_20261110B.md`。


**结论**：定位成本是**主导项**——无线索时它把运行推过 40k 预算上限（+28%~+35%），
有线索时同样任务只用 42–55% 预算即完成。
Level B 之所以成功，是因为任务文本**点名了文件**，等于替它完成了搜索这一步。

**下一轮唯一正确的攻关方向**（不是加提示）：
1. 让**失败证据自带定位**（失败时输出涉及的代码区域/符号）；或
2. 提供**强制先缩小范围**的检索工具（按错误码/阶段直接定位相关分支）；
3. 然后重跑 Level C′，检验"定位成本能否被工具消除"。

---

## 10. Level C 达成

C14 证明"工具清单不改变工具选择"，由此得到的攻关方向是**改变信息获取界面**。
C15 实现：`run_execution` 的失败证据**自带定位**（`suspect_regions`，由失败阶段/对象推导出的相关代码区域），
**不给行号答案、不给正确写法、不给修复方向**，任务文本与 Level C′ 逐字相同。

| 项 | 值 |
| --- | --- |
| 迭代 / Token | 4/16,937、5/22,077、5/23,258（**n=3，3/3 PASS**） |
| `list_dir` 次数 | **0 / 0 / 0**（C14 为 28） |
| 目标 `dual_object` | **PASS** |
| 回归 `normal` / `regrasp` | **PASS / PASS** |
| `claim_success` / `false_success` | false / false |
| 编辑 | `zones[zone_of[self._obj_a]]` → `zones[zone_of[decision.target]]`（正确） |

**这是本轮最重要的结果**：第一次在**无文件名、无行号、无修复方向**的条件下完成真实源码修复并通过三门独立验收。
与 Level B 的差别是本质性的——Level B 用**提示**替代了搜索，C15 用**证据**替代了搜索。

**诚实边界**：**n=3 完整归档，三次均 PASS**；单一缺陷类型；仍为探索性样本量。
另有一次同配置运行也 PASS，但其原始产物在 WSL 重启时丢失，**不计为证据**。

### 完整能力阶梯（最终）
| 等级 | 条件 | 结果 |
| --- | --- | --- |
| Level A | 配置修复 | **PASS**（历史 6/6、3/3；本轮 Flash 1/1 + 1/1） |
| Level B | 源码修复 + 点名文件 | **PASS 2/2**（5–6 轮） |
| **Level C（C15，证据定位）** | 源码修复 + **无提示** | **PASS 3/3**（4–5 轮） |
| Level C′ / C14 | 无提示 + 先运行 / 工具清单 | **FAIL**（**预算截断**，非能力边界） |
| C14 | 无提示 + 工具清单 | **FAIL 1/1**（工具选择） |
| **C15** | 无提示 + **证据自带定位** | **PASS 3/3**（4–5 轮） |

---

## 11. 更正 #2：Level C 失败 = 预算截断

更正 #1 发现三次失败均 `budget_exceeded`（40k 上限），但**未验证**"多给预算会怎样"。
P3 实验补上这一环：**唯一变量**是预算 40k → 150k，定位信息**关闭**，任务文本不变。

| 条件 | 迭代 | Token | `list_dir` | 结果 |
| --- | --- | --- | --- | --- |
| 无定位 + 40k | 截断 | 51k–54k | 12–34 | **FAIL** |
| **无定位 + 150k** | 10 | 48,067 | **34** | **PASS** |
| **有定位 + 40k** | **4–5** | **16,937–23,258** | **0** | **PASS** |

### 被推翻的说法
| 我曾写 | 实际 |
| --- | --- |
| "定位成本是硬约束，无定位无法完成" | **错**：给足预算能完成 |
| "Level C′ 卡在证据→定位" | **不准确**：卡在预算，遍历最终收敛 |
| "C14 失败机制是工具选择" | **不完整**：低效但可克服，只是更贵 |

### 仍然成立的净发现
**定位信息改变的是成本，不是可行性**：
- 迭代 **10 → 4–5**（−50%~60%）；
- Token **48k → 17–23k**（−52%~65%）；
- 目录遍历 **34 → 0**。

### 连带作废
**P2 经验复用实验（54,142 tokens，被截断）只能记 INVALID，不能记 H0。**
下一轮须在 150k 预算下重做。

### 写死的规则
> **任何 `budget_exceeded` 的运行，"未做某事"都不能作为能力证据。**

---

## 12. P2 经验复用（双臂对照）

旧 P2 实验被预算截断（54k），按更正规则作废。复做：

| 项 | 值 |
| --- | --- |
| 缺陷 | **VERIFY 分支**（非 PLACE，症状相同） |
| 定位信息 | 关闭 |
| 唯一额外输入 | 已归档的经验记录 |
| 迭代 / Token（有经验） | **9 / 91,664** |
| 迭代 / Token（**无经验对照**） | 11 / 121,496 |
| 三门 | **PASS / PASS / PASS**（两臂） |
| agent 是否读了经验 | **是**（对照臂已断言未读） |

agent 修复时**自己写了注释**，指出"用固定对象会让第二个对象对 zone_1 做验证"，
这与经验文件记录的缺陷模式（target-object selection）一致——是**模式复用**，不是照抄行号。

### 目标 §4 三项区分
| 要求 | 状态 |
| --- | --- |
| ① 人工编写的修复提示 | 存在（Level B） |
| ② Agent **自主归纳**的经验 | **经三次尝试仍未达成**（见 §16） |
| ③ Agent **真正复用**的经验 | **首次有证据** |

**可以说"开始实现 Experience-Driven Improvement"，但必须同时声明经验由工程师归纳。**

### 双臂对照（事后补，已声明）
| 指标 | 有经验 | 无经验 | 差异 |
| --- | --- | --- | --- |
| 结果 | PASS | PASS | 两臂都成功 |
| 迭代 | **9** | 11 | **−18.2%** |
| Token | **91,664** | 121,496 | **−24.6%** |
| `list_dir` | **18** | 59 | **−69%** |

**判定：`P2_EXPERIENCE_REUSED_AND_CHEAPER`**

### 诚实边界
- **n=1 / 臂**，探索性；
- 两臂都成功，所以证明的是**成本收益**，不是**可行性差异**；
- 经验的生产者仍是人（第 ② 项未达成）；
- 对照臂是看到实验臂结果后补的，已在预注册中声明。

---

## 13. 第三方复核入口

每个证据目录都带独立 `verify.py`，**不依赖本报告的叙述**。一条命令跑完全部：

```bash
bash ci-public-window/scripts/verify_all.sh
```

| 证据目录 | verdict | rc |
| --- | --- | --- |
| `w5_levelb_20261110` | `W5_LEVELB_REAL_SOURCE_REPAIR` | 0 |
| `w5_levelb_n2_20261110` | `W5_LEVELB_REAL_SOURCE_REPAIR` | 0 |
| `w5_levelc_evidence_20261110` | `W5_LEVELC_ACHIEVED_WITH_EVIDENCE_LOCALISATION` | 0 |
| `w5_levelcprime_20261110` | `LEVEL_C_PRIME_VALID_NEGATIVE` | 0 |
| `c14_tool_inventory_20261110` | `C14_H0_TOOL_CHOICE_NOT_FIXED_BY_INVENTORY` | 0 |
| `p3_budget_noloc_20261110` | `P3_BUDGET_NOT_CAPABILITY_LEVEL_C_FAILURES_WERE_TRUNCATION` | 0 |
| `p2_reuse_budget_20261110` | `P2_EXPERIENCE_REUSED_AND_CHEAPER` | 0 |
| `p2_reuse_20261110`（旧） | `P2_OLD_RUN_VOID_NO_ARTEFACTS_AND_BUDGET_TRUNCATED` | 0 |
| `w5_e2_flash_20261110` | `E2_FLASH_REPRODUCED` | 0 |
| `p0a_quarantine_20261110` | `P0A_QUARANTINE_ENGAGED_AND_CLEARED` | 0 |

**注意最后两行**：旧 P2 目录的 verifier **断言它是无效的**，而不是假装它有结论——
这样任何人都不能把作废的运行当成证据。

另外两个仅作历史保留、**不参与结论**的目录已在各自 `README.md` 标注：
`w5_levelc_20261110`、`w5_levelc_n2_20261110`（均为 40k 预算截断）。

---

## 14. P2 第 ② 项：agent 自主归纳经验（四次尝试未达成）

目标要求区分"人工提示 / agent 自主归纳 / agent 复用"。第 ③ 项已达成（§14），
第 ② 项本轮做了三次尝试，**均未达成**，如实记录。

| # | 迭代 | Token | 修复 | write-up 轮 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 1 | 3 | 14,918 | PASS | **否**（harness 缺陷） | 0 次记录 |
| 2 | 4 | 20,873 | PASS | 是 | **又跑了一遍场景**，未记录 |
| 3 | 3 | 23,958 | PASS | 是，工具箱收窄到只剩记录+读取 | 尝试 `read_telemetry`（被拒），未记录 |
| **4** | **4** | **44,488** | PASS | **记录声明为交付物 + 3 次重试** | **三次重试全在试被禁工具，从未调记录工具** |

### 第 1 次是我的 bug
`runner.py` 在判定 PASS 时**立即 break**，agent 根本没拿到 write-up 那一轮。
这不是 agent 的行为证据。已加**可选** `post_pass` 钩子（默认关闭，不影响任何历史结果）。

### 第 2、3 次是真实行为
- 明确要求"不要再跑场景，写下来"→ agent **仍然再次运行场景**；
- 把工具箱收窄到只剩 `record_experience` + `read_file` → agent **仍在试图获取更多证据**，
  始终没有调用记录工具。

### 判读
**未达成的机制不是"不会写"，而是"任务完成后持续倾向继续取证，而非沉淀结论"。**
**四种推动方式（提示 / 强制轮次 / 收窄工具 / 声明为交付物）均未改变该倾向。**

第 4 次尤其说明问题：任务明确写"不调用 record_experience 就不算完成"，并给 3 次重试、
每次只开放记录工具，agent 仍三次尝试**被禁止的工具**、读**不存在的文件**，
**宁可反复失败也不调用那个唯一被允许的工具**。

### 边界
- 三次属于**同一配置的不同推动手段**，不是独立重复；
- **修复每次都成功**（三门 PASS），所以这不是能力问题；
- 不影响第 ③ 项：agent 确实会**读取并使用**别人写的经验（§12，−18.2% 轮次）。

### 这给出下一轮最明确的题目
**让 agent 写得出经验**（而不是只会用经验），比让它多修几个 bug 更有信息价值。
可能方向：把 write-up 做成**任务成功的必填字段**（不填则任务不算完成），
或用独立的"复盘 agent"读取执行记录来生成经验。
