# EXPERIMENT MATRIX — 24H sprint 2026-11-10

本文件登记本轮所有实验的运行条件与结果。**未运行的项标记 NOT_RUN，不得计为 PASS。**

## W5 — 自主修复能力阶梯

| 实验 | 模型 | 任务 | 缺陷类型 | 引导级别 | n | 成功 | 迭代 | Token | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W5-E2d | deepseek-flash | 可达性配置 | 配置值 | 明确 | 6（历史） | 6/6 | — | — | 历史归档 |
| **E2d-Flash 复现** | deepseek-flash | T-W5E2D | 配置值 | 明确 | 1 | **PASS** | 2 | 2,573 | `setup/acceptance/w5_e2_flash_20261110/e2d_result.json` |
| **E2e-Flash 复现** | deepseek-flash | T-W5E2E | 配置值 | 明确 | 1 | **PASS** | 5 | 6,952 | `setup/acceptance/w5_e2_flash_20261110/e2e_result.json` |
| W5-E2e | deepseek-flash | 对象注册 | 配置值 | 明确 | 3（历史） | 3/3 | — | — | 历史归档 |
| **W5-E3B #1** | deepseek-flash | T-W5S dual_object | **源码：阶段/目标选择** | 明确（点名文件） | 1 | **PASS** | 5 | 23,754 | `setup/acceptance/w5_levelb_20261110` |
| **W5-E3B #2** | deepseek-flash | T-W5S dual_object | 同上 | 明确 | 1 | **PASS** | 6 | 31,586 | `setup/acceptance/w5_levelb_n2_20261110` |
| **W5-E3C #1** | deepseek-flash | T-W5SC dual_object | 同上 | **无位置提示** | 1 | **FAIL** | 8 | 40,307 | `setup/acceptance/w5_levelc_20261110` |
| **W5-E3C #2** | deepseek-flash | T-W5SC dual_object | 同上 | 无位置提示 | 1 | **FAIL** | 8 | 43,135 | `setup/acceptance/w5_levelc_n2_20261110` |
| W5-E3C′（作废 3 次） | deepseek-flash | T-W5SC2 dual_object | 同上 | 无位置提示 + "先运行" | 3 | **INVALID（判分 HARNESS_ERROR）** | 9 / 11 / — | 40,310 / 40,007 / — | `setup/acceptance/w5_levelcprime_invalid_20261110` |
| **W5-E3C′（有效）** | deepseek-flash | T-W5SC2 dual_object | 同上 | 无位置提示 + "先运行" | 1 | **FAIL**（**预算耗尽截断**） | 10 | 51,395（+28%） | `setup/acceptance/w5_levelcprime_20261110` |
| **C14（工具清单）** | deepseek-flash | T-W5SC2 dual_object | 同上 | 无提示 + 工具清单可见 | 1 | **FAIL**（H0，**预算耗尽截断**） | 9 | 53,045（+33%） | `setup/acceptance/c14_tool_inventory_20261110` |
| C15 run A | deepseek-flash | T-W5SC2 dual_object | 同上 | 无提示 + **证据自带定位**（被截断） | 1 | **PASS** | 5 | 25,380 | 原始产物丢失（WSL 重启），**不作证据** |
| **C15 run B** | deepseek-flash | T-W5SC2 dual_object | 同上 | 无提示 + **证据自带定位** | 1 | **PASS** | **4** | **16,937** | `setup/acceptance/w5_levelc_evidence_20261110/run_b_regions_visible` |
| **C15 run C1（重复）** | deepseek-flash | T-W5SC2 dual_object | 同上 | 同上 | 1 | **PASS** | **5** | **22,077** | `setup/acceptance/w5_levelc_evidence_20261110/run_c1` |
| **C15 run C2（重复）** | deepseek-flash | T-W5SC2 dual_object | 同上 | 同上 | 1 | **PASS** | **5** | **23,258** | `setup/acceptance/w5_levelc_evidence_20261110/run_c2` |

**Level B 与 Level C 不得合并统计。**

## Level B 明细（两次）

| 项 | #1 | #2 |
| --- | --- | --- |
| 首先调用 `run_execution` 并获得真实失败 | 是 | 是 |
| 编辑发生在观测失败**之后** | 是（`verify.py` 断言） | 是 |
| 目标 `dual_object` | PASS | PASS |
| 回归 `normal` | PASS | PASS |
| 回归 `regrasp` | PASS | PASS |
| `claim_success` | false | false |
| `false_success` | false | false |
| 验收器 `gate/acceptance.py` | 未修改 | 未修改 |
| 编辑内容 | `zones[zone_of[self._obj_a]]` → `zones[zone_of[decision.target]]` | 同 |

