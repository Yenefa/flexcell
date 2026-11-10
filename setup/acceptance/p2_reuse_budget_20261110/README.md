# P2 — 经验复用：**双臂对照证明"可复用且有成本收益"**

> 取代 `p2_reuse_20261110`（该次被 40k 预算截断，按更正规则作废）。

## 1. 设计（含对照臂，事后追加，已声明）

| 臂 | 缺陷 | 预算 | 定位信息 | 经验文件 |
| --- | --- | --- | --- | --- |
| **A 实验臂** | VERIFY 分支 | 150k | 关闭 | **有** |
| **B 对照臂** | VERIFY 分支 | 150k | 关闭 | **无** |

任务文本、模型、工具、验收全部相同。缺陷在 **VERIFY 分支**（旧缺陷在 PLACE），
**症状相同但代码不同**——不能用"记住行号"解释。

**对照臂是看到实验臂结果之后才补的**，预注册里已明确声明；它的作用是**排除**
"经验其实没起作用"这一解释，不是挑选有利结果。

## 2. 结果

| 指标 | A 有经验 | B 无经验 | 差异 |
| --- | --- | --- | --- |
| 目标 `dual_object` | **PASS** | **PASS** | — |
| 回归 `normal`/`regrasp` | PASS/PASS | PASS/PASS | — |
| 迭代 | **9** | 11 | **−18.2%** |
| Token | **91,664** | 121,496 | **−24.6%** |
| `list_dir` | **18** | 59 | **−69%** |
| `run_execution` | 6 | 3 | +3 |
| 是否读经验 | **是** | 否（已断言） | — |
| `claim_success` / `false_success` | false / false | false / false | — |

**判定：`P2_EXPERIENCE_REUSED_AND_CHEAPER`**

## 3. agent 自己写的修复注释（两臂都有，内容不同）

**A（有经验）**：
```python
# the verified object's own destination zone - using a fixed
# object here made the second object verify against zone_1
zx, zy, zz = zones[zone_of[decision.target]]
```

**B（无经验）**：
```python
label = 'VERIFY_%s(attempt=%d)' % (tag, vattempt)
# the expected pose is the zone THIS target was assigned to
# (a hardcoded obj_...
```

两臂都靠**执行证据**推出根因，但 A 的推理路径短得多（`list_dir` 18 vs 59）——
与"经验把定位成本降下来"一致。

## 4. 达到目标 §4 的哪一条

| 要求 | 状态 |
| --- | --- |
| ① 人工编写的修复提示 | 存在（Level B） |
| ② Agent **自主归纳**的经验 | **仍未达成**（记录由工程师写） |
| ③ Agent **真正复用**的经验 | **有证据，且测得成本收益** |

## 5. 诚实边界
- **n=1 / 臂**，探索性，不能算置信区间；
- 经验**生产者仍是人**（第 ② 项未达成）；
- 节省 18%/25% 是**单次对照**，可能含运行间方差；
- 两臂都成功，所以证明的是**成本收益**，不是**可行性差异**。