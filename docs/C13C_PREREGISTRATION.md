# C13c 预注册 — 修复 planner 并发准入，检验 MTC 的否定结论是否为该缺陷的产物

**写于修改代码之前。**

## 1. 已被证据确立的事实（C13b）

| 事实 | 位置 |
| --- | --- |
| 两个 MTC 服务共享 `Reentrant` 回调组 | `mtc_planner.cpp:39` |
| 节点跑 4 线程 `MultiThreadedExecutor` | `:351` |
| 互斥锁 `try_to_lock` 抢不到即返回 `planner busy` | `:61-62` |
| 客户端 3 次重试（3 s 间隔）全部被拒 | `mtc_motion.py:67-86` |
| `PLACE_B` 失败时 9 次 MTC 移动全部成功 | 运行日志 |

## 2. 可证伪命题

**H1**：`PLACE_B` 的失败由**准入拒绝**造成，与规划能力无关。
若把"抢不到就立刻拒绝"改为"在有限时间内排队等待"，MTC 应能完成 `dual_object`。

**H0**：即使不再拒绝，MTC 仍在同一阶段失败（且错误不同）。
则"MTC 无优势"的结论加强，且归因需再查。

**H2**：改了之后失败点变化但仍失败——则**两个问题并存**，必须分别记录。

## 3. 修改范围（最小、可回退）

只改 `mtc_planner.cpp` 的**取锁方式**：

```cpp
// 之前
std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
if (!lock.owns_lock()) { r->detail = "planner busy"; return; }

// 之后：有限等待，超时仍拒绝（不无限阻塞，不改变拒绝语义）
std::unique_lock<std::mutex> lock(mutex_, std::defer_lock);
if (!lock.try_lock_for(std::chrono::seconds(10))) {
  r->detail = "planner busy: admission wait exceeded 10 s";
  return;
}
```

**不改**：`Reentrant` 组、执行器线程数、重试次数、客户端超时、任何验收门。

## 4. 这不是"放宽验收"的理由

- 验收器 `gate/acceptance.py` **不动**；
- 成功阈值**不动**；
- 等待上限**写死 10 s**，仍会拒绝，不会把"忙"变成"成功"；
- 这是一次**准入策略**修复：静默丢弃调用方需要的请求本身是缺陷。

## 5. 判定标准（跑之前写死）

| 结果 | 判定 |
| --- | --- |
| MTC PASS `dual_object` | **H1 成立** → C13 的否定结论**撤回**，改为"MTC 曾因准入缺陷失败" |
| MTC 仍在 `PLACE_B` 失败，但错误码改变 | **H2** → 两个问题并存，记录新错误 |
| MTC 仍在 `PLACE_B` 失败，错误码相同 | **H0** → 准入不是原因，我此前的根因判断也错 |

## 6. 必须同时跑的对照

- `legacy` 同一受约束世界（应仍 PASS 6/6，证明没破坏基本链路）；
- `mtc` 默认世界（应仍 PASS 6/6，证明修复没引入新问题）。
