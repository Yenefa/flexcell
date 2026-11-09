# W5-E2 预注册 — 真实 Gazebo 上的自改进闭环（冻结草案）

> W5-E1 已在合成层跑通"失败→改代码→目标+回归→验"。E2 把它搬到真实 Gazebo。
> 本文件在运行前提交；指标与判读不得事后修改。

## 1. 目标缺陷（受控注入）
在允许修改的源码中注入一个**明确的实现缺陷**，使目标场景失败，例如：
- `src/flexcell/flexcell_skills/flexcell_skills/config/week1.yaml` 中 `zone_2` 默认值不可达；
- 或技能实现中一个可恢复分支返回错误动作（需重建）。

**选择原则**：缺陷必须能由 agent 通过读证据定位，并且修复不触碰验收器/阈值/测试。

## 2. 允许与禁止
| 类别 | 路径 |
| --- | --- |
| 允许修改 | `src/flexcell/flexcell_skills/flexcell_skills/config/week1.yaml`（仅 zone_2 相关键）或技能实现文件 |
| protected | `gate/*`、既有场景模板、验收阈值、测试断言 |

## 3. 双门验收（冻结）
1. **目标门**：新场景在真实 Gazebo 上 PASS（独立架跑）；
2. **回归门**：既有场景（T-G1 normal）在同一修改后仍 PASS（独立架跑）；
3. 修改必须在允许路径（protected hash 不变）。

## 4. 运行设计
- 单臂（W5-E2）+ 最多 3 次迭代；每次迭代含一次重建（build=True）与一次真实运行；
- 预算：token ≤ 20k、wall ≤ 30 min；
- 失败/超预算保留记录；
- 先跑 1 次试点，再决定是否重复。

## 5. 指标
| 指标 | 定义 |
| --- | --- |
| 主指标 | 目标门 + 回归门同时 PASS（verified improvement） |
| 适应成本 | 迭代数、重建次数、wall |
| 失败 | 哪一门失败、error_code |
| 证据 | 两份 result.json（目标/回归）、episode、fingerprint |

## 6. 判读规则
- 两门都 PASS → 记 **verified improvement（n=1 试点）**；
- 目标 PASS 但回归失败 → 记 **regression loss**，改进被拒绝；
- 两门都失败 → 记失败；不修改验收器使其通过；
- 不宣称"系统已能自我进化"，只记录本次闭环结果。

## 7. 冻结声明
- 结果写入 `experiments/pilot-001/runs/p1.5-w5e2-20261109/`。

## 8. 结果附录（运行后追加，不改规则）
- 试点 n=1 **失败**：agent 4 轮未修改 config，目标门 `ROBOT_FAILURE`、回归门 PASS；
- 验收机制正常（两门独立判定、fingerprint 一致）；
- 记录：`experiments/pilot-001/runs/p1.5-w5e2-20261109/`；
- 期间修复 4 个 harness 缺陷（config-override 杠杆、W5A 工具集、WSL 路径转换、tempfile 导入）。
