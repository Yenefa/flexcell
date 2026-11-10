# 回归：间距修复未破坏已冻结能力（6/6 → 6/6）

## 为什么必须做这一步

上一轮把共享模块 `spread_destinations.SPREAD_STEP_M` 从 0.056 改到 0.090。
这个模块被 **v0.1 全部任务**（通过 `prepare_baseline_b.py`）和恢复路径共用。

改完共享代码后直接报「8/8 通过」是不负责任的——
**v0.1 held-out 是已经独立验证过的冻结基线，必须逐任务比对，不能只看新数字。**

## 结果：无回归

| task | 改动前 | outcome | 改动后 | outcome |
| --- | --- | --- | --- | --- |
| HO-008a467cde3f | PASS | 0 | PASS | 0 |
| HO-13c5efca228e | PASS | **1** | PASS | **0** |
| HO-3654cf0ad144 | PASS | 0 | PASS | 0 |
| HO-387696edc61f | PASS | 0 | PASS | 0 |
| HO-38e7aabc1d67 | PASS | 0 | PASS | 0 |
| HO-3bd4abddd259 | PASS | 0 | PASS | 0 |

**before 6/6 → after 6/6，0 个回归。**

## 附带收获：上上轮那例分歧被顺带修好

`HO-13c5efca228e`（T03 同箱顺序）此前是 `outcome=1` 却 `graded=True` 的**分歧通过**——
执行器报 `err 62`，但实测落位正确。

间距改为 0.090 后变成 `outcome=0` 的**干净通过**。
说明当时那例分歧的根因就是间距余量不足，和本轮 4 例 `err 61` 是同一个。
**一个根因修复解决了两批不同的失败。**

## 回归门加固：删掉基线不能再绕过门禁

回归门新增 `held_out_baseline_intact()`：
检查 hold-out 基线里每一条 PASS verdict 是否仍在磁盘上。

### 发现并修掉的弱点
第一版在**基线目录不存在**时返回 `True`（「还没记录基线」）——
**这等于说：把证据删掉就能通过门禁。**

改为：**基线缺失即失败**。基线已提交在仓库里，缺失只可能是被移除。
新增测试覆盖两种情况：
- 基线完整 → 通过；
- 基线目录被删 → `gate` 返回 `accepted=False`。

实测：
```
intact: (True, 'held-out baseline intact (6 passing verdicts)')
gate with missing baseline: (False, 'held-out baseline evidence is missing from the repository')
```

## 当前门禁实跑结果

```
"accepted": true,
"reason": "all 50 verifiers still pass, id=d221e5a8e556"
```
**50 个验收 verifier 全部通过**才放行提案。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **110 passed** |
| v0.1 held-out 回归 | **6/6 → 6/6，0 回归** |
| 回归门 verifier 数 | **50** |
| 封存隔离 | `BLOCKED_GOOD` |

## 不宣称

- 不宣称 6/6 是稳定成功率（单批次）；
- 不宣称 v0.2 未见任务也全部无回归——本轮只回归了 v0.1 冻结集；
- 不宣称 Level 3 恢复率可测（修复后恢复路径未被触发）。

## 下一步

1. 把 v0.2 未见任务集也纳入回归基线；
2. 用**可控扰动**（非设计错误）测真实恢复率。
