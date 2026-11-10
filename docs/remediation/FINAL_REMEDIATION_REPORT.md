# FINAL REMEDIATION REPORT — FLEXCELL-REMEDIATION-2026-01

**Branch:** `autonomous/flexcell-remediation`  
**Baseline:** `ebe27f07881200ab0fc74dfaa5490208023bf9d9`  
**Status:** 14 项中 **13 DONE / 1 BLOCKED（缺硬件）**  
**Push / PR:** **未执行，需人工批准**

---

## 1. 执行摘要

本轮完成 13 项整改，全部有"缺陷复现 → 代码修改 → 自动化测试 → 全仓回归"四段证据；
其中 4 项额外通过**真实 Gazebo 集成验证**。P0-C（真机安全）因**无硬件**标记 BLOCKED，
交付评估报告，**未编造任何通过结论**。

**最重要的发现不是修了什么，而是单测全部通过时仍存在的三个真实缺陷**——它们只有跑
真实栈才暴露（见 §5）。

---

## 2. 逐项结果

| ID | 缺陷 | 修改 | 测试证据 | 提交 |
| --- | --- | --- | --- | --- |
| P0-A | 超时后发 cancel 即返回，未确认停止 | `skill_lifecycle.py` 新增；FSM 增加 QUARANTINED 与人工复位 | `test_skill_cancellation.py` 15 | `fefd628` |
| P0-B | 取消路径无真实派发路径测试 | 覆盖 `_demo_call()` 8 种情形 | 同上 15 | `fefd628` |
| P0-C | 真机安全无评估 | `P0C_PHYSICAL_SAFETY_READINESS.md` | 文档（全部 NOT_VERIFIED） | `1dd4543` |
| P1-A | `max_world_age_s=0.0` 使检查失效；`pose_age_s` 冻结 | 快照年龄按 monotonic 增长；FSM 传入接收时刻 | `test_world_freshness.py` 6 | `1dd4543` |
| P1-B | 所有拒绝都返回 53，无法区分原因 | 接入 `rejection_canonical_code()` | `test_rejection_typing.py` 5 | `64136eb` |
| P1-C | 安全门不检查动作顺序 | `_order_ok()`：PLACE/VERIFY/PICK 前置 | `test_action_order.py` 11 | `ec2ee41` |
| P1-D | GripperCommand 结果被丢弃 | `gripper_outcome()` 分类 | `test_gripper_feedback.py` 9 | `da06b2a` |
| P1-E | 模块级全局对象集合互相污染 | `known_objects.Registry`（node-scoped） | `test_object_registry_scope.py` 7 | `81a4c47` |
| P1-F | `finish()` 非幂等；拒绝路径丢 `recovery_audit`；UTF-8 | 幂等守卫、审计前置、编码与原子写 | `test_log_integrity.py` 6 + `test_finish_idempotent.py` 2 | `25c3216` |
| P2-A | 无 `void()/release()`；`settle()` 抛异常 | 释放可证明未发出的预留 | `test_budget_lifecycle.py` 10 | `1ba8db8` |
| P2-B | 决策日志两处重复且已漂移 | `contracts/decision_record.py` | `test_decision_record.py` 7 | `768e54b` |
| P2-C | MoveToPose 内联几何工具 | `pose_geometry.py`（纯函数，兼容再导出） | `test_pose_geometry.py` 14 | 见 §7 |
| P2-D | `_js_wall` 用 `0.0` 哨兵对比 monotonic | `_js_monotonic` + `None` 哨兵 | `test_time_domain.py` 5 + 规范文档 | `5f1eec9` |
| P2-E | 感知边界未厘清 | 边界测试 + 真机接入计划 | `test_perception_boundary.py` 9 | `4e3577e` |

---

## 3. 修复前后行为对比（关键项）

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| Skill 超时 | 发 cancel 后立即返回，租约释放、发 IDLE、允许下一任务 | 等待终端结果；未确认 → QUARANTINED，禁派发、禁释放、禁 IDLE |
| 过期世界 | `max_world_age_s=0.0`，检查恒不触发 | 超龄 → `STALE_WORLD`；决策前按需刷新世界 |
| 拒绝原因 | 一律 `ERR_SAFETY_REJECTED(53)` | 日志含 `rejection_kind` + canonical 码（Action 码保持兼容） |
| 乱序动作 | PLACE 未 PICK 也可派发 | 派发前拒绝 `place_without_pick` |
| 夹爪结果 | 只查传输错误 | `NO_CONTACT` 判抓取失败；`UNMEASURED` 不误判 |
| `finish()` 二次调用 | 可覆盖 SUCCESS 并重复写 | 幂等，返回首次结果 |
| 关节状态新鲜度 | 从未收到 → 看起来新鲜 | 从未收到 → 年龄未知，判为不可用 |

---

## 4. 测试证据汇总

- 新增测试文件 **12 个，共 105 项**；
- 全仓 skill 套件：**0 failed**（`test_parity_report.py` 4 项为环境预存失败，已用 stash 验证与本次无关）；
- 真实 Gazebo 集成：`setup/acceptance/p1_integration_20261110/` → **normal / dual_object / regrasp 三次三 PASS**；
- 取消路径集成：`setup/acceptance/p0a_cancel_20261110/` → `P0A_CANCEL_CONTRACT_HELD`。

