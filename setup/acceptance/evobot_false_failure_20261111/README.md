# 发现 false failure：世界成功了，任务却报告失败

# 32 例中 2 例（6.2%）

## 这是 false success 的镜像

| 方向 | 含义 | 实测 |
| --- | --- | --- |
| false success | agent 说成功，世界没成 | **0/32** |
| **false failure** | **任务说失败，世界成了** | **2/32 = 6.2%（1.7–20.1%）** |

两者都由**同一件事**决定：agent 的自述是否与世界一致。
我此前只盯着 false success，**从未测过反方向**。

## 证据链（两例完全同构）

```
技能层 place.jsonl:
  target_box_b  released=False  err=25  box_after=None   ← 报失败

attempt 1 结束后实测 ground truth:
  target_box_b  pose=[0.157, -0.148]  inside zone_1 (37.4 mm from centre)
  zone_1 半径 = 60 mm  → 箱子已经在目标区内

技能层自己的 verify.jsonl:
  target_box_b  verified=True  error=7.9 mm (tol 60 mm)

独立验收器:
  passed=True   failed_clauses=[]

FSM task.out:
  outcome=1   detail='native terminal/verification unconfirmed for target_box_b-1'
```

**箱子已释放、已在区内、自家验证也通过——但 place 技能报告释放失败。**

## 机理

`released=False` 与 `box_after=None` 同时出现，说明技能**没拿到释放确认**，
于是它把这次 place 记为失败且不记录位置。
但物体实际已经离开夹爪。

这正是我几轮前标记的 `ACTUATOR_STALL_ON_RELEASE` 类别——
**但当时我把它全部当成「真实的失败」。其中至少这 2 例不是。**

## 后果（这是为什么它重要）

1. 恢复驱动读 `task.out`，看到失败就**重试**——重做已经在区内的箱子；
2. 于是 batch2 出现「retried=2 但 b_failed=0」的矛盾信号；
3. **arm R 看起来被使用了，实际毫无必要**；
4. 下游消费者会**重复一个已经完成的任务**。

## 这动摇了一个我预注册过的结论

我曾为 `actuator_stall` 预注册补丁（`bounded_release_retry`，预期「通过率不变，
只买延迟与风险」）。

**现在看，预注册时的事实基础有误**：
至少部分 stall 是「物体已释放但确认丢失」，不是「物体没释放」。
对这类情况重试释放命令**不会改变结果**（早就松手了），
真正的修复方向是**确认逻辑**，不是重试。

因此：**那个提案仍然保持 `requires_human_approval: true`，且其预期效果需要重写。**
我不会在这个新认识下继续推进原提案。

## 新增工具

| 脚本 | 用途 |
| --- | --- |
| `false_failure_rate.py` | 跨批测任务层 false failure，含 Wilson CI |
| `false_failure_mechanism.py` | 单例机制取证（技能日志 / 实测 / 自家验证 / 验收器 / FSM） |

两者**都先过批次结构校验**，未通过则拒绝出数。

## 状态

| 项 | 值 |
| --- | --- |
| 批次 | batch1 + batch2，均 rc=0 |
| 封存 | `BLOCKED_GOOD` |
| 验收器 | **未改** |
| 技能层 | **未改** |

## 不宣称

- 不宣称 6.2% 是稳定估计（n=32，CI 1.7–20.1%）；
- 不宣称所有 stall 都是误报——**只确证了这 2 例**；
- 不宣称已修好——**根因在技能层，未动**；
- 无法从现有日志区分「释放失败但箱子掉进区」与「箱子本就在区」，
  两者都不影响本次结论（世界满足目标 ≠ FSM 说满足）；
- **未上真机，M0**。
