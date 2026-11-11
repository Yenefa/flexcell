# 冻结变更日志

每次修改**固定文件**都必须在此登记理由。
`evolution/validation/freeze_baseline.py` 在重新冻结前会检查本文件；
未登记就试图重新冻结会被**拒绝**。

---

## 2026-11-11 — `benchmark/evaluators/observe_from_run.py`

### 为什么必须改

`build_observation()` 的 `agent_claimed_success` 默认值是 `False`。
`evaluate()` 用 `claimed = bool(final_state.get("agent_claimed_success"))`，
所以**缺失的声明与「声称失败」字节相同**。

后果：`false_success` 成为**结构性零**，无法为真。
我据此报告了多轮的「False Success Rate 0/32」**是空的**。

更基础的是：CLI **根本没有传入声明的参数**，
所以任何批量运行都物理上无法记录声明。

### 改了什么

| 项 | 改动 |
| --- | --- |
| 默认值 | `False` → **`None`**（显式未知，不再伪装成测量值） |
| 新增字段 | `agent_claim_source`: `absent` \| `measured` |
| CLI | 新增 `--agent-claim <true\|false>` 入口 |

### 为什么这不改变尺子

`benchmark/tests/test_claim_does_not_affect_grading.py` 证明：
对 **true / false / 缺失** 三种声明，
`passed`、子句名称、子句 `ok` 标记**完全一致**；
只有 `false_success` / `false_failure` 这两个派生布尔变化。

### 证据

- `setup/acceptance/evobot_assess_v4_20261111/`：v1..v4 四版自评对比，
  false success 1/32 → 0/32，且准确率 62.5% → 87.5%；
- `setup/acceptance/evobot_honesty_retraction_20261111/`：撤回空零的完整记录。

### 回滚

`git revert` 该提交；默认值恢复为 `False`，`--agent-claim` 消失。
注意：回滚会让 false-success 指标**重新变回不可测量**。

---

## 2026-11-11 — `benchmark/generators/unseen_tasks.py`

### 为什么改

此前的留出集只变**世界**，不变**要求的结构**：T12 要重复路线，T13 要几何条件判断，
两者都可以在不思考「先做哪个」的情况下通过。
为了测真正的跨类型泛化，新增模板 **`T14_ordered_pair`**：顺序成为目标的一部分。

### 改了什么

| 项 | 内容 |
| --- | --- |
| 新增函数 | `t14_ordered_pair()` |
| 注册 | `TEMPLATES["T14_ordered_pair"]` |
| 现有模板 | **一行未动** |

### 为什么不改变尺子（已实测证明）

重新生成 20 个既有实例（T12/T13，跨 5 个留出集）并与磁盘上的公开 spec 比对：

| 字段 | 结果 |
| --- | --- |
| `instruction` | 完全一致 |
| `objects` | 完全一致 |
| `zones` | 完全一致 |
| `execution_budget` | 完全一致 |
| `split` | 完全一致 |
| `constraints` | **公开侧为 `null`**——封存剥离（`order` 属答案） |

**除被封存剥离的字段外，零差异。既有实例与既有数字全部仍然成立。**

### 验收器

**未改。** `order` 子句早已存在，从 `move_sequence` 判分。

### 证据

`setup/acceptance/evobot_crosstype_20261111/`：16 例新实例，
规划层顺序合规 16/16、执行层 14/16、**真正颠倒 0**、R 16/16。

### 回滚

删除 `t14_ordered_pair` 与 `TEMPLATES` 中的注册行；
既有模板与封存集不受影响（已封存实例是磁盘文件）。
