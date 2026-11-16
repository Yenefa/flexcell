# DATA_DICTIONARY — 字段定义、单位与分母口径（v0.1 草案）

> **状态：DRAFT v0.1。未冻结。未执行。**
> 本文档只定义「怎么数」。它不包含任何数值结果，也不定义任何阈值。
> 阈值归 [TASKS.md](TASKS.md) §6 与冻结评估器，#250 契约归 [TASKS.md](TASKS.md) §5。

## 1. 三种计数对象（先分清，否则所有比例都错）

| 计数对象 | 定义 | 一条的边界 | 单位 |
| --- | --- | --- | --- |
| **修复记录**（repair record） | 某 `slot_id` 的一次完整「派发 → 终态」 | 从发出第一份信息包开始，到写入终态为止 | 条 |
| **候选执行**（candidate execution） | 在仿真里**启动并跑完**某个场景（目标或保留）的一次动作 | 一次场景进程从 launch 到结束 = 1 次；同一场景重复 N 次 = N 次 | 次 |
| **最终场景**（final scene） | 终态确定后，由独立验收重跑的**一轮**最终判定 | 一轮内可含多个场景与多道门，但仍只算 **1** 个最终场景 | 个 |

**关键区分**：一条修复记录可以触发很多次候选执行，但只产生 **1** 个最终场景，
且只在修复记录层计 **1** 条。把「候选执行」和「修复记录」混计会让成功率高估或低估，
所以下文所有比例都**显式写出分母是哪一个**。

## 2. 什么算一条记录 / 什么不算

| 情形 | 算记录吗 | 理由 |
| --- | --- | --- |
| 派发了一个槽位，跑完得到明确终态 | **算**，1 条 | 正常路径 |
| 派发后因 S1（未确认动作终态）停下 | **算**，终态 `UNKNOWN` | 发生了派发与消耗，必须进账 |
| 派发后因 S2（环境不健康）停下 | **算**，终态 `INVALID` | 记下来，但不进分母 |
| 条件 A 读到了结果类信息 | **算**，终态 `INVALID` | 信息边界失守，不能当有效样本 |
| 达 6 次交互 / 20,000 tokens 上限 | **算**，终态 `BUDGET_EXHAUSTED` | 预算是协议的一部分，耗尽也是结果 |
| 同一 slot 因协议偏差重跑一次 | **算两条**（原行 + `.re2`） | 不覆盖，不合并 |
| 预跑/探测（不进入 24 槽） | **不算**，标 `PROBE` | 探测不参与统计 |
| 人工手动跑一遍以验证环境 | **不算**，标 `ADMISSION_CHECK` | 环境验证不是修复记录 |
| 历史 W5/E2 的任何一次运行 | **不算**，不进入任何 v0.2 分母 | 身份不同，不可合池 |
| 只跑了候选执行、没跑最终场景（中途停） | **算**记录，但最终场景数 = 0 | 记录在，最终场景缺席 |
| 评估器自身报错导致无判定 | **算**，`INVALID` | 不是修复失败 |

## 3. 字段表

### 3.1 身份与归属

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `run_id` | string | — | 本记录唯一 ID，计划格式 `RC-<slot_id>-<yyyymmdd>-<nn>` | 是 |
| `slot_id` | string | — | 形如 `F1-A-r1`，必须存在于 [RUN_MANIFEST.md](RUN_MANIFEST.md) | 是 |
| `family` | enum | — | `F1` / `F2` | 是 |
| `condition` | enum | — | `A` / `B` / `C` / `D` | 是 |
| `repetition` | int | — | 1 / 2 / 3 | 是 |
| `seed` | int | — | 任务实例 seed，与同 `(family, repetition)` 的其它条件相同 | 是 |
| `contract_version` | string | — | #250 契约版本（计划接口） | 是 |
| `protocol_version` | string | — | 本协议的版本，如 `v0.1` | 是 |

### 3.2 身份冻结面（防篡改）

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `code_sha` | string | — | 执行所用源码完整 SHA（40 位），不用短 SHA | 是 |
| `evaluator_sha256` | string | — | `benchmark/evaluators/evaluate.py` 的 sha256 | 是 |
| `task_spec_sha256` | string | — | 该 seed 的冻结 task spec sha256 | 是 |
| `protected_paths_digest` | string | — | 保护文件清单的聚合摘要 | 是 |
| `injection_sha256` | string | — | 缺陷注入文件（覆盖/补丁）的 sha256 | 是 |

