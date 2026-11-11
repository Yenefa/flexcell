# EvoBot Capability Report — 2026-11-12 (round 2)

**按 goal §20A：明确区分 Existing / Newly Acquired / Failed / Unverified / Requires Human Approval。**
等级阶梯不越级：Designed → Implemented → Unit Tested → Simulation Tested → Independently Verified → Generalization Tested。

> **一句话结论**：本轮把 T08 从「不可判定」推进到「可判定」，拿到了**项目史上第一个 `passed=true`**
> （S/t3，117.32 mm，九门全过，Lead 独立复核），并**反转了上一轮「恢复 4/5 优于基线 2/5」的叙事**
> （本轮 R 0/5、S 1/5，Fisher p=1.0）。但**泛化仍然未测**：六个"未见"试次实际跑的是 **dev 世界**，
> 被按未见几何评分，**已整体作废（INVALID_INFRA）**——本轮一度据此宣布"0/6 不迁移"，该结论已**撤回**。
> 另发现验收器**不能抵抗伪造的产出方**、记录器会静默摧毁有效证据（已发生两次）、
> 以及**harness 无法按 spec 设置物体初始位姿**这个更根本的阻塞。
> **Level 4 Develop 仍未跨过；T08 = 单 dev 实例 1/9。**

| 项 | 值 |
| --- | --- |
| HEAD | `a6fe30af`（`autonomous/flexcell-remediation`） |
| 终态评测器 | `evaluate.py` **v0.5.0**（本轮未改，冻结数字未动） |
| 证据验证器 | `benchmark/evidence/verify.py` **v1.0.0**（审计发现 2 门可被击穿、2 门空转） |
| 证据 schema | `t08-evidence/1.0` |
| 30 mm 阈值 | **未改** |
| 离线测试 | `benchmark/evidence/` **75 passed**；门审计新增 **6 passed + 14 xfail(strict)** |
| LLM 调用 | **0**（全轮无付费调用） |
| Gazebo 运行 | arm R 5 次 + 既有历史运行 |

---

## 1. Existing（本轮之前存在，本轮复核）

| 能力 | 等级 | 证据 |
| --- | --- | --- |
| T01–T06 TaskSpec + 生成器 + 执行器 + 独立验收 | **Simulation Tested** | `benchmark/tasks/train/`(72) + `val/`(36) |
| Baseline A-v2（确定性执行器） | **Simulation Tested** | `evobot_a_v2_final_20261111/`，71/72 |
| A-v2 的**版本稳健性** | **CONFIRMED（本轮新增复核）** | 用 v0.5.0 重评 72 个归档观测 → **72/72 一致，0 分歧**，`evobot_lead_regression_v050_20261112/` |
| held-out OS 级隔离 | Independently Verified（仅机制） | `evobot_heldout_isolation_20261111/` |
| Baseline B 真实执行 | **Simulation Tested** | 9/9，False Success 0，`evobot_p0_paired_20261112/` |
| T08 轨迹证据验证器 v1.0.0 | **Unit Tested** | 75 测试；但见 §3.2 |

---

## 2. Newly Acquired（本轮真正新增）

**严格地说：本轮没有新增任何机器人任务能力。** 新增的是**判定能力**与**缺陷知识**。

| 项 | 等级 | 证据 | 为什么不算机器人能力 |
| --- | --- | --- | --- |
| T08 首次**完整证据包**运行（terminal + 9 门同源） | **Simulation Tested（判定链）** | `evobot_t08_evidence_loop_20261112/evidence/{R,S}/` | 判定链可用，但通过率 1/9 |
| **项目史上第一个 T08 `passed=true`**（S/t3） | **Simulation Tested（单实例 1/5）** | `evobot_lead_t08_first_pass_20261112/`（Lead 独立复核 6 项） | 单实例、dev 集、1/5，**不构成能力** |
| 证据包与终态**同源绑定**（rest_height 从 spec 推导、max_z 从原始物理日志重算） | **Independently Verified（机制）** | 独立 lane 重评 0 分歧；`rest_height_from_spec == declared_to_recorder == 0.0175` | 是测量链路，不是操作能力 |
| **首个可判定的 T08 否定结果** | **Simulation Tested** | arm R：terminal 1/5，passed 0/5 | 否定结果本身是知识，不是能力 |
| 反向抛掷作为**跨臂可复现**的主失效模式 | **Simulation Tested**（两独立臂） | arm R 4/5 cos≈−1；早期单发臂 3/5 反向 | 现象确认，机制仍 UNKNOWN |
| 验收器**抗伪造**能力缺陷的系统性证据 | **Unit Tested + 复现** | `evobot_t08_gate_audit_20261112/`：5 PROVEN / 2 DEFEATED / 2 VACUOUS | 是审计产物 |