---

## 5. 只有真实栈才暴露的三个缺陷（本轮最重要的教训）

1. **新鲜度上界 2 s 与 7 s 的腿时长冲突**：单测用合成年龄，全部通过；真实栈三场景**全失败**（`world_stale`）。
   修法不是放宽门槛，而是**决策前按需刷新世界**。
2. **刷新写入 history 打断策略顺序**：修复 1 后仍失败，`FSMPolicy` 回放严格顺序时看到 OBSERVE 而期望 PLACE，抛 state error。
   修法：刷新只替换执行器世界视图，**不写入 history**。
3. **取消探针自身两个 bug**：等待 result 时未 spin rclpy（3 次误报"挂死"）、未等 BUSY 就 cancel。
   已在 README 明确记录，**避免把工具问题误记为产品缺陷**。

---

## 5b. 隔离态已在真实图中验证（本轮补齐）

通过把 `stop_cancel_timeout_s` 设为 `0.0`（代码中已文档化的"取消请求超时"分支，**未改 skill 代码**）
在真实 ROS 图中触发隔离：`saw_quarantined=true`、第二个任务被拒（`error_code=50`，
"motion quarantine active ... until a verified reset"）、`reset_motion_quarantine` 成功清空。
证据：`setup/acceptance/p0a_quarantine_20261110/`（`verify.py` → `P0A_QUARANTINE_ENGAGED_AND_CLEARED`）。

附带发现：`stop_result_timeout_s=0.2` 没有触发隔离——真实 skill 的停止确认约 50 ms 完成，
说明隔离是**最后手段**而非日常路径。

## 6. 剩余风险清单

| 风险 | 严重度 | 说明 |
| --- | --- | --- |

| PLACE 超时、控制器拒绝取消未测 | 中 | NOT_RUN |
| 真机安全链完全未验证 | **高** | 无急停/STO/安全 PLC；**禁止上真机** |
| PLACE 超时路径未单独验证 | 低 | 隔离已由 cancel-timeout 路径验证 |
| 相机闭环未接入 | 中 | 无硬件；仅完成边界与计划 |
| `max_effort` 固定 10.0 | 低 | 未按物体标定 |
| 模块化仅完成 2 个切片 | 低 | `TaskWorld` / `SkillDispatcher` 仍 DEFERRED（受 FSM-P0-1 约束） |
| Action 错误码未纳入 canonical 类型 | 低 | 契约冻结，需人工批准才能改 |

---

## 7. 延期事项（有明确未来验收条件）

| 项 | 理由 | 未来验收条件 |
| --- | --- | --- |
| P0-C 真机安全 | **无硬件** | 按 `P0C_PHYSICAL_SAFETY_READINESS.md` §3 五项前置逐条执行 |
| P2-B 剩余切片 | FSM-P0-1 禁止大规模模块化 | 每次一职责一提交，回归全绿 |
| P2-C 剩余切片 | 不得重写已验证取消机制 | 先补离线测试再迁移 |
| 相机闭环 | 无相机硬件 | 按 `P2E_SIM2REAL_PERCEPTION_PLAN.md` §3 七条前置 |

---

## 8. 最终成熟度评估

| 维度 | 等级 | 依据 |
| --- | --- | --- |
| 仿真受控任务执行 | **M3（受控）** | 三场景真实 Gazebo 反复 PASS |
| 执行安全（软件层） | **M2+** | 停止确认 + 隔离 + 新鲜度 + 顺序 + 类型化拒绝，全部有测试 |
| 可观测性/审计 | **M3** | episode/log 幂等、UTF-8、原子写、类型化拒绝 |
| 真机就绪 | **M0** | 硬件安全链完全未验证，**明确不可上真机** |
| 自主源码修复（W5 Level B） | **未达成** | 见 §9 |

---

## 9. 未达成的总目标（诚实结论）

24H 冲刺的最终成功标准是"**Agent 自主诊断并修复一个此前没有答案的源码级故障**"（W5 Level B）。

**本轮未达成。** 已完成的是：
- 冻结基线与预注册协议（`W5E3C_PREREGISTRATION.md`）；
- 修复了三个导致 agent"只读不写"的**工具层根因**（工具描述就是工具名、4000 字符截断 vs 53 KB 单行、缺少搜索工具）；
- 但修复后**未取得一次真实成功**。

归因：**UNKNOWN（倾向于工具/提示层面，非模型能力）**——因为根因修复后尚未重跑，没有证据支持任何更强结论。

---

## 10. 结论

本轮把"技能超时后盲目继续"这一类**最危险的执行缺陷**在软件层封住了，并且**用真实栈证明了它成立**。
但没有达成"自主源码修复"这一研究目标，也没有任何真机证据。

**下一步最有信息价值的实验**：用修好工具链的 Flash agent 重跑 Level B 三次，
统计"是否发生第一次写操作 / 定位是否正确 / 修复后目标场景是否 PASS"。

**所有提交均为本地提交，未经推送或 PR，需人工批准。**