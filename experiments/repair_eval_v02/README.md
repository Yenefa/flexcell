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

## 运行记录对表：DATA_DICTIONARY §3.3–§3.6

驱动脚本产出的东西以前只是“接近”声明的 schema。把三份字段表逐条对了一遍，发现**四处不一致**：

| # | 不一致 | 谁对 |
| --- | --- | --- |
| 1 | `budget_exhausted_at` 我输出的是 dict | 文档要 string（`interaction:7`） |
| 2 | `final_scenes` 完全没有 | 文档必填 |
| 3 | C 条件的 `feedback_source` 策略里叫 `mismatch_run`，记录里叫 `donor_run` | 两套词表，需要显式映射 |
| 4 | D 条件策略里是 `own_run` + guidance，记录里要求一个值 `own_run_plus_guidance` | 同上 |

### 词表映射写进代码，不静默转换

```
policy feedback_source      记录 feedback_source
none                    ->  none                   (A)
own_run  + no guidance  ->  own_run                (B)
mismatch_run            ->  donor_run              (C)
own_run  + guidance     ->  own_run_plus_guidance  (D)
```

`POLICY_TO_RECORD` 是唯一真源，四条臂各有用例；出现未映射的词表值一律 `RecordError`，**不透传**。

### 文档是 schema 的唯一真源

`test_run_record.py` 直接**解析 `DATA_DICTIONARY.md` 的表格**，而不是在测试里重抄一遍：

- 文档加字段 → 测试红，直到代码跟上；
- 代码发明文档没写的字段 → 测试红（双向检查）；
- 只要求 `必填 = 是` 的字段存在，`notes` 这种可选字段不强制。

### 一个诚实的更正

上一轮我报“24 槽全部 ACCEPT”。接上真实 schema 后，同样的 24 槽产出的是：

```
terminal_states: {UNKNOWN: 22, BUDGET_EXHAUSTED: 2}
```

原因：`SUCCESS_VERIFIED` 要求 **G1–G4 全通过**，而试运行没有跑独立验收（保留场景），
`gate_independent` 是 `NOT_RUN`。没有任何一道门失败，但也没有验证——那就是 `UNKNOWN`，
不是成功。

**“24/24 ACCEPT”是契约层的裁决，不是运行记录的终态**。混用会让一份没验证过的运行看起来像成功的。
这条也顺带说明了为什么要把记录接到真 schema 上：自造的字段名看起来更好看，但它不在词表里。

### `false_accept` 由代码推导，不允许调用方声明

§3.5 定义是“声称成功但 G1–G4 未全通过”。实现按字面：

- 认作“全通过”要求 `gate_target` / `gate_contract` / `gate_independent` 都是 `PASS`，且每个保留场景都是 `PASS`；
- **`NOT_RUN` 算作“未通过”**——没跑过的门不算通过，否则一次没测量的运行会被算成真阳性；
- `false_reject` 永远不由代码推断（文档要求人工复核后才可置 true）。

## 清单对账：手写表与真记录（`reconcile.py`）

`RUN_MANIFEST.md` §1 是手写的 24 行表，表头自称「状态列是权威计数」。**此前没有任何东西核对它和记录是否一致**——现有自检只断言「24 行全是 `NOT_RUN`」，那只能证明本包没执行过，看不出表和旁边的记录对不上。

### 三种漂移，两个方向

| 漂移 | 后果 |
| --- | --- |
| 槽位标了终态但没有记录 | 一个没有底账的声明 |
| 记录到了终态但表还写 `NOT_RUN` | 做了却没被计入 |
| **试运行记录提升了槽位** | 从「没跑过」到「跑过」的痕迹被抹掉 |

第三条是这里最危险的，所以单独处理：任何 `qualification` 含 `DRY_RUN` / `SCRIPTED` 的记录**一律排除**，并在报告里列出（不静默丢弃）。

```
$ reconcile.py --manifest RUN_MANIFEST.md
manifest slots   : 24
records read     : 0
excluded non-real: 0
verdict          : CONSISTENT

$ reconcile.py --manifest RUN_MANIFEST.md \
      --records evidence/budget_matrix.json
manifest slots   : 24
records read     : 24
excluded non-real: 24      <- 24 条矩阵记录一条都没能提升槽位
verdict          : CONSISTENT
```

### 结构上直接拒绝（不是记一条警告）

- 记录指向表里没有的槽位；
- 同一槽位两条**真**记录（补跑应新增 `.re2` 行，不是盖在同一条上）；
- 记录的状态不在 §4 词表内；
- 表里出现词表外的状态。

### 变异验证

| 变异 | 结果 |
| --- | --- |
| 试运行当真实记录 | KILLED (4 failed) |
| 忽略「有终态无记录」 | KILLED |
| 放行表外槽位 | KILLED |
| 解析器接受任意状态 | KILLED |
| 允许同槽位两条记录 | KILLED |

15 条用例，5 个变异全部被杀。其中 4 条用例专门盯「试运行不得提升槽位」。
## 接缝测试：从散文变成用例（`test_seam.py`）

`INTEGRATION_SEAM.md`（#254）当时写了四条实测结论，并留了一句：探针**不进仓库**，因为依赖两个尚未合并的分支；等 #257 与 #258 合并后应变成测试。

这条分支就是三者汇合的地方，所以那四句话现在有测试了：

| 断言 | 机制 |
| --- | --- |
| A 读裁决 → `reserved_name`，读候选源码 → 允许 | 拒绝是机制不是提示 |
| 候选目录里留了裁决 → `StaleArtifact` | 新运行不继承旧反馈 |
| 翻转 `claim_success` → `status` 与 `codes` 都不变 | 记录但不采信 |
| 目标改到容差外再声称成功 → `REJECT / GOAL_NOT_MET` | 自述救不回没达成的目标 |

另加两条身份断言：一条记录必须能同时写下 `policy_id` / `policy_fingerprint` / `condition` / `contract.sha256()` / `contract.version`；并且**策略内容一改指纹就变**（否则「记录了指纹」证明不了任何事——规则可以在名字不动的情况下被换掉）。

### 变异验证

| 变异 | 结果 |
| --- | --- |
| 让候选的自述决定裁决 | KILLED (2 failed) |
| 指纹变成常量 | KILLED |
| 放行读裁决 | KILLED |

前两个变异第一次跑时**显示 SURVIVED**，查下来是我的变异脚本替换锚点没命中、文件根本没被改——**一个静默无效的检查**，正是我这几轮一直在挑的那类毛病。加了「替换没有实际改变文件就判 INVALID」之后，三条全部 KILLED。