---

## 3. Failed（本轮确证失败）

### 3.1 T08 推动技能仍然不是可用能力

| 臂 | n | terminal_passed | passed | 主要失效 |
| --- | --- | --- | --- | --- |
| 闭环恢复 arm R（本轮，完整证据） | 5 | **1/5** | **0/5** | 4/5 物体被推**向反方向**（cos ≈ −1）；R/t4 因记录器缺陷判 INVALID_INFRA 并**排除出分母** |
| 单发基线（历史，同接触高度 0.0200） | 5 | 2/5 | 0/5 | 2/5 反向 |
| 单发基线（历史，接触高度 0.030） | 1 | 0/1 | 0/1 | 连接触都未建立（0.59 mm） |

**这反转了上一轮的叙事。** 本轮完整证据批次：

| 臂 | terminal | passed |
| --- | --- | --- |
| R（闭环恢复） | 1/5 | **0/5** |
| **S（单发）** | 2/5 | **1/5** |

Fisher 精确检验（有效试次）：passed **p = 1.0000**，terminal **p = 1.0000**。
**两臂在 n=5 下不可区分。** 正确读法不是「恢复变差」，而是**两臂都被 run-to-run 方差主导**，
上一轮的 4/5 本身就在方差内（Lead 统计审计早已给出 p=0.5238）。要分辨 80% vs 20% 需约 **9.5 次/臂**。

**主失效模式（9 个有效试次）**：`FAIL_DIRECTION` **4**（cos ≈ −1，物体被推**向反方向**）、
`FAIL_LIFT` 1、`FAIL_ZONE` 1、`FAIL_OVERSHOOT` 1、`GATE_GRIPPER` 1、**PASSED 1**。
机制 **UNKNOWN**；形态已确立（接触面维持不住，重试无法修复接触几何——与 R 得 0/5 一致）。

**R/t1 的裁定：UNRESOLVED（不是假失败，也不是已确认的真失败）。** 本轮我先后提出两种解释，**两种都被推翻**：
先称夹爪门有「弧度/米」单位错误——实测 URDF 该关节为 **prismatic**，0.002 本就是 2 mm，**推翻**；
再称门无法区分抓取与接触——但那比较的是**绝对位置**，而门量的是**行程**：标称抓取 21.05 mm（10.5×限值）、
已知非抓取推动 0.00099 mm（0.0005×）、R/t1 3.06 mm（1.5×），**门确实能分开两个已测类别**，**再次推翻**。
3.06 mm 落在**没有任何非抓取测量**的区间内，因此该限值**无法用现有数据判定对错**。保留 `passed=false`。

### 3.2 验收器不是 fail-closed against 一个会伪造的产出方

| 门 | 判定 | 说明 |
| --- | --- | --- |
| terminal / trajectory / protected_unmoved / no_attachment / no_teleport | **PROVEN** | 各有具名负例 |
| `table_support` / `no_lift` | **DEFEATED** | 依赖 `rest_height_m`（产出方自报）；常数高度搬运可全过 9 门 |
| `pusher_contact` | **VACUOUS** | `pusher_links` 自报，声明地板即可通过 |
| `manifest.bundle_sha256` | **无门验证** | 只校验 `isinstance(str)`，清零不改变任何结果（Curator 发现） |
| `gripper` | **VACUOUS（n=1 时）** | 单样本跨度恒为 0 |

**关键校准（必须连这句一起引用）**：验证器**对诚实但损坏的记录器是 fail-closed 的**，
**对伪造的产出方不是**。本轮**没有产生任何 T08 `passed=true`**，因此**没有虚假能力被宣称**；
缺陷在于**验证器无法认证**，不在于有人做了错误宣称。

