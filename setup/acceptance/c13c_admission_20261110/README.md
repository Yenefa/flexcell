# C13c — 准入修复后：MTC **能放置了**，但卡在撤回

## 1. 预注册与实际结果

预注册写了三种可能（`docs/C13C_PREREGISTRATION.md`），实际是 **H2**：
**失败点后移，错误码改变，两个问题并存。**

## 2. 改了什么

只改一处取锁方式（`mtc_planner.cpp`）：
```cpp
// 之前：抢不到立刻拒绝
std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
if (!lock.owns_lock()) { r->detail = "planner busy"; return; }

// 之后：有限等待（10 s），超时仍拒绝
std::unique_lock<std::timed_mutex> lock(mutex_, std::defer_lock);
if (!lock.try_lock_for(std::chrono::seconds(10))) {
  r->detail = "planner busy: admission wait exceeded 10 s";
  return;
}
```
成员从 `std::mutex` 改为 `std::timed_mutex`。**未改**回调组、线程数、重试次数、任何验收门。

## 3. 结果（三臂）

| 臂 | 结果 | 说明 |
| --- | --- | --- |
| `mtc-constrained` | **ROBOT_FAILURE @ `PLACE_B`** | 但**失败点后移** |
| `legacy-constrained` | **PASS 6/6** | 对照，未受影响 |
| `mtc-default` | **PASS 6/6** | 对照，未受影响 |

### 修复确实生效了
- 修复前：`planner busy` 拒绝，**0 次成功规划**；
- 修复后：**12 次 MTC 移动，11 次成功**，日志里**再无 `planner busy`**。

### 而且物体真的放下了
```
detail: "object dropped (place_err=0.000) but retreat failed: ..."
```
**放置误差 0.000 m**——MTC 完成了抓取、搬运、放置。

## 4. 剩下的失败：撤回

```
ValueError: measured start state differs from planned trajectory:
  joint1 measured=0.20671 planned=0.20671 delta=0.0
  joint2 measured=-0.19399 planned=-0.19183 delta=0.00216
  joint3 measured=0.36051 planned=0.41343 delta=0.05292   <== 超过 0.03
  joint4 measured=-0.43809 planned=-0.43809 delta=0.0
```

**容差 0.03 rad，joint3 差 0.0529 rad。**

注意这次的数据是**加了日志之后才有的**——上一轮同一个 guard 触发时，
我们连差多少都不知道，因此只能记 UNKNOWN。

### 这意味着什么
撤回轨迹的**规划起点（0.41343）与实测（0.36051）不一致**。
放置动作完成后机械臂的实际位置，与规划撤回时假设的起点不同。
这是**规划快照与执行状态之间的偏差**，不是并发问题。

## 5. 对 Track C 结论的影响

| 之前 | 现在 |
| --- | --- |
| "MTC 在这个场景失败" | **"MTC 完成了放置，卡在撤回"** |
| 归因：planner 并发拒绝 | 归因：**撤回轨迹起点与实测不符** |

**"MTC 无优势"的结论需要弱化**：它不是做不到，而是**在收尾阶段有另一个缺陷**。
但**也不能说 MTC 有优势**——它仍然没有完成整个任务，而 legacy 完成了。

## 6. 边界

- n=1/臂；
- 只修了准入，未修撤回；
- 撤回的根因（为什么规划起点会偏离）**尚未定位**，不得猜测。

## 7. 下一步

1. 查清撤回轨迹的规划起点从哪来（是否用了预测状态而非实测）；
2. 修好后重跑，才能对"MTC 是否能完成受约束 dual_object"给出定论。
