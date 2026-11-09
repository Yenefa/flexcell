# W5-E2c 预注册 — 多场景回归门（冻结草案）

> W5-E2b 的回归门只覆盖 normal 一个场景。E2c 把回归门扩展到 **normal + regrasp**，
> 检验"改进不破坏既有能力"是否仍成立。

## 1. 与 E2b 的差异
| 项 | E2b | E2c |
| --- | --- | --- |
| 目标门 | dual_object | dual_object（不变） |
| 回归门 | normal | **normal + regrasp** |
| 迭代预算 | 6 | 6 |
| 缺陷 | `zone_2_x=0.45`（最小覆盖） | 同 |

## 2. 验收（冻结）
三份真实 Gazebo 运行全部 PASS 才算 verified improvement：
1. 目标：dual_object；
2. 回归 A：normal；
3. 回归 B：regrasp；
另有 `gate/` protected。

## 3. 判读
- 三门全 PASS → verified improvement（n=1 试点）；
- 任一回归失败 → **regression loss**，改进被拒绝；
- 不修改任何验收器/阈值/世界；
- 记录：`experiments/pilot-001/runs/p1.5-w5e2c-20261109/`。

## 4. 结果附录（运行后追加，不改规则）
- 2 次试点均 **失败**：6 轮、约 7.5k tokens、**未写文件**；目标门 ROBOT_FAILURE；
- normal/regrasp 回归门 PASS（未修复配置下这两个场景本就不受 zone_2 影响）；
- 记录：`runs/p1.5-w5e2c-20261109/`；
- 结论：多场景回归门**未验证**；按资源规则停止调参。