**范围更正（Lead 自我更正）**：初稿称「6 门依赖自报值」。实测 `verify.py` 中
`rest_height_m`(2)、`pusher_links`(2)，而 `max_z_m`/`bundle_sha256`/`max_gap_ns`/`dropped_samples`
**出现 0 次、无门读取**。**实际是 3 门**，且 `table_support` 是双侧的，故常量重声明会触发它。
另有一处不在初稿清单内的真缺陷：`manifest.bundle_sha256` 只校验 `isinstance(str)`，**无门验证封印**。

### 3.3 记录器：单步接触会静默摧毁整个证据包

`recorder.contact_intervals()` 把区间终点设为其首个接触步，因此**恰好持续一个 5 ms 物理步**的接触
被写成 `[t, t]`；`schema.py` 正确拒绝，**9 门全部变为不可评估**。实测 R/t4：
`intervals[6] start==end, span 0 ns`，1 个 schema 问题，9 门全红。
**在一次干净运行上，这会把有效结果记成机器人失败**——正是 mission 禁止的误分类。
见 `evobot_lead_recorder_zero_interval_20261112/`。

---

## 3.4 泛化：**未测**（六次"未见"运行已作废）

**本轮曾一度宣布"unseen 0/6，泛化失败"。该结论已撤回。**

六个 `t08_unseen` 试次（seed 3000/3001/3002 × 恢复/单发）**实际跑的是 dev 世界**：
`sim_profile.py` 硬编码了 `target_box_a (0.22, 0.00)`、`target_box_b (0.20, −0.18)`，
**不接受任何 per-instance 位姿参数**。六个 `sim/world.sdf` 全部相同，等于 dev spec。

| Seed | spec 声明 A 的 XY | 世界实际 A 的 XY | 偏移 |
| --- | --- | --- | --- |
| 3000 | (0.210, 0.030) | (0.220, 0.000) | **31.6 mm** |
| 3001 | (0.230, −0.070) | (0.220, 0.000) | **70.7 mm** |
| 3002 | (0.190, 0.020) | (0.220, 0.000) | **36.1 mm** |

**所以这六次是用 dev 几何跑了六遍，再拿未见几何去评分。**
判定：**INVALID_INFRA (Environment)**，不是未见任务的测量。

**连带的两个观察也随之作废**：

1. 「蓝块被移动 0.030/0.010/0.050 m」← **这是 Lead 自己的错误**。ground truth 显示
   `target_box_b` 的世界位移在六次中均为 **0.000000 m**。子句的 `distance_m` 是
   **spec 声明起点与世界实际终点之差**，不是机器人造成的位移。
2. 位移数值也被扭曲，且两个方向都有：U/seed3000 评分读到 147.45 mm（未超 150 上限），
   世界基准实测 **155.32 mm**（**超上限**）；U_shot/seed3002 读到 54.82 mm，
   实测 **19.85 mm**（**低于 30 下限**）。

**护住的部分**：dev 的 seed2000 spec 与世界**完全一致**（delta 0.000 m，已在 R/t1、S/t3 核实），
因此 **dev 的 R/S 表、S/t3 的 `passed=true`、9 个有效 dev 试次的失效分类全部有效**。

**这暴露的阻塞比一个实验臂更根本**：本 benchmark 中**任何**任务都从未按其声明的初始位姿被实例化过，
除非 spec 恰好与硬编码世界重合（dev 就是如此）。所以 `benchmark/tasks/val/` 以及任何重新生成的
spec 同样无法实例化；**早前轮次的 held-out 泛化结果（`evobot_heldout_n6_20261111/`）也需要先用这个
缺陷复核其初始位姿，在此之前不得再引用**（该检查**尚未做**，状态 UNKNOWN）。

详见 `evobot_lead_t08_unseen_20261112/`（撤回文档 + `check_world_poses.py`）。

## 4. Unverified（代码/文档存在，无有效执行证据）

