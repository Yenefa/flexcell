# EvoBot Baseline B — 第一次 Agent 自主规划任务

**任务：** `T01-train-seed1000`（与 Baseline A **同一实例**）
**臂：** B（Runtime Agent）— **Agent 自主规划，不修改源码**

## 结果

| 项 | 值 |
| --- | --- |
| Agent 规划 | `a→zone_1`, `b→zone_2` |
| Agent 理由 | "Red block goes to the right bin (negative y)." |
| Agent 置信 | high |
| composite 结果 | `outcome=0`，两阶段完成 |
| **独立验收** | **PASS** |
| 落点误差 | 10.34 mm / 5.55 mm（阈值 60 mm） |
| `false_success` | **false** |

## 与 Baseline A 的配对对照

| | A 确定性 | B Agent |
| --- | --- | --- |
| 映射来源 | 从 spec 机械推导 | **Agent 从指令 + 感知推断** |
| 映射 | a→zone_1, b→zone_2 | a→zone_1, b→zone_2 |
| 独立验收 | PASS | **PASS** |
| 落点误差 | 9.26 / 4.39 mm | 10.34 / 5.55 mm |
| Token 成本 | 0 | 有（未记录数值） |

**同一实例、同一验收器、同一阈值。** B 的映射与 A 一致，说明 B 不是"碰巧另一个答案"。

## Agent 是怎么知道左右方位的

我在观测里给了**机器人坐标系约定**：
> `+y is the robot LEFT, -y is the robot RIGHT, +x is forward.`

这是**机器人事实**，不是任务答案——就像人类操作员知道自己的左右。
Agent 自己完成了：颜色→物体、方位词→坐标符号、物体→箱子。

## 这个结果证明了什么

1. **Baseline B 存在且可用**：Agent 能从自然语言 + 感知产生可执行计划。
2. **信息隔离有效**：Agent 输入只有 `instruction / objects / zones / skills`，
   `verify.py` 断言其中不含 `expected / placement / evaluator / tolerance / unmoved`。
3. **A 与 B 可配对比较**：这是区分"栈的能力"与"Agent 的能力"的前提。

## 这个结果**没有**证明什么

- **n=1**，一个实例。T01 是最简单的模板（两个独立抓放）。
- **没有证明恢复能力**（Question B）——本轮没有失败可恢复。
- **没有证明经验迁移**（Question C）。
- **没有跑 held-out**，且隔离尚未强制执行。
- Token 成本**没有记录**，因此还不能说"B 用了多少代价换来这个结果"。

## 途中修掉的缺陷

| 缺陷 | 类型 |
| --- | --- |
| `Chat` 客户端没有 `complete()`，实际接口是 `chat(messages)` | 我的假设错误（未读接口就调用） |
| 测试里的 stub 与真实接口不一致 | 同一根因 |

**这是本轮第 3 类错误**：按印象调用接口，而不是先读接口。
