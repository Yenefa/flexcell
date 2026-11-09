# REMEDIATION MASTER PLAN — FLEXCELL-REMEDIATION-2026-01

> Baseline: `ebe27f0` · Branch: `autonomous/flexcell-remediation` · 自主执行中

## Backlog（14 项）
| ID | 任务 | 状态 | 证据 |
| --- | --- | --- | --- |
| P0-A | FSM 超时停止确认 + QUARANTINE | **DONE** | `skill_lifecycle.py`、`test_skill_cancellation.py` 15 passed |
| P0-B | 取消机制自动化回归 | **DONE** | 15 项新测试 + 全仓 1154 passed |
| P0-C | 真机安全前置评估 | **BLOCKED**（缺硬件） | `P0C_PHYSICAL_SAFETY_READINESS.md` |
| P1-A | WorldState 新鲜度 | **DONE** | `test_world_freshness.py` 6 passed |
| P1-B | Safety Gate 错误码分类 | **DONE** | `test_rejection_typing.py` 5 passed |
| P1-C | FSM 动作顺序约束 | **DONE** | `test_action_order.py` 11 passed |
| P1-D | Gripper 反馈验证 | **DONE** | `test_gripper_feedback.py` 9 passed |
| P1-E | known_objects 状态解耦 | TODO | — |
| P1-F | Episode 与日志完整性 | TODO | — |
| P2-A | Inference Budget 完善 | TODO | — |
| P2-B | Task FSM 模块化 | TODO | — |
| P2-C | MoveToPose 模块化 | TODO | — |
| P2-D | 时间域规范 | TODO | — |
| P2-E | Sim2Real 感知准备 | TODO | — |

## P0-A 详情
- 新增 `flexcell_skills/skill_lifecycle.py`：`confirm_stop()`（等待 cancel 响应 + 终止结果）与 `MotionQuarantine`（粘性隔离闸门）；
- `task_fsm_server._demo_call` / `_call_skill` 改为：超时/取消 → 请求停止 → **等待终止证据** → 确认或隔离；
- 隔离时：**不释放租约、不发布 IDLE、拒绝新运动派发**；
- `reset_motion_quarantine`（`std_srvs/Trigger`）仅在隔离目标已终止时才能清除；
- 复用 MoveToPose 已有的五重停止证明（不重写底层取消）。

## 提交记录
| Commit | 内容 |
| --- | --- |
| `fefd628` | P0-A/P0-B 停止确认 + 隔离 |
| `1dd4543` | P1-A 世界新鲜度 + P0-C 安全评估 |
| `64136eb` | P1-B 拒绝码分类 |
| `ec2ee41` | P1-C 动作顺序约束 |
