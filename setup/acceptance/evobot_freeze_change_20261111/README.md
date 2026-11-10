# 补上最后一个诚实缺陷：声明根本没有传入入口

## 上轮留下的问题

> `observe_from_run` 的 `agent_claimed_success=False` 默认值仍在。

这轮走了正式变更流程。

## 缺陷比「默认值不合适」更基础

```
def build_observation(run_dir, declared_objects, agent_claimed_success=False, ...)
```

**CLI 里根本没有 `--agent-claim` 参数。**
任何批量运行都**物理上无法**把声明传进去——不只是默认值问题，是**入口不存在**。

## 改了什么

| 项 | 前 | 后 |
| --- | --- | --- |
| 默认值 | `False` | **`None`**（显式未知） |
| 新字段 | 无 | `agent_claim_source`: `absent` / `measured` |
| CLI | 无 | **`--agent-claim true|false`** |

## 前提：证明不改变尺子

这是修改固定文件，必须先证明判分不变。做法是**精确隔离那一个字段**：

| 断言 | 内容 |
| --- | --- |
| 三种声明值下 | `passed`、子句名、子句 `ok` **完全一致** |
| 缺失 vs `False` | 判分**完全一致** |
| 只有派生布尔变化 | `false_success` 变时 `passed` 不变 |
| 记录现实 | `None` 与 `False` 在 evaluator 眼里不可区分 |

最后一条正是缺陷根源：**所以 harness 绝不能依赖那个默认值代表「已测量」**。

## 冻结机制真的拦住了我

改完固定文件后测试立刻失败：

```
AssertionError: ['pinned file CHANGED: benchmark/evaluators/observe_from_run.py']
```

## 但重新冻结原来是免费的——这是真实漏洞

原实现可直接再跑一次 `freeze_baseline.py` 覆盖基线，那样所有漂移检查都变成装饰品。

已加变更管控：`changed_pinned()` 发现有变化且 changelog 未登记就 `SystemExit`。

实测：

```
REFUSING to re-freeze: these pinned files changed with no entry in
docs/FREEZE_CHANGELOG.md: ['benchmark/evaluators/observe_from_run.py']
```

登记变更日志（为什么改、改了什么、为何不改变尺子、如何回滚）后才允许冻结，
并把变更写进基线自身的 `changes_since_previous`。

## 一个我差点漏过的错误

插入字典项时**漏了一个逗号**，`py_compile` 失败但我没看输出；
是测试收集阶段报 `SyntaxError` 才暴露。

## 状态

| 项 | 值 |
| --- | --- |
| 离线测试 | **181 passed** |
| 冻结基线 | **INTACT**（已正式变更并记录） |
| 封存 | `BLOCKED_GOOD` |
| 验收器 `evaluate.py` | **未改** |
| 改动的固定文件 | **1 个**，有变更日志与回滚说明 |

## 现在整条链是通的

```
自评产生声明 → --agent-claim 传入观测 → evaluator 计算 false_success
     ↑                                              ↓
  max_tokens 必须够（8192+）              honesty_guard 拒绝空零
```

每一环都有测试，且每一环都被实测打回过一次。
