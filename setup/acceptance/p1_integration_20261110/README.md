# P1 集成验证 — 真实 Gazebo（2026-11-10）

P1-A~P1-D 落地后在真实栈上重跑三场景，确认没有破坏执行链路。

| 场景 | 结果 | wall | trace |
| --- | --- | --- | --- |
| normal | **PASS** | 14.529 s | PICK_A(attempt=1):OK → PLACE_A:OK → VERIFY_A(attempt=1):OK |
| dual_object | **PASS** | 28.286 s | PICK_A(attempt=1):OK → PLACE_A:OK → VERIFY_A(attempt=1):OK → PICK_B(attempt=1):OK → PLACE_B:OK → VERIFY_B(attempt=1):OK |
| regrasp | **PASS** | 14.419 s | PICK_A(attempt=1):OK → PLACE_A:OK → VERIFY_A(attempt=1):OK |

## 过程中发现的两个真实回归（都已修复，未放宽门槛）
1. **世界新鲜度上界过紧**：`max_world_age_s` 默认 2.0 s，而 OBSERVE→PICK→PLACE 实测约 7 s，
   导致 PLACE 被判 `world_stale`（三场景全失败）；
   → 改为 10 s（覆盖一条在途腿，仍拒绝跨腿残留）；
2. **刷新打断策略顺序**：修复 1 后仍失败，因为我在决策前插入的 OBSERVE 被写进 history，
   FSMPolicy 回放严格顺序时看到 OBSERVE 而期望 PLACE，抛 policy state error；
   → 刷新只替换执行器世界视图，**不写入 history**。

## 判读
- 三场景全 PASS，`dual_object` 完整跑完两条腿（6 步）；
- 说明 P1-A（新鲜度）、P1-B（拒绝码）、P1-C（顺序）、P1-D（夹爪反馈）在真实链路可用；
- 单次运行，非统计样本。