**Level B: 2/2**（探索性，n<10，**不构成统计证据**）。

## Level C 明细

| 项 | #1 | #2 |
| --- | --- | --- |
| 是否运行场景 | **否** | **否** |
| 是否编辑源码 | **否** | **否** |
| 迭代 | 8 | 8 |
| 前几轮消耗于 | `list_dir`×12、`task.md`、`week1.yaml` | 同 + `run_checks`、`test/`、`launch/` |
| 结果 | ROBOT_FAILURE（未被修复） | 同 |
| `claim_success` | false | false |

**失败机制**：Level B 的任务文本点名了文件，省下约 4 轮定位；Level C 去掉后，
agent 在**定向成本**上耗尽预算，尚未进入 `run_execution`。
归因：**任务设计（预算/探索成本）为主，不能归因于模型诊断能力**——它没有做出错误诊断，
而是**没有机会做出诊断**。标记 **UNKNOWN**（n=1）。

## Track A（执行安全 / 整改）

| 项 | 结果 | 证据 |
| --- | --- | --- |
| 取消 + 隔离（P0-A/B） | 离线 15 项 PASS；真实栈取消契约成立 | `test_skill_cancellation.py`, `p0a_cancel_20261110` |
| 世界新鲜度（P1-A） | 6 项 PASS | `test_world_freshness.py` |
| 拒绝码分类（P1-B） | 5 项 PASS | `test_rejection_typing.py` |
| 动作顺序（P1-C） | 11 项 PASS | `test_action_order.py` |
| 夹爪反馈（P1-D） | 9 项 PASS | `test_gripper_feedback.py` |
| 对象注册表（P1-E） | 7 项 PASS | `test_object_registry_scope.py` |
| 日志完整性（P1-F） | 8 项 PASS | `test_log_integrity.py`, `test_finish_idempotent.py` |
| 预算生命周期（P2-A） | 10 项 PASS | `test_budget_lifecycle.py` |
| 决策记录（P2-B） | 7 项 PASS | `test_decision_record.py` |
| 几何工具（P2-C） | 14 项 PASS | `test_pose_geometry.py` |
| 时间域（P2-D） | 5 项 PASS | `test_time_domain.py` |
| 感知边界（P2-E） | 9 项 PASS | `test_perception_boundary.py` |
| 真实栈三场景 | 3/3 PASS（多次复跑） | `p1_integration_20261110` |
| **隔离态真实触发** | **ENGAGED_AND_CLEARED** | `p0a_quarantine_20261110` |

## Track B（Hybrid Runtime）

**NOT_RUN** —— 本轮资源全部投入 W5 与整改，未做新的 Hybrid 实验。
历史结论不变：Hybrid 可运行，但**无证据**优于 FSM。

## Track C（FSM / MTC）

**C13 已预注册并尝试，结果 BLOCKED** —— 受约束世界无法在不动冻结 `world_sha256` 的前提下构造
（`sim_profile.py` 无 obstacle 入口；加 `--world` 覆盖会削弱验收门）。**机制问题仍未回答。**
**仍未回答**。预注册与待应用的 world patch 见 `docs/C13_PREREGISTRATION.md`、
`setup/acceptance/c13_constrained_20261110/`。本轮**未新增普通样本**，拒绝用数量代替机制检验。

## 工具链缺陷（影响所有实验的解释）

| # | 缺陷 | 影响 | 状态 |
| --- | --- | --- | --- |
| T1 | `search_code` 对文件路径用 `rglob` | 恒 `(no matches)`，agent 无法定位 | 已修 |
| T2 | `export/_wsl` 对 POSIX 路径 `split(":")[1]` | 每次 `run_execution` 抛 `IndexError`，**从未拿到失败证据** | 已修 |
| T3 | 无条件调用 `wsl` 可执行文件 | WSL 内 `FileNotFoundError` | 已修 |
| T4 | 进度提示未显示已执行次数 | agent 反复阅读不运行 | 已修 |
| T5 | `T-W5S` `max_iterations=10`，文件 1436 行 | 预算不足 | 已提到 24 |
| T6 | 工具**参数**未记录 | 失败不可诊断 | 已记录 |

**结论**：E2c 的"只读不写"至少在本轮可归因于**工具层缺陷**，而非模型倾向。
但这不等于模型一定能做好——Level C 显示**定向成本**仍是瓶颈。

