# P0-A 取消路径集成验证 — 真实 Gazebo（2026-11-10）

在真实栈上对执行中的 PICK 发起 cancel，检查停止确认与后续准入。

## 观测结果
| 项 | 值 |
| --- | --- |
| goal 结果 | `OUTCOME_CANCELED(2)` / `ERR_CANCELED(32)` |
| detail | `canceled during PICK_A(attempt=1)` |
| 任务状态序列 | BUSY → IDLE → BUSY → IDLE |
| 第二个任务 | **被拒绝**，`error_code=53`，`already_carried`（`canonical_error_code=35`） |
| 隔离状态 | 未触发（`no active quarantine`） |

## 已验证的不变量
1. **cancel 后 goal 正常终止**，携带类型化取消码，无未受管理的后台 Goal；
2. **cancel 后下一任务被拒绝**——PICK 在抓取中被取消，夹持仍处于 engaged，
   安全门以 `already_carried` 拒绝新任务，机器人不会在状态未知时继续接受运动指令；
3. 拒绝是**类型化**的（canonical 35），不是静默失败。

## 未验证（明确标记 NOT_VERIFIED）
- **隔离状态未在仿真中触发**：本次 cancel 被 skill 正常确认（skill 自行终止），
  因此不需要隔离。要在仿真里制造"停止未确认"必须人为让下游 Goal 不终止，
  这属于故障注入，不在本轮安全验证范围内。
  → 隔离逻辑由 `test_skill_cancellation.py` 的 15 项离线测试覆盖（真实 `_demo_call` 路径）。
- PLACE 期间超时、控制器拒绝取消：NOT_RUN。

## 探针自身的两个 bug（已修复，如实记录）
1. 等待 result 时**没有 spin**，rclpy 回调不执行 → 健康的停止被误判为挂死（3 次误报）；
2. 首次版本未等 BUSY 就 cancel，cancel 落在任务启动前。
两处都是验证工具的问题，不是被测系统的问题——修复后才得到上面的结果。
