# #252 对照矩阵：机制试运行（DRY RUN）

> **状态：DRY RUN —— 没有任何模型参与，不是能力结果，不得进入任何分母。**
> 本目录证明的是"24 槽矩阵、条件路由、可见性边界、契约判定、新鲜度门能够端到端串起来"，
> 不证明任何关于模型能力的结论。

## 为什么先做这一步

本机**没有模型凭据**，实测三处全部为空：

| 来源 | 结果 |
| --- | --- |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `FLEXCELL_PILOT_API_KEY` | 全部 unset |
| gate 脚本 `/mnt/c/Users/fuker/.../evobot_llm_key.sh` | 路径不存在 |
| `~/.config/flexcell/pilot.env` | 不存在 |
| Windows 注册表 `HKCU` / `HKLM` 的 `FLEXCELL_PILOT_API_KEY` | 均未设置 |

在拿不到 key 的情况下，选择是：把 24 槽标成 NOT_RUN 等授权，或者用仓库自带的 `ScriptedAgent`
把**同一套 24 槽、同一个适配器**跑一遍。选后者，理由是本仓库已经吃过两次同样的教训——
**一条从未端到端执行过的流水线不是流水线，是计划**。如果第一次端到端跑发生在有真模型的那天，
harness 的每个 bug 都会静默变成"能力结果"。

事实证明这个判断是对的：这次试运行抓出了 **4 个缺陷**，其中 2 个会让整个矩阵静默归零。

## 试运行抓到的缺陷

| # | 缺陷 | 后果 | 归属 |
| --- | --- | --- | --- |
| 1 | `CANDIDATE_SCHEMA` 是死常量，从未被读 | 别的 harness 的报告被判 ACCEPT | #250，已修 `7c19876` |
| 2 | 身份回显被硬 REJECT | 每条运行都 REJECT（假失败污染） | #250，已修 `721b31e` |
| 3 | 物体名叫 `target`/`goal`/`version` 被判"篡改不可变字段" | **24/24 静默 REJECT** | #250，已修 `16e7ca5` |
| 4 | `editable_fields` 写目录形式授权不了任何文件 | **24/24 静默 REJECT** | #250，已修 `16e7ca5` |

第 3、4 条是这次试运行的直接产出：它们不会让任何一条现有测试变红（7 例语料用的是
`block_a`、且 `editable_fields` 用的是文件形式），只有把 24 槽真跑一遍才会暴露。

## 试运行结果

`
python3 experiments/repair_eval_v02/dry_run_matrix.py
`

| 项 | 值 |
| --- | --- |
| 槽位 | 24 / 24（2 族 × 4 条件 × 3 次） |
| 状态 | 24 `DRY_RUN_COMPLETE` |
| 裁决 | 24 `ACCEPT`，`codes` 全空 |
| 可见性一致性 | 24/24 的 `gate/` 为 `sealed_material` |
| `policy_fingerprint` | `a48651c0…` |

### 这个结果不能说明什么（重要）

**4 个条件全部 6/6 ACCEPT，是因为 agent 是固定脚本**——它在每个条件下都执行同一个已知修复。
所以这份记录**不能**用来比较条件之间谁更好，也**不能**说"反馈没用"。要回答那个问题必须有真模型，
因为只有模型的行为才会随信息供给变化。

它证明的是**机制**：条件路由确实给了不同信息（见下表），判定确实按契约执行，门确实把评估器封印了。

| 条件 | 反馈通道实际返回 |
| --- | --- |
| A_STATIC | `policy_denied`（拿不到，符合协议） |
| B_REAL_FEEDBACK | `missing_material`（本试运行没有真运行产物） |
| C_MISMATCHED_FEEDBACK | `present`（从固定 donor 取，符合协议） |
| D_GUIDED | `missing_material` + 指导文本 |

B 和 D 返回 `missing_material` 不是缺陷：试运行没有"上一条真实执行"可供回放。真跑时这里应当是
本 run 的执行日志。

## 复现

`
git checkout codex/evobot-paper-v02-control-runs
python3 experiments/repair_eval_v02/dry_run_matrix.py | head -40
`

输出里每行都带 `"qualification": "DRY_RUN"`，汇总里带
`"qualification": "DRY_RUN_SCRIPTED_AGENT_NOT_A_MODEL_RESULT"`。

## 真跑还缺什么

| 项 | 状态 |
| --- | --- |
| 模型凭据（gate 脚本或 env 文件） | **缺** |
| 执行源码 40 位 SHA 冻结 | 缺（分支仍是候选） |
| 镜像 digest、模型 id、提示 sha256 | 缺 |
| `seed` 与 C 的 donor 绑定 | 缺（协议标 TBD） |
| 运行窗口与串行约定 | 缺 |

在这些补齐之前，本目录的记录保持 `DRY_RUN`，不计入 `ADMISSION.md` 的任何一项。

## 预算层：协议 5.1 第一次被执行

