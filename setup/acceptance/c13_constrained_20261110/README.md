# C13 — 受约束世界下的 FSM/MTC 机制对照（**首次获得证据；两边都未完成**）

> 取代此前 BLOCKED 状态。解除阻塞的方法：**新增一个 scene id**，纯增量，
> 不触碰任何既有世界；已实测默认世界哈希**未变**。

## 1. 预注册的命题

**H1**：在需要绕障规划的场景中，MTC 能完成而 legacy（FSM 派发）不能。
**H0**：两者表现相同 → 记负结果。**H2**：MTC 也失败但方式不同 → 过去记为"不可判"。

## 2. 场景怎么建的（关键：不破坏冻结物）

`scripts/sim_profile.py` 新增 `constrained_approach` scene，在 `target_box_a`
（0.22, 0, 0.0175）上方 **z=0.155** 加一块 **0.30×0.30×0.010** 静态顶板。

**为什么这不违反"不得改动冻结世界"**：
1. 既有 `three_boxes` / `tagged_three_boxes` 生成路径**一行未动**；
2. 实测默认世界 `world.sdf` 的 sha256 = `f78a469d…bb187`，**改动前后一致**；
3. 没有测试断言 `SCENES` 的完整元组，只有按名引用；
4. 新场景有自己的哈希 `2ebf1148…c9aa90`，是两个实验臂**共同**的世界。

## 3. 结果（同一 world，仅 `skill_backend` 不同）

| 臂 | 状态 | 错误码 | 通过的阶段 |
| --- | --- | --- | --- |
| **legacy** | ROBOT_FAILURE | `ERR_SKILL_FAILED` | `PICK_A:OK` |
| **MTC** | ROBOT_FAILURE | `ERR_RECOVERY_EXHAUSTED` | `PICK_A:OK`、**`PLACE_A:OK`**、**`VERIFY_A:OK`** |

两臂 `world_sha256` **完全相同**：`2ebf1148b7f975569564661f6d78e5c007e75a4dcb52fc9b4c172d6981c9aa90`。

**legacy 的失败点在 PLACE_A**（`ERR_PLACE_FAILED`，legacy error 25），
**MTC 通过了 PLACE_A 与 VERIFY_A**（完整做完第一个物体），随后在 **PICK_B** 连续两次
`ERR_MOTION_FAILED`（error 30）→ 重试预算耗尽。

## 4. 判读（严格）

**可以说的**：在同一受约束世界里，**MTC 到达了 legacy 无法到达的阶段**——
legacy 连第一个物体的放置都做不成，MTC 完成了"放置 + 独立验证"。
这是 Track C 第一次拿到**机制层面的差异证据**，而不是又一批普通场景样本。

**不能说的**：
- **两边都没有完成整个任务**，所以这是一次**部分能力差异**，不是"MTC 能解这个场景"；
- n=1/臂，单次运行，**不能算成功率**；
- MTC 在 PICK_B 失败，很可能是**我的顶板尺寸只考虑了 box A**，把 box B 也挡住了——
  这是**场景设计缺陷**，不是 MTC 的边界。

## 5. 结论

**`C13_MTC_REACHES_A_PLACE_PHASE_LEGACY_CANNOT`**

比"BLOCKED"强：现在有可复现的、同一世界下的阶段差异。
比"证明 MTC 更优"弱得多：两边都失败，且失败点 B 疑似是我把场景做坏了。

## 6. 下一步（已可执行，不需再解封）

把顶板缩到只覆盖 box A 的上方（或抬高到 z=0.20），让 box B 可抓，重跑两臂：
- 若 MTC **完成**而 legacy 仍失败 → H1 成立，Track C 得到真正的机制证据；
- 若两边都完成 → H0，受约束世界不构成区分，需换约束维度；
- 若 MTC 也失败在同一阶段 → 记录为 MTC 的边界。

## 7. 复现

```bash
bash ci-public-window/scripts/c13_run3.sh   # 两臂
bash ci-public-window/scripts/c13_verify.sh # 独立校验
```