| 项 | 状态 | 依据 |
| --- | --- | --- |
| **真正的 A′/B 配对执行** | **NOT_RUN** | 归档的「A′」列实为 **oracle**（72/72 字节级复现）；`evobot_p0_paired.sh` 的 Python heredoc **无法编译**，全仓无 `paired.tsv` |
| Baseline C 完整事件链 | **NOT_RUN** | 骨架 + 离线测试，从未在 Gazebo 跑完整链 |
| Baseline D | **UNKNOWN（未定义）** | 全仓无定义；goal §7.5 仅为建议 |
| T08 unseen 3000–3002 | **NOT_RUN —— harness 无法按 spec 实例化（见 §3.4）** | `evobot_lead_t08_unseen_20261112/` |
| 早前 held-out 泛化（`evobot_heldout_n6_20261111/`） | **UNKNOWN — 需用同一缺陷复核初始位姿，复核前不得引用** | 未检查 |
| T07 / T09 / T10 | **NOT_RUN（无 spec）** | |
| 真机 | **BLOCKED** | 无硬件 |
| 任何 Development Skill 的有效性 | **NOT_MEASURED** | 采用率 **0/4**；见 §6 |

---

## 5. 基准缺陷（本轮新发现，影响既有数字的解读）

**72 个训练实例中 16 个存在 t=0 即满足的 placement 子句**（4 个完全空转：T05 seed 1001/1007/1009/1010；
12 个部分：每个 T04）。全部来自同一子句：`target_box_a` 初始距 `zone_2` 中心 58.31 mm，
半径 60 mm，**余量 1.69 mm**。

- **不影响** A-v2 的 71/72 或 B 的 9/9（运行确实发生、确实被评分）。
- **影响**「这些数字代表多少次真实操作」：B 执行的 9 个实例中 3 个（全部 T04）含一个白送子句。
- **不得**为此改阈值——半径是冻结参数，改它就是 mission 禁止的「调整验收规则制造成功」。
- 见 `evobot_lead_benchmark_vacuity_20261112/`。

---

## 6. Development Skills（Q5 的答案）

| Skill | 状态 | 本轮采用率 | 对「本轮真实复发 bug」的覆盖 |
| --- | --- | --- | --- |
| ros2-interface-preflight | **PROPOSED** | 0/6 | 自述 6 案例覆盖 **2/6** |
| simulation-process-lifecycle | **PROPOSED** | 0 | 6/6 驱动仍用裸 `pkill` |
| evidence-level-audit | **PROPOSED** | 0 | 本轮真实 bug **0/1** |
| effect-verification | **PROPOSED** | 0 | 本轮真实错误 **0/2** |

**Q5 的一句话答案**：**没有任何 Development Skill 在本轮可测量地降低了错误率或开发成本。**
四个 Skill 全部是事后总结，采用率 0/4，且在真正复发的 bug 上覆盖 0/1 与 0/2。
变异覆盖已更正为 11/11 killed（registry 曾少报为 8）。

---

## 7. Requires Human Approval

| 改动 | 为何需要批准 | 状态 |
| --- | --- | --- |
| `place_server.py` 释放谓词修复（T04 假失败） | 技能层是机器人执行代码 | **PROPOSED，未实施**；位置结论见 `evobot_t04_executor_mismatch_20261112/` §4b（是位置结论，不是授权） |
| `verify.py` **v1.1.0** + `evaluate.py` **v0.6.0** | 改变验收协议 | 补丁准备中，v1.0.0 保持字节不变 |
| `gripper` 门限标定（2 mm 无出处） | 改变成功含义 | **未改**；需 G1/G2/G3 标定实验先行 |
| 三层 lift 限值统一（0.005 / 0.020 / 0.005） | 改变判据 | **未改**；已确认为假拒绝路径 |
| `recorder.py` 零长区间修复 | 冻结文件 | **未改**，已报告 |
| T04/T05 spec 重新生成以消除空转子句 | 使冻结 72 实例集失效 | **未做**；建议先「报告」再「加字段」，重新生成需批准 |

---

## 8. Level 判定

| Level | 状态 | 依据 |
| --- | --- | --- |
| L1 Designed | ✅ | |
| L2 Implemented | ✅ | |
| L3 Unit Tested | ✅ | 75 + 6 passed/14 xfail |
| **L4 Simulation Tested（T08）** | ⚠️ **部分** | 首次出现 `passed=true`（S/t3），合并 1/9；单 dev 实例 |
| **L5 Independently Verified（T08）** | ❌ | 唯一的 `passed=true` 依赖产出方诚实，而非验证器抗伪造；且 1/5 |
| **L6 Generalization Tested（T08）** | ❌ **未测** | 六个"未见"运行已作废；harness 无法按 spec 实例化（§3.4） |
| **L4 Develop** | ❌ | 无 agent 自建新技能 |