### 3.3 信息供给面（条件差异的记录）

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `feedback_source` | enum | — | `none`（A）/ `own_run`（B）/ `donor_run`（C）/ `own_run_plus_guidance`（D） | 是 |
| `feedback_payload_sha256` | string | — | 实际下发信息包的摘要 | 是 |
| `guidance_sha256` | string | — | D 条件显式指导文本的摘要；A/B/C 为 `null` | 是 |
| `donor_run_id` | string | — | C 条件的 donor 记录 ID；其它条件为 `null` | 是 |
| `visibility_policy_id` | string | — | #249 可见性策略的版本标识（计划接口） | 是 |

> **摘要口径（DRAFT-FIXED）**：本表所有 `*_sha256` 字段一律按
> `utf8-lf-sha256/1` 计算：按 UTF-8 解码 → 把 CRLF 与单独的 CR 归一为 LF →
> 再按 UTF-8 编码 → sha256。
>
> 为什么必须写死：不归一化时，同一份反馈在 Windows 与 Linux 上会得到不同摘要
> （实测 `e9024f1a` 与 `6612d9c9`），于是两条本应可比的记录变成两个不可比的数字。
> 归一化针对的是**平台写出的换行**，不是内容本身。
>
> **字节级证据不走这条口径**：归档成员、二进制、按其确切字节计量的文件用
> `sha256_bytes`（不归一化）。对字节做归一化会改变被测量的东西。

### 3.4 预算账本

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `interactions_used` | int | 次 | 已用模型交互次数（一次请求-响应 = 1） | 是 |
| `interactions_cap` | int | 次 | 固定 6 | 是 |
| `tokens_in` | int | token | 输入 token，按提供方 usage | 是 |
| `tokens_out` | int | token | 输出 token | 是 |
| `tokens_total` | int | token | `tokens_in + tokens_out` | 是 |
| `tokens_cap` | int | token | 固定 20,000 | 是 |
| `tokens_source` | enum | — | `provider_split` 或 `provider_total_only`；后者表示提供方只给了总数，`tokens_in`/`tokens_out` 记 `null` | 是 |
| `task_variant` | enum | — | `v1` 或 `v2`；v1 的题面写出要注册的物体名与期望配对，v2 只写症状、名字改由执行反馈给出。两批不得混池：v2 下无反馈条件按设计拿不到名字。 | 是 |
| `candidate_executions` | int | 次 | 本记录触发的场景执行次数（见 §1） | 是 |
| `final_scenes` | int | 个 | 本记录产生的最终场景轮数（0 或 1） | 是 |
| `wall_clock_s` | float | 秒 | 从派发到终态 | 是 |
| `budget_exhausted_at` | string | — | 如 `interaction:7` / `token:20013`；未耗尽为 `null` | 是 |

> **截断**：`interactions_used` 等于该批的交互上限时，该观测是**截断值**，不是「用完了」。`summarise.py` 把「耗尽」与「顶在上限」分开计数，并在整格全顶时标注该行描述的是天花板而非工作量。

### 3.5 判定面

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `terminal_status` | enum | — | [RUN_MANIFEST.md](RUN_MANIFEST.md) §4 的词表之一 | 是 |
| `gate_target` | enum | — | `PASS` / `FAIL` / `NOT_RUN`（G1） | 是 |
| `gate_regression` | map | — | 每个保留场景 ID → `PASS`/`FAIL`/`NOT_RUN`（G2） | 是 |
| `gate_contract` | enum | — | `PASS` / `FAIL`（G3，计划接口） | 是 |
| `gate_contract_codes` | list | — | 契约拒绝理由码（[TASKS.md](TASKS.md) §5.1） | 是 |
| `gate_independent` | enum | — | `PASS` / `FAIL` / `NOT_RUN`（G4） | 是 |
| `claim_success` | bool | — | 修复者**是否声称**成功；只用于算错误接纳，**不参与判定** | 是 |
| `false_accept` | bool | — | 声称成功但 G1–G4 未全通过 | 是 |
| `false_reject` | bool | — | 实际达成目标但被某道门拒（需人工复核后才置 true） | 是 |

### 3.6 过程与偏差

| 字段 | 类型 | 单位 | 说明 | 必填 |
| --- | --- | --- | --- | --- |
| `edited_paths` | list | — | 实际被修改的文件路径 | 是 |
| `first_edit_after_execution` | bool | — | 是否「先观测到失败、后编辑」（防事后编造） | 是 |
| `deviation_codes` | list | — | [PROTOCOL.md](PROTOCOL.md) §8.1 的码 | 是 |
| `evidence_path` | string | — | 运行记录目录（相对仓库根） | 是 |
| `notes` | string | — | 自由文本，不得写入结论性判断 | 否 |

## 4. 分母口径（不重复计数）

设 `R` 为某 `(family, condition)` 下全部修复记录集合。

