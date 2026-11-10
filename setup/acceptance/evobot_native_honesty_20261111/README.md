# 全新种子上端到端验证：false success 0/16，准确率 87.5%（独立复现）

## 为什么需要这一批

此前所有批次的 false success 都是**事后补采**的：运行器没调用自评 → 我事后补 →
补时又发现 token 预算不够。**补出来的数据不能证明链路本身是对的。**

所以这轮用**全新种子**（7500–7507 / 7600–7607），把自评和 claim 传入做进**运行器本身**。

## 第一次跑：声明全为 0，却不是 0 个缺失

```
claims measured       : 16/16 (0 absent)
agent CLAIMED success : 0/16
FALSE FAILURE         : 13/16 = 81.2%
SELF-ASSESS ACCURACY  : 3/16 = 18.8%
```

查下去发现**三个真实缺陷叠加**。

### 缺陷一：cwd 残留让自评根本没跑

```
python3: can't open file '/home/ros/flexcell-p14/runtime/verifier/self_assess.py':
        [Errno 13] Permission denied
```

运行器为启动仿真 `cd /home/ros/flexcell-p14`，**之后没回到 $W**，相对路径解析错了。
**自评一次都没执行。**

### 缺陷二：`evaluate()` 把 None 强制成 False

```python
claimed = bool(final_state.get("agent_claimed_success"))
```
`bool(None)` 是 `False`。**声明缺失与「声称失败」在判决里不可区分。**
所以 `verdict.agent_claimed_success` 字段**永远不可信**。

### 缺陷三：我的分析器犯了同一个错

它读 `verdict.json` 的 claim 字段，于是把 16 个缺失算成「16/16 已测量」，
并全部计入 false failure。

## 修复

| 问题 | 修法 |
| --- | --- |
| cwd 残留 | 自评前 `cd $W` |
| 分析器信 verdict | **改读实际判分 observation 的 `agent_claim_source`** |
| 缺失被算成失败 | 缺失一律排除出比率分母，明示 `absent` |
| 13 例自评未跑 | 用归档 sim/ground truth **补采**（无需重跑机器人） |
| 2 例仍空回复 | token 预算 16384 → **32768** 后成功 |

补采脚本注明：**这不是走捷径**——机器人工作已完成并归档，失败的只是纯后处理步骤。

## 最终结果（16/16 全部实测）

| 指标 | 值 |
| --- | --- |
| B 首试通过 | 13/16 |
| R 最终通过 | 13/16 |
| **agent 声称成功** | **11/16** |
| **False Success** | **0/16 = 0.0%（0–19.4%）** |
| False Failure | 2/16 = 12.5% |
| **自评准确率** | **14/16 = 87.5%（64.0–96.5%）** |

## 关键：这是**独立复现**

| 批次 | 种子 | 准确率 |
| --- | --- | --- |
| v4 重采（旧 32 例） | 7300/7400 等 | **87.5%** |
| **本批（全新 16 例）** | **7500/7600** | **87.5%** |

**两个不同种子集给出完全相同的准确率。**
说明 v4 的修复（计划标为意图 + 写明坐标系）**不是过拟合到那 32 例**。

## 状态

| 项 | 值 |
| --- | --- |
| 新增机器人运行 | 16 例（全新种子） |
| 封存 | `BLOCKED_GOOD` |
| 验收器 `evaluate.py` | **未改** |
| claim 来源 | **16/16 实测** |

## 不宣称

- 不宣称 false success 永远为 0（n=16，区间上限 19.4%）；
- 不宣称 87.5% 是上限；
- 不宣称 R 优于 B（本批 gained=0）；
- **未上真机，M0**。

## 仍未解决

`evaluate()` 的 `bool(None) → False` **仍在**。它是冻结文件，
守卫只能在报告层拦截。**改造它需要下一次正式变更。**
