# 第一个非事后提案：系统自己发现了未修复的缺陷

## 我上轮的判断错了，这轮改正

上轮我写：「执行器 stall 在技能层，**不在我的作用域**」。
这轮先核对了这个判断——**它错了**：

`src/flexcell/flexcell_skills/flexcell_skills/place_server.py`
**是被 git 跟踪的，就在本仓库里**（`src/flexcell` 下 212 个文件）。

> 附注：我第一次核对时用 WSL 的 git，因 worktree 路径解析失败得到「未被跟踪」——
> **那是假结果**，改用 Windows git 才看清。又一次「工具错了不等于事实」。

## 代码确认的缺陷

```python
# place_server.py 第 417 行，整个文件里唯一一次调用：
gres, gerr = self._gripper.command(self._gripper_open)
```

**单次调用，无任何重试。** 若控制器返回 `stalled=True`（可观测状态），
直接判 `PLACE` 失败。全文件搜索 `retry` / `for attempt` —— **没有**。

## 但这轮的重点不是我去修它

使命要求能力**来自完成任务**，而不是我预先写死修复。
所以正确做法是：**让系统的提案循环自己提出这个改动**。

### 先修一个让提案循环看不见它的 bug

生成器原先只读 `task*.out`，里面是**策略包装层**的话：
`native terminal/verification unconfirmed`。
而 `gripper did not open` **只存在于 episode 记录里**。

**这正是前面几轮让我误判根因的同一个坑。**
修法：把 `execution_root_cause` 从 episode 读到的东西并入证据源。

修复前后：
```
修复前: actuator_stall 不可见（0 条证据）
修复后: actuator_stall n=24  GATE ACCEPTED
```

## 决定性验证：它是「新工作」还是「事后重建」

我写了 `check_applied.check_actuator_stall()`：
**读代码判断释放命令是否已带重试**，而不是读文字。

```
actuator_stall.json        WOULD_FIX          release open issued exactly once (1 call site)
occupied_destination.json  ALREADY_SATISFIED  spacing already 0.090 m
```

| 标签 | 含义 |
| --- | --- |
| `WOULD_FIX` | **当前代码仍有缺陷，这是真正的修复提案** |
| `ALREADY_SATISFIED` | 已实现，提案是事后重建（上轮那个） |

**这是自进化循环第一次产出 `WOULD_FIX`。**

## 提案内容

| 字段 | 值 |
| --- | --- |
| 签名 | `actuator_stall` |
| 证据条数 | **24** 条实测失败 |
| 目标文件 | `place_server.py` |
| 改动 | 释放命令 stall 时有界重试，而非首次即失败 |
| **可falsify的预期效果** | 仅因首次 stall 失败的阶段会成功；**持续 stall 仍必须失败**，故不能把真失败变成通过 |
| 回滚 | `git revert`，恢复到单次尝试 |
| 人工批准 | **`requires_human_approval: true`** |

## 我没有应用它

提案写了 `requires_human_approval: true`，而**我没有拿到批准**。
所以：**只生成、只过门禁、不落地**。

这一点很重要：如果我自己批准自己，那「人工批准」就是装饰。

## Level 5 的状态变化

| 之前 | 现在 |
| --- | --- |
| 循环存在，但唯一提案是事后重建 | **循环产出了第一个 `WOULD_FIX`** |
| Level 5 Improve：未达成 | **仍未达成**（提案未获批、未应用、未验证效果） |

诚实地说：**这是「提案能力」的验证，不是「改进能力」的验证。**
要变成 Level 5，还差：批准 → 应用 → 重跑 → 证明效果且无回归。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **149 passed** |
| 封存 | `BLOCKED_GOOD` |
| 源码改动 | **无**（生成器/检查器，未改 place_server） |
| 验收器 | **未改** |

## 不宣称

- 不宣称 Level 5 达成（提案未获批未应用）；
- 不宣称重试一定能修复 stall（未测）；
- 不宣称 stall 是仿真专属（**未上真机，M0**）。

## 需要的人工决定

**是否批准对 `place_server.py` 做有界释放重试？**
批准后我将：应用 → 重跑 16 例 → 证明 stall 率下降且 false success 仍为 0 → 方可宣称 Level 5。