### 不得宣称

- ❌ Level 4 Develop ／ T08 SINGLE-INSTANCE SUCCESS ／ T08 Independently Verified ／ Generalization Tested
- ❌ 「恢复策略提升了 T08 通过率」（本轮 R 0/5、S 1/5，p=1.0；上轮 4/5 亦在方差别内）
- ❌ 「T08 已解决」（dev 1/9；泛化未测）
- ❌ 「dev 的通过说明方法可行」（它说明一个位姿容许通过，仅此而已）
- ❌ 「unseen 0/6，泛化失败」（**该结论已撤回**——那六次跑的是 dev 世界）
- ❌ 「泛化已测」（**未测**；harness 缺 per-instance 位姿实例化能力）
- ❌ 「S/t3 证明系统可靠」（它是**一次性**成功，同臂另 4 次全失败）
- ❌ 「恢复臂比单发臂差」（p=1.0，两臂不可区分；报告方向反转不等于证明方向反转）
- ❌ 任何 T08 `passed=true`（本轮一个都没有；且验证器暂不可信）
- ❌ 「A′/B 配对对照已完成」（那是 oracle vs B，且配对脚本从未能运行）
- ❌ 「Development Skill 提升了开发效率」（采用率 0/4）
- ❌ 双臂／跨本体；LIBERO 结果不得并入 OpenMANIPULATOR-X

---

## 9. 本轮最重要的三条结论

1. **T08 仍未获得；泛化仍未测。** dev 9 个有效试次 **1 次** `passed=true`（S/t3，单发臂，独立复核为真实推动）。
   上一轮「恢复 4/5 > 基线 2/5」在本轮反转（R 0/5、S 1/5，p=1.0），说明两臂都被方差主导。
   主失效：**9 个有效 dev 试次中 4 次方向余弦为负**，物体被推**向反方向**。
   泛化：**未测**——六次"未见"运行跑的是 dev 世界，已作废；这是本轮最重要的发现之一。
2. **验收器还不能认证任何东西。** 它挡得住诚实的坏记录器，挡不住伪造的产出方；
   且记录器自身有一个会静默摧毁有效结果的缺陷。**修复前不得用 T08 `passed` 下任何结论。**
3. **harness 从未按 spec 实例化过任何任务。** `sim_profile.py` 硬编码物体初始位姿，不接受
   per-instance 参数，所以「未见任务」从未真正跑过；任何依赖不同初始位姿的实验（val 集、重生成 spec、
   早前 held-out 结果）都需先复核。**这一条比任何单次通过或失败都更重要**，因为它决定本项目能不能测泛化。
4. **基准有 16/72 的空转子句，A′ 标签是 oracle。** 既有数字没错，但「它们代表多少次真实操作」
   被系统性高估。这些都属于同一类：**标签声称的东西，没有任何机制去验证。**

---

## 10. 复现

| 项 | 位置 |
| --- | --- |
| 事实总表（六态） | `docs/FACT_STATE_20261112.md` |
| 评测器回归 | `setup/acceptance/evobot_lead_regression_v050_20261112/run_regression.sh` |
| A′ 误标 | `setup/acceptance/evobot_p0_aprime_mislabel_20261112/` |
| 基准空转 | `setup/acceptance/evobot_lead_benchmark_vacuity_20261112/scan_vacuity.py` |
| 记录器零长区间 | `setup/acceptance/evobot_lead_recorder_zero_interval_20261112/` |
| 夹爪门裁定 | `setup/acceptance/evobot_lead_gripper_gate_adjudication_20261112/` |
| 门审计 | `setup/acceptance/evobot_t08_gate_audit_20261112/` |
| T08 证据循环 | `setup/acceptance/evobot_t08_evidence_loop_20261112/` |
| T04 诊断 | `setup/acceptance/evobot_t04_executor_mismatch_20261112/` |
| Skill 回访 R2 | `development_skills/REVISIT_R2_20261112.md` |
| 统计审计 | `setup/acceptance/evobot_lead_statistical_audit_20261112/statistics.py` |