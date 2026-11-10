# T05 中转任务 — 多实例结果（n=6）

**关键：把三种失败分开统计。** 第一版我把它们混在一起，得出"成功率 33%"，
那个数字会让人以为 Agent 不行——实际上是**我的 harness 崩了 3 次**。

## 分层结果

| seed | A′ 能规划 | 层 | 说明 |
| --- | --- | --- | --- |
| 1000 | 否 | **PASS** | 全部子句通过 |
| 1001 | 否 | EXECUTION | `err 62` 运动未达成 |
| 1002 | 否 | EXECUTION | `err 62` 运动未达成 |
| 1003 | 否 | HARNESS | 栈未启动 |
| 1004 | 否 | HARNESS | 栈未启动 |
| 1005 | 否 | HARNESS | 栈未启动 |

## 诚实的结论

| 层 | 数量 | 含义 |
| --- | --- | --- |
| **规划层** | **6/6 正确** | Agent 每次都生成了正确的两阶段中转计划 |
| 执行层 | 1/3 成功 | 真实运动失败（`POSE_NOT_REACHED`） |
| Harness | 3/6 | Gazebo 栈未起来，**与 Agent 无关** |

**规划 6/6，执行 1/3。** 这两个数字必须分开说：
- 「Agent 能规划中转」—— **证据充分（6/6）**
- 「Agent 能完成中转任务」—— **证据不足（1/3，且样本仅 3）**

## 修掉的真实缺陷：准入锁是非阻塞的

### 症状
复合任务第二阶段立即失败：
```
err 41: another pick goal is active
err 30: another MoveToPose goal is active
```

### 根因
`RunComposite` 在上一阶段返回终态后**立刻**派发下一阶段，
而上一阶段的 goal handle 释放要晚几毫秒。
`self._admission.acquire(blocking=False)` **立即拒绝**，
于是一个**完全合法**的计划被判失败。

### 修复
改为**有界等待**（`acquire(timeout=5.0)`）：
- 锁真被别的任务占用时，**仍然拒绝**，错误码不变；
- 只是不再因为几毫秒的交接窗口误杀。

修改点（**两处，我第一次只改到一处**）：
1. `pick_server.py` 的 admission
2. `move_to_pose_server.py` 的 `_register_planned`
3. `move_to_pose_server.py` 的主 admission（**第一次漏掉的那个**）

**教训**：`grep` 到一个匹配就以为改完了。实际有 3 处 `blocking=False`，
我改完 2 处后重跑，错误从 `err 41` 变成 `err 30`——同一个 bug 的另一张脸。

## 修复后剩余的失败是真实的
并发冲突消除后，剩下的失败是：
```
POSE_NOT_REACHED
measured pose outside tolerance: pos=0.1807m (tol 0.020)
```
这是**运动学/控制层**的真实失败，不是 harness bug。
**我停在这里，没有去调大容差。**

## 没有证明什么

- 执行成功率 1/3 的**样本只有 3**，不能得出稳定结论。
- 3 次 harness 失败说明**测试环境本身不稳定**，这会污染任何成功率统计。
- 未跑 held-out。
- **Level 2（Compose）仍不能宣称**：规划能力有证据，完成能力证据不足。

## 下一步（按价值排序）

1. **稳定 Gazebo 启动**——3/6 失败率让任何统计都不可信；
2. 归因 `POSE_NOT_REACHED`：是 IK、碰撞、还是超时？
3. 稳定后再跑 n=20。