| 记号 | 定义 | 用途 |
| --- | --- | --- |
| **D1** 修复运行数（可判定） | `|{r ∈ R : terminal_status ∈ {SUCCESS_VERIFIED, FAIL, BUDGET_EXHAUSTED}}|` | **主指标分母** |
| **D1'** 修复运行数（全派发） | `D1 + |{r ∈ R : terminal_status = UNKNOWN}|` | 辅助：展示不确定性规模 |
| **D2** 候选执行数 | `Σ candidate_executions over r ∈ D1` | 执行层辅助指标分母 |
| **D3** 最终场景数 | `Σ final_scenes over r ∈ D1` | 独立验收层分母 |
| **N1** 未派发 | `|{r : r 未派发}|` = manifest 里 `NOT_RUN` 数 | 覆盖度指标 |
| **N2** 证据无效 | `|{r : INVALID}|` | 质量指标；**不进 D1/D1'/D2/D3** |

### 4.1 主指标

```
自主修复成功率(族, 条件) = |{r ∈ R : terminal_status = SUCCESS_VERIFIED}| / D1
```

- 分子只数 `SUCCESS_VERIFIED`；`FAIL`、`BUDGET_EXHAUSTED` 在分母里但不进分子；
- `UNKNOWN` 与 `INVALID` **不进 D1**；`UNKNOWN` 另按 D1' 报一次，`INVALID` 单列；
- 一个 (族, 条件) 格只有 3 条记录 → 比例写作 `x/3`，同时给出原始计数，不写百分数。

### 4.2 不重复计数的九条规则（DRAFT-FIXED）

1. 一条修复记录只在它自己的 `(family, condition)` 里计 **1** 次，不跨格累计。
2. 一条记录内的多次候选执行**不**产生额外记录，也不各自进成功率分子。
3. 一次最终场景里的多道门、多个保留场景**不**算多个最终场景。
4. 保留场景失败**不**新增记录，只把该记录终态改成 `FAIL`（G2）。
5. 重跑行（`.re2`）独立计数，与原行**不合并**、不平均。
6. 探测运行（`PROBE`）与准入验证（`ADMISSION_CHECK`）不进任何分母。
7. 历史 W5/E2 记录不进任何 v0.2 分母，也不作为分子。
8. `INVALID` 记录既不做分子也不做分母，但**必须**在表里出现（否则是选择性报告）。
9. 同一记录的不同指标（交互数、token、错误接纳）各自按自己的分母算，**不**互相复用。

### 4.3 单位约定

| 量 | 单位 | 精度 |
| --- | --- | --- |
| 距离 | 米（m） | 评估器输出为准，报告保留 3–5 位小数 |
| 时间 | 秒（s） | 整数秒；预算墙钟用 float |
| token | 个 | 按提供方 usage，四舍五入到整数 |
| 费用 | 币种 `TBD` | 按批次额度单位（[PROTOCOL.md](PROTOCOL.md) §5.3） |
| 计数 | 条 / 次 / 个 | 整数，不给小数 |

## 5. 允许与拒绝的例子（记录层）

| 情形 | 判定 | 理由 |
| --- | --- | --- |
| 一条记录跑了 4 次候选执行、1 次最终场景、最终 PASS | `candidate_executions=4`、`final_scenes=1`、计 **1** 条记录 | §4.2 规则 2、3 |
| 同一条记录把「4 次候选执行」当成 4 条记录写进表 | **拒绝** | 分母膨胀 |
| 只统计 PASS 的记录，`INVALID` 从表里删掉 | **拒绝** | §4.2 规则 8 |
| 把历史 E2e 的 `3/3` 加进 v0.2 F1-B 的分子 | **拒绝** | §4.2 规则 7 |
| 把 `.re2` 重跑与原行取平均 | **拒绝** | §4.2 规则 5 |
| 记录 `UNKNOWN` 并同时报 D1 与 D1' | **允许** | §4 |
| 用 `claim_success` 参与成功判定 | **拒绝** | 判定归冻结评估器；该字段只用于错误接纳 |

## 6. 已知限制

- 字段清单是**计划**：实际运行记录 schema 由 #252 落成，落成后若与本表不符，以**本表的口径**为准，
  差异回写到本表并升版本。
- `tokens_in` / `tokens_out` 的统计口径依赖提供方 usage。若提供方不给分项，两者记 `null`、`tokens_source` 记 `provider_total_only`，
  **不得**由 `tokens_total` 反推分项。`null` 表示「提供方没给」，与 `0` 不是一回事。
- `false_reject` 需要人工复核才可靠，可能被低估；报告时必须说明复核方法。
- `final_scenes` 上限为 1，但允许为 0（中途停止）；为 0 的记录不计入 D3。
