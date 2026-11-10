# n=16 配对：让 `err 62` 可归因，恢复率 3/4

## 上一轮留下的问题

上轮有 **2 例 `err 62` 停在 `UNKNOWN`**，分类器说：
```json
{"action": "no_recovery", "failure_class": "UNKNOWN",
 "measured_reason": "component failed (code 62); no discriminator"}
```
我当时写的是「需要更多诊断信息，而不是放宽分类器」。**这轮就去拿那个信息。**

## 第一步：诊断信息一直都在，只是没被读

composite journal 里已经有每阶段的 native 结果：
```json
{"event": "NATIVE_TERMINAL", "stage_id": "target_box_a-0",
 "component": {"error_code": 50,
   "detail": "policy abort: place failed (ERR_PLACE_FAILED)",
   "final_state": {"fsm_trace": ["PICK_A(attempt=1):OK", "PLACE_A:FAIL"]}}}
```
**真实原因是 place 技能失败**，不是「未确认」。

新增 `runtime/recovery/diagnostics.py` 读取它，实测：
```
before: ('UNKNOWN', 'component failed (code 62); no discriminator')
after : ('grasp', "native place stage failed: ['PICK_A(attempt=1):OK', 'PLACE_A:FAIL']")
```

## 第二步：修好归因后，又暴露一个更深的缺陷

重跑后这 2 例变成了 `redispatch`（重放原计划），错误码从 **62 → 61**：

```
attempt1: err 62   completed_stage_ids = []
实测: box_a 从 (0.22, 0.0) 移到了 (0.116, -0.2)   ← pick 成功、place 失败，箱子被挪走了
attempt2: err 61   state drift or occupied destination
```

**我的恢复逻辑有个真实缺陷**：我用 `completed_stage_ids` 判断「世界是否改变」。
但**失败的阶段本身也会改变世界**——pick 成功、place 失败时，箱子已经在别处了，
而 committed 列表仍是空的。

### 修复：用**实测位置**判断世界是否改变
若实测位置与计划声明的 `initial_objects` 偏差 > 20 mm，则禁止重放，改用 resume。

## 结果

| 指标 | 修复前（上轮） | 本轮 |
| --- | --- | --- |
| B 首试通过 | 13/16 | **12/16** |
| **R 最终通过** | 14/16 | **15/16** |
| 配对增益 | gained=1 | **gained=3, lost=0** |
| 触发重试 | 2 | **4** |
| **恢复率** | 1/2 | **3/4 = 75%** |
| **False Success Rate** | 0/16 | **0/16** |
| Harness 失败 | 0 | **0** |

## 必须诚实说明的方差

**B（首试）在同一批 16 个实例上，跨批次是 9 → 13 → 14 → 12。**
这是执行层的真实波动，不是我的修复造成的。

所以：
- **恢复率 3/4 = 75%** 是目前最好的估计，但触发仅 4 次，**不是稳定数字**；
- 单批次 B 差异若小于 9–14 这个波动范围，**不能当作结论**。

我保留了这个波动记录（`variance.txt`），而不是只报本轮好看的 12/16。

## 仍未恢复的那 1 例

`HO-1ca3385be0b3`：resume 后仍 `err 62`。这是**真实的抓放失败**，
重试同一策略不会自动变好——需要更好的抓取参数或视觉反馈，不在本轮范围。

## 关键安全性

- 恢复**只由执行结果触发**，从不由验收结果触发；
- `clearance`、箱半径、间距、验收容差 **全部未动**；
- 修复都落在「让计划与世界一致」，不落在「让判定变宽松」。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **124 passed** |
| 封存 | `BLOCKED_GOOD` |
| 上一批证据 | **保留**（verifier 断言它仍在） |

## 不宣称

- 不宣称恢复率 75% 稳定（触发 4 次）；
- 不宣称 Level 3 达成（1 例仍失败，且抓取失败类无解）；
- 不宣称 15/16 可外推（单批次 16 实例）。
