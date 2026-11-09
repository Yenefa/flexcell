# C6 预注册 — 扩大 n（normal 场景，n=9/臂）

> C3 的 normal 对照为 n=3，MTC +22.9% wall。C6 检验该方向在更大样本下是否稳定。
> 本文件在运行前提交。

## 1. 两臂与运行
- 命令同 C3：`--case normal --backend velocity_servo --decision-policy fsm`，`--skill-backend legacy|mtc`；
- 在 C3 的 3+3 基础上各补 6 次，合计 **9/臂**；
- 交替顺序：L,M,M,L,M,L,M,L,L,M,L,M（L=legacy/FSM，M=MTC）；
- 单次超时 600 s；失败保留。

## 2. 指标（预注册）
| 指标 | 定义 |
| --- | --- |
| 主指标 | 成功率（PASS/总数） |
| 次指标 | wall 均值/中位数、失败分类 |
| 证据 | result/episode、fingerprint、`initial_world_state` |

## 3. 判读规则（冻结）
- 成功率差异 → 报告方向，用 Fisher 精确检验给出 p 值，但**不宣称因果**；
- wall 差异 → 报告均值/中位数与区间，n=9 仍为探索性；
- 与 C3 结论冲突时，如实报告冲突，不选择性引用；
- 不修改验收器/阈值/世界。

## 4. 边界
- 仿真（M3-S）；
- 同一台机器、同一配置；
- 结果写入 `setup/acceptance/c6_normal_n9_20261109/`。

## 5. 结果附录（运行后追加，不改规则）
- 9/9 vs 9/9 PASS；
- FSM 平均 14.665 s（中位 14.173），MTC 平均 17.145 s（中位 16.235）；
- 平均差 +2.481 s（+16.9%），中位差 +2.062 s；
- 与 C3（+22.9%，n=3）方向一致、幅度略降；
- 记录：`setup/acceptance/c6_normal_n9_20261109/`。
