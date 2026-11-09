# EXPERIMENT MATRIX — 24H sprint 2026-11-10

本文件登记本轮所有实验的运行条件与结果。**未运行的项标记 NOT_RUN，不得计为 PASS。**

## W5 — 自主修复能力阶梯

| 实验 | 模型 | 任务 | 缺陷类型 | 引导级别 | n | 成功 | 迭代 | Token | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W5-E2d | deepseek-flash | 可达性配置 | 配置值 | 明确 | 6（历史） | 6/6 | — | — | 历史归档 |
| W5-E2e | deepseek-flash | 对象注册 | 配置值 | 明确 | 3（历史） | 3/3 | — | — | 历史归档 |
| **W5-E3B #1** | deepseek-flash | T-W5S dual_object | **源码：阶段/目标选择** | 明确（点名文件） | 1 | **PASS** | 5 | 23,754 | `setup/acceptance/w5_levelb_20261110` |
| **W5-E3B #2** | deepseek-flash | T-W5S dual_object | 同上 | 明确 | 1 | **PASS** | 6 | 31,586 | `setup/acceptance/w5_levelb_n2_20261110` |
| **W5-E3C #1** | deepseek-flash | T-W5SC dual_object | 同上 | **无位置提示** | 1 | **FAIL** | 8 | 40,307 | `setup/acceptance/w5_levelc_20261110` |
| **W5-E3C #2** | deepseek-flash | T-W5SC dual_object | 同上 | 无位置提示 | 1 | **FAIL** | 8 | 43,135 | `setup/acceptance/w5_levelc_n2_20261110` |

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

## Track B（Hybrid Runtime）

**NOT_RUN** —— 本轮资源全部投入 W5 与整改，未做新的 Hybrid 实验。
历史结论不变：Hybrid 可运行，但**无证据**优于 FSM。

## Track C（FSM / MTC）

**NOT_RUN（本轮）** —— C11 之后的机制问题（MTC 是否在复杂约束/多候选规划中展示 FSM 缺失的能力）
**仍未回答**。本轮未新增样本，避免用普通场景数量代替机制检验。

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
