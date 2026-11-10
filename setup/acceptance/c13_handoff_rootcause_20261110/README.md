# C13b — MTC `PLACE_B` 失败根因：**已确定**

> 前两版解释都是错的，且都已撤回（见 §6）。这一版有实测日志支撑。

## 1. 方法：先加日志，再下结论

上一版记为 UNKNOWN，因为**失败点没有被记录**。这次先做一件事：
在 `_consume_mtc` 里把「实测值 / 轨迹起点 / 差值 / 容差」全部写进 `detail`。

重跑后 `_consume_mtc` **一次都没有触发**——9 次 MTC 移动**全部 SUCCEEDED**。
失败点因此移动到了别处，这才看清真正的错误：

```
place.jsonl → outcome=1, error_code=30
detail: "MTC planning failed before execution: planner busy"
```

## 2. 根因链（全部有代码或日志依据）

### (a) 两个 MTC 服务共享一个 `Reentrant` 回调组
```cpp
// mtc_planner.cpp:39
group_ = create_callback_group(rclcpp::CallbackGroupType::Reentrant);
// :42-47 两个服务都用 group_
```
**`Reentrant` 明确允许并发进入回调。**

### (b) 执行器是多线程的
```cpp
// mtc_planner.cpp:351
rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
```
4 个线程 + Reentrant 组 ⇒ `handle()` 可以被**同时**调用。

### (c) 互斥锁用 `try_to_lock`，抢不到立刻返回
```cpp
// mtc_planner.cpp:61-62
std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
if (!lock.owns_lock()) { r->detail = "planner busy"; return; }
```
**不排队、不等待、不重试**——直接拒绝。

### (d) 上层重试也不够
```python
# mtc_motion.py:67-86
retries = 2                      # 共 3 次
...  time.sleep(3.)              # 间隔 3 秒
```
实测 3 次重试全部 busy。说明占用时间长于 ~9 秒，或占用方在同一进程内持续竞争。

## 3. 为什么 legacy 不受影响

legacy 走 MoveIt 的 `MoveGroup` 规划，**不经过这个 planner 服务**，
所以同一个受约束场景下 legacy **PASS 6/6**，而 MTC 失败。

## 4. 结论

**MTC 在 `PLACE_B` 的失败不是规划能力问题，也不是轨迹交接问题，
而是 planner 服务的并发准入设计：`Reentrant` 组 + `try_to_lock` = 高负载下静默拒绝。**

这也解释了为什么它是**间歇性**的——同一份代码在默认世界能 PASS 6/6。

## 5. 对 C13 结论的影响

C13 说"MTC 无优势"，**结论方向不变但归因必须修正**：
- 不是"MTC 规划不出绕障路径"；
- 而是"**MTC 的规划服务在并发下会拒绝请求**"。

后者是一个**工程缺陷**，比"规划能力不足"更容易修，也更应该修。

## 6. 我在这个文件里撤回过的两个错误解释

| # | 我说过 | 为什么错 |
| --- | --- | --- |
| 1 | "guard 没有容差，要求精确浮点相等" | 代码是 `> .03`；我读取时截断显示了该行 |
| 2 | "夹爪关节差 0.031 触发检查" | 只比较 4 个手臂关节；且我比错了对象（相邻两次运行 vs 轨迹起点） |

两次共同点：**用自洽的故事替代了去取真正的数据。**
这次先加日志再判断，才拿到真答案。

## 7. 建议的修复（未实施，需预注册）

1. 把 planner 服务放进 **MutuallyExclusive** 组（或独立组），从根上消除重入；
2. 或把 `try_to_lock` 改为**带超时的阻塞等待**，并在 detail 里写明等待了多久；
3. 修好后重跑 C13 两臂，才能判断"MTC 无优势"是否仍然成立。
