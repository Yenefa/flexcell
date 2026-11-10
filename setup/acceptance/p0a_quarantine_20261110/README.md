# P0-A 隔离态真实触发（2026-11-10）

此前 `P0-A 取消契约` 验证的是**正常取消**路径，隔离态从未在真实图中触发（DoD 缺口）。本轮补上。

## 方法（未修改任何 skill 代码）
把 FSM 的 `stop_cancel_timeout_s` 设为 **0.0** —— 这是代码中**已文档化**的"取消请求本身超时"分支，
不是新功能，也不是放宽验收。

## 观测结果
| 项 | 值 |
| --- | --- |
| goal 结果 | `OUTCOME_CANCELED(2)` / `ERR_CANCELED(32)` |
| detail | `stop unconfirmed (goal terminated but the cancel was not accepted)` |
| `saw_quarantined` | **true** |
| 第二个任务 | **拒绝**，`error_code=50`，`motion quarantine active ... until a verified reset` |
| 人工复位 | **success**，`quarantine cleared by reset_motion_quarantine` |

## 关闭的 DoD 项
1. 未确认停止 → **进入隔离**（真实图，非单测）；
2. 隔离下**禁止派发新运动**（码 50 + 专属文案）；
3. **经验证的复位可用**。

## 附带发现
`stop_result_timeout_s=0.2` **没有**触发隔离：真实 skill 的停止确认约 50 ms 完成。
说明隔离是**最后手段**，健康仿真中停止几乎总被确认。

## 复现
```bash
bash ci-public-window/scripts/p0a_quarantine_run2.sh
python3 setup/acceptance/p0a_quarantine_20261110/verify.py
```