上表那份 DRY RUN 用的是固定脚本 agent，**从不花 token**，所以 5.1 的三条规则
（6 次交互上限、20,000 token 上限、BUDGET_EXHAUSTED 不计成功）在整个仓库里
**没有一行代码在执行**。一条只存在于文档里的上限不是上限。

本目录新增：

| 文件 | 作用 |
| --- | --- |
| `budget.py` | `Ledger`：唯一能到达模型的入口。**调用前**检查交互与 token 上限（会超的那次调用根本不发出，不花钱）；token 只能在调用后知道，所以调用后再查一次。任一上限触发即**永久关闭**账本（5.1 禁止“再给一次机会”） |
| `agent.py` | `RepairAgent`：从可见性边界**拼提示词**，且只通过 `ToolFacade` 写文件，所以评估器、裁决、隐藏答案都读不到 |
| `test_budget.py` | 23 条用例，逐条对应 5.1 / 5.2 |
| `budget_matrix.py` | 24 槽全部走真实 repair loop + 真实账本 |

### 24 槽账本结果

```
terminal_states: {DONE: 22, BUDGET_EXHAUSTED: 2}
counted_in_denominator: 22
excluded_budget_exhausted: 2
every_row_has_full_account: true
no_row_exceeds_cap: true
qualification: SCRIPTED_TRANSPORT_NOT_A_MODEL_RESULT
```

两槽（`r3` 的 `D_GUIDED`）**故意烧掉预算**，用真实矩阵行证明“耗尽不计入分母”，
而不是只在单元测试里成立。

### 变异验证（用例能失败）

删掉规则看用例是否变红——5 条全部被杀：

| 变异 | 结果 |
| --- | --- |
| 去掉调用前的交互检查 | 5 failed |
| 耗尽不再压过成功声明 | 2 failed |
| 调用后不查 token 上限 | 1 failed |
| 关闭的账本允许再试一次 | 1 failed |
| 循环停在 cap（旧写法） | 1 failed |

第 4 条一开始**没被杀掉**（22 passed）。原因是“不可追加”此前只经过交互检查那条路，
而它自己也会拒绝。补了一条“因执行次数关闭的账本，即使交互与 token 都还空着也必须拒绝
新调用”之后才杀死。这条用例缺口是变异测试自己发现的。

### 顺带抓到的两个真 bug

1. **循环停在 cap 时永远发现不了耗尽**：`range(max_interactions)` 用完就正常退出，
   账本没有机会拒绝，于是“用光次数但没完成”被记成 `INVALID`（像是放弃），而不是
   `BUDGET_EXHAUSTED`（如实记录耗尽）。改成循环上界 `cap+1`——多出来的那次在到达
   transport 之前就被拒，因此**发现耗尽不花钱**。
2. **`_feedback()` 吞异常**：原本 `except Exception: return ""`，会把“策略拒绝”和
   “harness 坏了”混成同一个结果，让坏掉的运行看起来像一次正常的 A 条件运行。现在只对
   `policy_denied` 返回空，其它异常照抛。

### 新鲜度门的正确用法

第一版夹具把 `candidate/telemetry` 写在 `assert_fresh_run()` 之前，被 `StaleArtifact` 拒了。
这不是 bug——门的本意就是“新 run 不得继承上一轮的反馈”。正确顺序是：
断言新鲜 → 执行产出 telemetry → agent 读反馈。已在代码注释里写明。

## 保留场景门（#253）：把"不许偷看"变成机制

#253 的候选依赖 #252 的真跑，**无法执行**。但其中有一条纪律是可以离线固化的：

> 固定候选源码 SHA……选择过程不得查看保留场景结果。

写成承诺就不可验证——等你能证明偷看时，数字已经进论文了。`holdout.py` 把它变成代码：

| 规则 | 机制 |
| --- | --- |
| 候选必须先冻结 | `HoldoutPlan` 构造需要 `Freeze`，不给就抛 |
| 评估的就是冻结的那个 | `assert_frozen()` 每次执行前比对 SHA |
| **结果不能早于冻结** | `record()` 比较 `frozen_at`，结果时间戳早于冻结即拒 |
| 失败不能被改写 | 槽位一次写入，第二次抛，`FAIL` 保留原身份 |
| 修复数与保留执行数分开报 | `counts()` 分别给 `repair_runs` / `holdout_executions` |

第三条是关键：**冻结时间晚于某条结果**，意味着被冻结的候选可能是照着那条结果挑的，
再怎么解释都救不回来。

### 变异验证

| 变异 | 结果 |
| --- | --- |
| 允许结果早于冻结 | KILLED |
| 允许改写已有结果 | KILLED |
| 放行任意候选 SHA | KILLED |
| 无冻结也能建计划 | KILLED |
| 逐槽不校验 SHA | KILLED |

15 条用例，5 个变异全部被杀。

### 它不做什么

它**不能**阻止人绕开代码去读保留答案，也不假装能。它只关掉会留下痕迹的两条路：
事后补一个冻结时间、或结果公布后换掉候选。这条限制写在模块 docstring 里。
