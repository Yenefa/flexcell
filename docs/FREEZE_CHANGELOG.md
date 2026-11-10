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

