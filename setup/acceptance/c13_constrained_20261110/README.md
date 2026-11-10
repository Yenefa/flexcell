# C13 — 受约束世界下的 FSM/MTC 对照（**结论：否定，且附带一个真实缺陷发现**）

## 0. 结论

**在公平的受约束场景里，legacy（FSM 派发）完成整个任务，MTC 没有。**

Track C 机制问题的答案：**MTC 没有展示出 FSM 缺失的能力**（至少在这个场景上）。

## 1. 四次运行（缺一不可）

| 运行 | 世界 | 结果 |
| --- | --- | --- |
| **`mtc-default`（对照）** | 默认世界 | **PASS 6/6** |
| `legacy` | 0.12 m 顶板（公平） | **PASS 6/6，29.6 s** |
| `mtc` | 0.12 m 顶板（公平） | **FAIL @ `PLACE_B`** |
| `plate030-legacy` / `plate030-mtc` | 0.30 m 顶板（**我的 bug**） | 均 FAIL |

### 为什么必须有 `mtc-default` 这个对照
没有它，"MTC 在受约束场景失败"可能只是"**MTC 本来就做不了 dual_object**"。
现在证明**不是**：MTC 在默认世界 **PASS 6/6**。
所以受约束场景**确实**区分了两者，而方向**与假设相反**。

## 2. MTC 的失败不是规划超时

从 `skills/move_to_pose.jsonl` 里取到的真实原因：

```
outcome: FAILED
detail: ValueError: measured start state differs from planned trajectory
        (move_to_pose_server.py:288, _consume_mtc)
```

### 这是一个独立的真实缺陷（本轮顺带发现）

```python
if joints is None or age is None or age > .5 or any(
        name not in positions or abs(positions[name] - trajectory...points[0].positions[i])
        for i, name in enumerate(...)):
    raise ValueError("measured start state differs from planned trajectory")
```

`abs(...)` **没有和任何容差比较**——非零即真。也就是说这里要求
**实测关节角与规划起点精确浮点相等**。这在真实硬件上不可能成立。

**我没有在实验中改它**，因为那会污染 C13 的结果。它被记录为待修缺陷。

## 3. 被我自己推翻的那一半

第一次跑用 **0.30×0.30 m** 顶板，把 box B 也挡住了。当时我看到"MTC 到 `VERIFY_A`、
legacy 止于 `PLACE_A`"，就写成了"MTC 更强"。**那是错的**：两者撞的是同一块板，
只是 legacy 先撞。缩到 0.12 m 后方向反转。

`verify.py` **同时断言两轮**，任何人都不能只引用有利的那半段。

## 4. 判读边界

- n=1/臂；
- 单一场景；"受约束"只实现为一块静态顶板；
- 因此只能说：**在这个场景上** MTC 无优势，**不能**推广到多候选/窄通道/动态障碍；
- 而 MTC 这次失败的直接原因是**状态一致性检查过严**，不是规划能力不足——
  这一点很重要：**不能说"MTC 规划能力差"**，只能说"这条路径上有阻塞"。

## 5. 下一步

1. **修 `_consume_mtc` 的容差**（独立缺陷，与 Track C 结论解耦），然后重跑 C13；
   若修好后 MTC 能 PASS，则"C13 否定结论"需要**撤回**——它可能只是这个 bug 的产物。
2. 换约束维度（多候选路径、窄通道），保留 FSM 对照。