## Level C′（无位置提示 + 先运行场景）

### 有效运行（判分工具链修复后）
| 项 | 值 |
| --- | --- |
| 迭代 / Token | 10 / 51,395 |
| `run_execution` 次数 | **9** |
| 看到真实失败 | **是**（`ROBOT_FAILURE`） |
| 源码编辑 | **0** |
| `target` / `regression_normal` | **ROBOT_FAILURE** / PASS |

**判读**：不是没看到证据（9 次），也不是探索不足（第 1 轮就运行），而是**卡在"证据 → 定位"**。
对比 Level B（点名文件）2/2、5–6 轮：差别在**定位成本**，不在模型能力。

### 作废的 3 次（判分无效，不计入统计）
两次 WSL 内 `HARNESS_ERROR`（仿真栈未启动），一次 Windows Python 无法启动 `wsl`（WinError 5）。
**修复**：在判分前清理中补上 gz ruby 启动器、`ros2 daemon stop`、`/dev/shm/fastrtps_*`，
随后判分恢复正常。该修复已写入 `pilot/gazebo.py`。

## C14 — 工具清单可见性（H0 成立，负结果）

| 工具 | 调用次数 |
| --- | --- |
| `search_code` | **0** |
| `list_dir` | **28** |
| `read_file` | 11 |
| `run_execution` | 8 |
| `edit_file` | **0** |

即使系统提示明写 `search_code` 的用途，agent 仍一次未用；默认策略是**目录遍历 + 分段读**，
在 1436 行文件上耗尽 40k 预算（**+33%**）仍未到达编辑。**工具清单不足以改变工具选择。**
与 Level B（点名文件 → 2/2、5–6 轮）对比：**提示实际上替代了搜索**。

### 三个负结果的机制区分（已按 `budget_exceeded` 更正）

| 实验 | 看到证据 | 编辑 | **终止原因** | 失败机制 |
| --- | --- | --- | --- | --- |
| Level C | 否 | 否 | 预算耗尽 | 探索成本 |
| Level C′ | **是（9 次）** | 否 | **预算耗尽（+28%）** | 定位成本吃光预算 |
| C14 | **是（8 次）** | 否 | **预算耗尽（+33%）** | 工具选择：不用搜索，只遍历 |
| **C15（对照）** | 是（4–5 次） | **是** | 正常结束（用 42–55%） | 定位信息把成本降到 1/3–1/2 |
| **P3（无定位 + 150k）** | 是（10 次） | **是** | 正常结束（用 32%） | **给足预算无定位也能修好，但要 34 次遍历** |

> **更正（两次）**：
> ① 三次失败均被 40k 预算**强制截断**（`runner.py:107`），"看到证据但不编辑"只是解释；
> ② **P3 实验已证明**：给到 150k 预算，无定位也能 **PASS**（10 轮 / 48k / 34 次遍历）。
> 所以 Level C′/C14 的失败 = **预算截断**，不是能力边界。
> 定位信息改变的是**成本**（10→4–5 轮，48k→17–23k，遍历 34→0），不是**可行性**。
> 详见 `docs/experiments/CORRECTION_20261110C.md`。

## C15 — 失败证据自带定位（**Level C 首次达成**）

| | run B（regions 可见） |
| --- | --- |
| `suspect_regions` 送达 | **是** |
| `list_dir` | **0**（C14 为 28） |
| 迭代 / Token | **4 / 16,937**、**5 / 22,077**、**5 / 23,258**（**n=3**） |
| `dual_object` / `normal` / `regrasp` | **PASS / PASS / PASS**（三次） |
| `list_dir` | **0 / 0 / 0** |
| `edit_file` | 1 / 1（均正确） |
| 编辑 | `zones[zone_of[self._obj_a]]` → `zones[zone_of[decision.target]]`（正确） |

**这是本项目第一次在"无文件名、无行号、无修复方向"的条件下完成真实源码修复并通过三门——且已重复 3 次（3/3）。**
与 Level B 的区别：Level B 用**提示**替代搜索；C15 用**证据**替代搜索。

### 方法演进（同一任务、同一缺陷、同一预算）
| 条件 | 结果 | 关键行为 |
| --- | --- | --- |
| Level C′ | FAIL | 运行 9 次，0 编辑 |
| C14 工具清单 | FAIL | 运行 8 次，`list_dir` 28 次，0 编辑 |
| **C15 证据定位** | **PASS** | 运行 4 次，**`list_dir` 0 次**，1 次正确编辑 |
