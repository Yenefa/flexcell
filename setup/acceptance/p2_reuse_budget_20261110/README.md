# P2 — 经验复用：**agent 读了经验，并在另一个缺陷上完成修复**

> 本实验**取代** `p2_reuse_20261110`。旧实验在 54,142 tokens 被预算截断（`budget_exceeded`），
> 按 `CORRECTION_20261110C.md` 的规则，被截断的运行不能作为能力证据，因此旧的 H0 判定作废。

## 1. 设计

| 项 | 值 |
| --- | --- |
| 缺陷位置 | **VERIFY 分支**（1320 行）——**不是** Level C′ 的 PLACE 分支 |
| 任务文本 | 无文件名、无行号、无修复方向 |
| 定位信息 | **关闭**（`suspect_regions` 不出现） |
| 额外输入 | **唯一**：`experience/experience_place_target.json`（逐字复制的已归档经验） |
| 预算 | **150k tokens / 40 轮** |

症状与旧缺陷相同（`VERIFY_B` 失败），但缺陷在**不同分支**——**不能用"记住了那行代码"解释**。

## 2. 结果：**PASS**

| 项 | 值 |
| --- | --- |
| 迭代 / Token | 9 / **91,664**（占 150k 的 61%） |
| `list_dir` / `read_file` / `run_execution` | 18 / 35 / 6 |
| `edit_file` | **1** |
| 目标 `dual_object` | **PASS** |
| 回归 `normal` / `regrasp` | **PASS / PASS** |
| `claim_success` / `false_success` | false / false |
| **是否读取经验文件** | **是**（`read_file experience/experience_place_target.json`，返回完整 JSON） |

### agent 自己写的修复注释
```python
# the verified object's own destination zone - using a fixed
# object here made the second object verify against zone_1
zx, zy, zz = zones[zone_of[decision.target]]
```
这条注释**对应经验文件里记录的缺陷模式**（"target-object selection"），
说明它没有机械照搬行号，而是把经验当作**模式**使用。

## 3. 这达到了目标 §4 的哪一条

| 目标要求 | 状态 |
| --- | --- |
| ① 人工编写的修复提示 | 存在（Level B），与本实验无关 |
| ② Agent 自主归纳的经验 | **仍未达成**——文件是工程师归纳的 |
| ③ **Agent 后续真正复用**的经验 | **首次获得证据**：读取、跨缺陷应用、修复通过 |

**因此可以说"开始实现 Experience-Driven Improvement"，但必须同时声明：
经验是工程师归纳的，不是 agent 自主归纳的。**

## 4. 诚实边界
- n=1；
- 经验的**生产者**仍是人（第 ② 项未达成）；
- 单次成功不能证明"经验普遍降低修复成本"——本次 9 轮 / 91k，**比**无经验的 P3（10 轮 / 48k）**并不更快、更便宜**；
  事实上 token 更高（91k vs 48k），因为 VERIFY 缺陷更难、且要读经验；
- 所以本实验证明的是**"可复用"**，不是**"有收益"**。