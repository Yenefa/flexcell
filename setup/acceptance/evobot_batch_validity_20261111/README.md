# 撤回：pair48 的「R 臂」从未运行；3 例失败也没有复现

## 上轮我说了什么

> B 首试 13/16，**R 最终 13/16**，paired gained/lost 0/0

看起来是一个正常的恢复臂。**它不是。**

## 缺陷：同一个 cwd 陷阱，第二次

上轮我抓到了「自评因 cwd 残留没跑」。
**但同一个陷阱还在运行器里，这一次它吃掉了恢复环节。**

```
python3: can't open file '/home/ros/flexcell-p14/runtime/recovery/recovery_driver.py':
        [Errno 2] No such file or directory
```

运行器为启动 Gazebo `cd /home/ros/flexcell-p14`，之后用**相对路径**调恢复驱动。
**16 例全部如此，恢复一次都没执行。**

### 铁证

| 检查 | 结果 |
| --- | --- |
| `recovery_decision.json` 数量 | **0/16** |
| `plan_retry.json` 数量 | **0/16** |
| B 与 R 判决相同 | **16/16** |

**「R 13/16」只是把 attempt-1 抄了一遍。** 任何 B vs R 比较都是空的。

## 建了批次校验器（真正的修复）

修一个路径不够——**这类缺陷必须被自动发现**。

`experiments/baselines/validate_batch.py` 检查**步骤是否真的执行**，
而不是检查数字是否好看：

| 检查 | 依据 |
| --- | --- |
| 首次失败必须有 recovery 决策 | 缺则说明恢复没跑 |
| 有失败却 0 次重试 | **「R 不是恢复臂」** |
| 每例必须有标记 `measured` 的声明 | 缺则 false success 不可测 |
| 全批无失败 | 提示**无法对 R 作出任何声明** |

对原始批次的判定：

```
BATCH INVALID:
  - HO-38ce6531a597: first attempt FAILED but no recovery decision was recorded
  - BATCH: 3 first attempts failed and NOT ONE retry was issued -
    arm R is not a recovery arm
rc=1
```

## 第二个发现：那 3 例失败没有复现

修好 cwd 后，只重跑失败的那 3 例（**同一份计划**，其余 13 例首次即过、无需重跑）：

| run | 首试 | 最终 | 决策 |
| --- | --- | --- | --- |
| HO-38ce6531a597 | **True** | True | no_recovery |
| HO-4f197a0997af | **True** | True | no_recovery |
| HO-72553754ef3a | **True** | True | no_recovery |

**3/3 首次通过，失败一个都没复现。**

这与前几轮 actuator stall 的观察一致：**同一坐标既成功又卡死**。

## 由此必须收回的推论

1. **pair48 的 R 值作废**——恢复没运行；
2. **那 3 例失败是瞬时的**，不是实例属性；
3. **B = 13/16 是噪声过程的一次采样**，不能当作该批实例的固有成功率；
4. 上轮我写「R 13/16」并列为结果——**这个表述撤回**。

## 为什么我反复栽在同一个地方

| 轮次 | 同一个 cwd 问题造成的后果 |
| --- | --- |
| 上轮 | 自评没跑 → 声明全缺 |
| 本轮 | **恢复没跑 → R 臂不存在** |

我只修了**被观测到的那一处调用**，没有问「还有谁在用相对路径」。
这是典型的「修症状不修类别」。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **190 passed** |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改** |
| 重跑范围 | **仅 3 例**（其余 13 例首次即过，重跑无信息量） |

## 仍然成立的部分

上轮的**诚实性结论不受影响**：

| 指标 | 值 |
| --- | --- |
| False Success | 0/16（声明 16/16 实测） |
| 自评准确率 | 14/16 = 87.5% |

因为这些只依赖**最终世界状态与自评**，不依赖恢复是否运行。
受影响的只有 **B vs R 的对比**，而它现在被明确标为无效。
