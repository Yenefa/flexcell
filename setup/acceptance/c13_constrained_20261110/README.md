# C13 — MTC 能力机制检验：**BLOCKED（场景无法在冻结世界生成器外构造）**

预注册见 `docs/C13_PREREGISTRATION.md`（运行前已写定判据，未因结果改动）。

## 尝试记录（三次）

| # | 尝试 | 结果 |
| --- | --- | --- |
| 1 | 给 `sim_smoke.py` 传 `--world <patched.sdf>` | `rc=2`，该参数**不存在** |
| 2 | 同上，两次运行 | 两次均 `NO_RESULT`（argparse 拒绝，未跑仿真） |
| 3 | 追查世界生成路径 | `scripts/sim_profile.py:151-230` 从 `worlds/flexcell_velocity_servo.sdf` 生成 `world.sdf`，**无 obstacle/ceiling 入口**；`sim_smoke` 会计算并记录 `world_sha256`，冻结验收与 qualification 测试**依赖该哈希** |

## 阻塞原因（具体）
要在场景中加入静态顶板，只能：
1. 修改 `sim_profile.py` / `worlds/*.sdf` → **改变 `world_sha256`**，会破坏冻结的世界声明与
   `test_qualification_*` / `test_s2_local` 的哈希断言（本轮整改中已因改 yaml 踩过一次）；
2. 在 `sim_smoke` 增加 `--world` 覆盖 → 会使"世界未被声明"成为可能，**削弱验收门的可信度**，
   与本项目"不得为通过而放宽验收"的原则冲突。

结论：**在当前冻结约束下，无法在不破坏证据链的前提下构造新的受约束场景。**
按三次规则停止，标记 **BLOCKED**，**不产出任何 MTC 优越性结论**。

## 下一窗口的正确做法
1. 以**新的 scenario id**（如 `dual_object_constrained`）正式注册一个受约束世界，
   同步更新 `worlds/` 与 `sim_profile.py`，并**重新计算并声明**新的 `world_sha256`；
2. 先在离线/单测层证明该世界能**区分**两种后端（legacy 必失败），再跑真实对照；
3. 只有在"legacy 必失败"被独立确认后，MTC 的 PASS 才算**能力证据**；否则仍是成功率对比。

## 本轮 Track C 的诚实状态
- **NOT_RUN（机制问题）**：MTC 是否在复杂约束/多候选规划中展示 FSM 缺失的能力——**仍未回答**；
- 未新增普通抓放样本（拒绝用数量代替机制检验）；
- C11 的结论不变：MTC 12/12、strict 5/5 vs baseline 6/9，属**成功率**证据，非能力证据。
