# MISSION UPDATE — goal round 4 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮结论：我上一轮的「发现」是重发现，而它依赖的提案本身有缺陷

本轮做了三件事，每一件都**推翻或收窄**了某个已有的说法，包括我自己的。

## §19.2 第一件：我重发现了昨天的成果（过程错误）

第 3 轮我把 `place` 释放缺陷当作**新**根因发现来呈现。**它不是。**

2026-11-11 已经用 9 例确立了同一机制（`setup/acceptance/evobot_release_mechanism_20261111/`），
更早的错误提案 `bounded_release_retry` 已被显式作废，正确的修复**已经预注册并在等批准**：

```
evolution/proposals/release_confirmation_preregistration.json
  proposal_id: release_confirmation_over_gripper_aperture
  registered_at: 2026-11-11   approved: false
  target_file: .../place_server.py
```

**我只检查了代码里有没有这个 bug，从未检查项目是否已经知道。**
纠正措施（一般化）：**诊断缺陷前，先搜 `evolution/proposals/` 和 acceptance 归档里有没有它的签名。**

## §19.3 第二件：项目的结果没有被污染——只有执行判决被污染

我本想用「承载释放」这个与物体因果相连的可观测量重新评分全部归档，替换掉被污染的
执行数字。**重评分把结论溶解掉了。**

| 项 | 数值 |
| --- | --- |
| 扫描的归档 run | **238** |
| 命中 place 释放缺陷 | **47（19.7%）** |
| 其中承载仍然释放了 | **47（100%）** |
| 承载被卡住未释放 | **0** |
| 这 47 次中记录为 PASS | **28** |
| 记录为 FAIL | 11 |

**我原来的判据「所有阶段都释放了、没有卡住」是必要但非充分的。** 释放不等于放到位。
逐个核对 11 个记录的 FAIL，对照失败子句自己的证据与 ground truth：

```
候选测试            : 11
可证明的 False Failure:  0
```

**11 个全是真实失败**——多数是一个物体**还停在初始位姿**。任务根本没被执行。

所以第 3 轮「世界是对的、判决是错的」只对**执行判决**成立，对**任务判决**不成立。
`independent_evaluation_passed` 是**可靠的**；只有 `execution_succeeded` 被污染。

**这比我想证明的更强，也更重要**：我差点发表「项目的历史结果被污染」这个说法，而它是假的。

## §19.4 第三件：待批准提案的两处缺陷

### (a) 任务级成功判据是空转的

提案预测：`task_level_false_failure_rate: 6.2% (2/32) -> 0%`，
成功判据之一：「task-level false failure count falls to 0」。

**实测 0/237。** 这个判据**已经满足**，实施后它会「达标」而什么也没证明。

### (b) 安全论证按字面是错的

提案的理由：「evaluator 评的是世界，不是技能自述，所以重新分类自述不可能让失败的世界通过。」

**假的。** `benchmark/evaluators/observe_from_run.py:74,114` 读 `place.released`，
而那个模块**构造的正是 evaluator 所评的 observation**。被修改的字段**在评分路径上**。

### (c) 它为什么仍然安全——但理由是偶然的

```
released=False 的 place 行        :  51
  其中带 box_after 的             :   0   <-- 决定性数字
released=True 且带 box_after 的   : 488
```

`observe_from_run` 需要**同时**有 pose 和 truthy 的 `released`。51 行都没 `box_after`，
所以两种情况下都被跳过，只翻转 `released` 不改变任何东西。

**但这个安全来自「失败路径不写 box_after」——当前代码的偶然属性，不是保证。**

### (d) 真正有风险的是提案自己的后续预测

提案预测 `place_box_after_will_be_recorded: true`。**那是第二个、独立的改动，而且它才是动 evaluator 的那个。**
若失败路径开始写 `box_after`，51 行的 provenance 会从 `verify.jsonl` 变成 `place.box_after`。

| 部分 | 改动 | 评分输入 | 风险 |
| --- | --- | --- | --- |
| **1** | 翻转 `released` | **不变** | 无——但只因为 `box_after` 缺失 |
| **2** | 开始记录 `box_after` | **51 行改变** | 安全论证未覆盖 |

**会不会造成假成功？未证明。** 这些行没有 `box_after`，其未来值无法离线读出。
11 个物体未移动的 run 里，那个位姿不在目标区，所以假成功**不太可能**——**但不太可能不是测试**。

## §19.5 同一个教训的第三次出现

| 位置 | 假设 | 打破它的检查 |
| --- | --- | --- |
| 第 2 轮，T08 门 | 孔径行程意味着抓到了 | 与空气相差 0.42 mm |
| 第 3 轮，`place` | 孔径意味着释放了 | 同一条记录里 `carry_release_confirmed: true` |
| **第 4 轮，该提案** | **「evaluator 不读它」** | **`observe_from_run.py:74` 就读它** |

形状完全一样：**声称某个量没被使用，却没有追踪它的使用。** 便宜的做法是 grep，昂贵的错误是先发表。

## §19.6 能力等级（不膨胀）

| 项 | 等级 |
| --- | --- |
| 归档重评分 | **Simulation Tested 之上、Generalization 未及** — 离线、238 run、可复现 |
| 提案验证 | **未实施**；提案仍 `approved: false`，`place_server.py` 未动 |
| T08 | 未变，skill 级 **0/6** |
| P0 A′ vs B | **仍无法区分** |
| L4 Develop | **未跨过** |

## §19.7 待人工决定（累积，未实施）

1. `place_server.py` 释放判据（**第 1 轮提出，第 4 轮证明其安全论证有误、判据空转**）
2. 提案拆分：part 1 / part 2 分别立判据
3. 修正 anti-gaming 论证，点名 part 1 安全所依赖的条件
4. 开口度上限（2 mm → gap (4.83, 11.70) mm 内某值）与增加 lift 门
5. 前几轮六项

## §19.8 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0**（本轮全为离线日志/归档分析） |
| 孤儿进程 | 0 |
| 冻结文件改动 | **0** |
| 阈值改动 | **0** |
| 删除失败证据 | **0** |
