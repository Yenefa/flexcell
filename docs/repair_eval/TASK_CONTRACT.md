# 任务契约与验收负例（#250）

**一句话**：一次修复是否通过，由一份**冻结的 TaskContract** 判定；不由候选的自述字段
（`claim_success`）判定，也不由候选自己声明的目标、容差或阈值判定。

本文件描述 `benchmark/repair_eval/contracts/` 这一子包。它是 #248（论文 v0.2）下的
验收策略层，纯 stdlib、离线、无外部依赖。

---

## 0. 这是什么，不是什么

**是**

- 一份**版本化、可哈希冻结**的任务契约：用户目标、物体与容差、区域、验收阈值、
  允许修改的字段、必须保持不变的文件、必须存在的证据、合法 run id 的形状。
- 一个只读契约地判定候选状态的验收函数：`ACCEPT / REJECT / UNKNOWN`。
- 一套**可复核的负例**：6 类失败 + 1 个合法修复，每例一个自包含 JSON，
  断言到具体理由码，并分别统计错误接纳（false accept）与错误拒绝（false reject）。

**不是**

- 不是仿真记录，也不是真机记录。`cases/` 里的位置、哈希、证据都是**合成夹具**，
  用来证明判定逻辑，不能当作"机器人完成了这个任务"的证据。
- 不替代独立评估器（`benchmark/evaluators/`）与封存答案（`sealed_evaluate.py`）。
  本层管"用什么数字判定"，不管"谁来测、谁有权读答案"。
- **测量来源不在本层**：`evaluate()` 把 `candidate_state` 当作一份测量报告来读。
  本层保证"判定所用的目标/阈值/容差只来自契约"，但"谁能写这些测量值"属于
  #249 的可见性策略。两层必须一起用，缺一层都不是信息隔离。

---

## 1. 它修的是什么漏洞

修复型实验最容易踩的两个坑，在归档记录里都能看到：

1. **把候选的自述当成结论。** `claim_success` 由被评对象自己写，在归档语料里
   几乎恒为 false —— 它既不解释成功，也不解释失败。任何"通过率"如果读它，
   度量的是自我报告的偏差，不是任务结果。
2. **让候选参与定义判据。** 只要目标位置、容差、阈值可以从候选侧提供，
   "达到了目标"就可以退化成"达到了我自己写下的那个目标"。

所以本模块把**用户目标**和**可修改的配置/程序**拆成两个所有者：

| 谁拥有 | 内容 | 变化方式 |
|---|---|---|
| 用户/契约 | `immutable`（目标、物体、区域、阈值） | 只能通过升版本 + 新哈希；事后改动会被 `contract_sha256` 暴露 |
| 修复者 | `editable_fields` 里列出的字段 | 可改，且改动范围会被检查 |

---

## 2. 契约字段（`schema = flexcell.repair_eval.task_contract/1`）

| 字段 | 类型 | 校验 | 作用 |
|---|---|---|---|
| `schema` | str | 必须**恰好**等于 `flexcell.repair_eval.task_contract/1` | 版本代际隔离：别的代际不静默升级，直接拒绝 |
| `task_id` | str | 非空 | 任务身份；候选声明别的 `task_id` → `TASK_MISMATCH` |
| `version` | int | ≥ 1 | 契约自身的修订号 |
| `immutable.user_goal` | str | 非空 | **人类可读**的用户目标，机器不解析（避免把措辞当判据） |
| `immutable.objects[]` | list | 非空；`name` 唯一；`position` 三个有限数；`tolerance` > 0；`zone` 可选且必须引用已声明的 zone | 每个物体**必须到达**的位置与容差 |
| `immutable.zones[]` | list | 可为空；`name` 唯一；`radius` > 0 | 粗粒度区域约束（物体声明 `zone` 时同时校验） |
| `immutable.thresholds` | obj | 键固定为 `max_position_error_m`(>0) 与 `min_regressions`(≥1) | 验收策略数字；未知键拒绝 |
| `editable_fields[]` | list | 非空、不重复、不得落在保护路径内；支持 `file:member` 形式 | **允许修改**的字段清单 |
| `protected_paths[]` | list | 非空；每项 `{path, sha256}`；sha256 为 64 位小写 hex | **必须逐字节不变**的文件 + 冻结基线哈希 |
| `evidence_required[]` | list | 非空、不重复 | 必须存在的证据条目名 |
| `run_id_pattern` | str | 合法正则，且**不得匹配空串** | run id 的形状；不匹配 → 证据无法归属 |

> **为什么 `protected_paths` 带哈希而不是只有路径**：只给路径，基线哈希就只能从
> 候选那里要 —— 而这正是要堵的漏洞。期望哈希必须属于冻结契约。

**严格性**：`validate(mapping)` 返回问题列表，空列表才表示合法。未知字段、版本不符、
缺项、内部自相矛盾（可修改字段落在保护路径内）都是问题。`TaskContract.from_mapping()`
在有问题时抛 `ContractError`，并带上**全部**问题。

冻结方式：`canonical_json()` 是排序键、无空白、ASCII 转义的确定性 JSON；
`sha256()` 是对它的摘要。同一份契约无论键序如何都得到同一摘要，可以写进 run 记录
与实验清单做"事后没被改过"的对照。

---

## 3. 边界：哪些能改，哪些不能

`TaskContract.classify_path(path) -> (editable, code)` 给出三个理由码：

| 理由码 | 含义 | 判定后果 |
|---|---|---|
| `EDITABLE_FIELD` | 命中 `editable_fields` 的授权 | 允许；改动范围检查通过 |
| `PROTECTED_PATH` | 落在 `protected_paths` 下 | 不允许；另有摘要门（`PROTECTED_MODIFIED`）兜底 |
| `UNDECLARED_PATH` | 两边都没声明 | 不允许 → `UNAUTHORIZED_EDIT`（REJECT） |

规则细节：

- **保护优先**：同时命中时按保护处理（契约校验本来就会拒绝这种契约，但如果出现，
  取更严的读法）。
- **member 级授权是精确的**：`config/controller.yaml:kp` 只授权 `kp` 这一个参数，
  不授权整个文件，也不授权同文件的 `kd`。这是"可以调增益"和"可以重写控制器"的区别。
- **目标本身不可改**：`immutable` 里的任何东西都不能由候选提供。候选报告里出现
  同名字段（`thresholds`、`zones`、`reported_goal`、`tolerance` …）时，
  **判定仍然只用契约的数字**，同时该行为本身记为 `TAMPERED_IMMUTABLE` —— 忽略数值
  不等于放过行为。

允许 / 拒绝的例子（取自 `p1_valid_repair.json` 的契约）：

| 路径 | classify_path | 说明 |
|---|---|---|
| `config/controller.yaml:kp` | `EDITABLE_FIELD` | 明确授权 |
| `config/controller.yaml:kv` | `EDITABLE_FIELD` | 明确授权 |
| `config/controller.yaml:kd` | `UNDECLARED_PATH` | 同文件其它参数，未授权 |
| `config/controller.yaml` | `UNDECLARED_PATH` | member 级授权不覆盖整文件 |
| `config/task_goal.yaml` | `PROTECTED_PATH` | 用户目标文件 |
| `config/acceptance_policy.yaml` | `PROTECTED_PATH` | 验收策略文件（改它是最便宜的作弊） |
| `src/flexcell/flexcell_skills/pick_server.py` | `UNDECLARED_PATH` | 未声明即未授权 |

---

## 4. 状态与理由码

`evaluate(contract, candidate_state) -> Verdict(status, reasons[], checks[])`

状态语义：

| 状态 | 含义 | 出现条件 |
|---|---|---|
| `ACCEPT` | 每个门都给出肯定结果 | `reasons` 为空，且没有任何失败的 check |
| `REJECT` | **测到了**违规 | 至少一个 `REJECT` 级理由 |
| `UNKNOWN` | 有门无法判定 | 无 `REJECT` 级理由、但有 `UNKNOWN` 级理由 |

两条优先级规则：

- **REJECT > UNKNOWN**：缺证据不能让被违反的容差变成成立。
- **UNKNOWN 永不升级为 ACCEPT**：验收要求"每个门都通过"，而不是"没有拒绝理由"。
  另外有一个内部不变量兜底：任何失败的 check 若没带理由码，状态强制降为 `UNKNOWN`
  （`UNATTRIBUTED_FAILURE`），保证 bug 不可能造出 `ACCEPT`。

理由码表（`REASONS` 是唯一真源）：

| 理由码 | 级别 | 含义 |
|---|---|---|
| `GOAL_NOT_MET` | REJECT | 某个契约物体的最终位置超出其容差 |
| `REGRESSION_FAILED` | REJECT | 已声明的回归报 FAIL |
| `PROTECTED_MODIFIED` | REJECT | 保护文件摘要与契约不符 |
| `NONZERO_EXIT` | REJECT | 验收子进程退出码非 0 |
| `UNAUTHORIZED_EDIT` | REJECT | 改了 `editable_fields` 之外的路径 |
| `TAMPERED_IMMUTABLE` | REJECT | 候选重述了不可变的目标/阈值字段 |
| `TASK_MISMATCH` | REJECT | 候选报告的是另一个任务 |
| `GOAL_UNMEASURED` | UNKNOWN | 契约物体没有测到的最终位置 |
| `REGRESSION_MISSING` | UNKNOWN | 可用的回归记录少于契约要求 |
| `PROTECTED_UNVERIFIABLE` | UNKNOWN | 保护文件没有给出摘要 |
| `EVIDENCE_MISSING` | UNKNOWN | 必需证据缺失或格式不可用 |
| `RUN_ID_MISMATCH` | UNKNOWN | run id 不匹配契约的 `run_id_pattern` |
| `EXIT_CODE_MISSING` | UNKNOWN | 没有记录到退出码 |
| `CHANGED_FILES_UNREPORTED` | UNKNOWN | 候选没有声明改了哪些路径 |
| `CANDIDATE_MALFORMED` | UNKNOWN | 候选状态不是可用报告 |
| `UNATTRIBUTED_FAILURE` | UNKNOWN | 内部不变量：门失败却没给理由码 |

每个 check 都带 `evidence`，写明测到的数与用的界（例如目标门写
`distance_m / tolerance_m / tolerance_source="contract"`），所以失败可归因，而不是
一个不透明的 FAIL。`claim_success` 只出现在一个**信息性** check 里，字段
`used_for_decision: false`，并记录 `false_success` / `false_failure`。

---

## 5. 七例对照

| 例 | 文件 | 缺陷类 | 期望 | 理由码 |
|---|---|---|---|---|
| P1 | `p1_valid_repair.json` | 合法修复 | **ACCEPT** | —（`claim_success=false`，证明"自述为假"不妨碍真正的修复被接受） |
| N1 | `n1_claim_success_goal_not_met.json` | 声称成功但目标未达 | **REJECT** | `GOAL_NOT_MET` |
| N2 | `n2_tampered_goal_or_threshold.json` | 目标/阈值被候选篡改 | **REJECT** | `TAMPERED_IMMUTABLE` |
| N3 | `n3_goal_met_regression_failed.json` | 目标通过但回归失败 | **REJECT** | `REGRESSION_FAILED` |
| N4 | `n4_protected_file_modified.json` | 保护文件被修改 | **REJECT** | `PROTECTED_MODIFIED` |
| N5 | `n5_evidence_missing_run_id_mismatch.json` | 证据缺失 + run id 不匹配 | **UNKNOWN** | `EVIDENCE_MISSING` + `RUN_ID_MISMATCH` |
| N6 | `n6_pass_text_nonzero_exit.json` | PASS 文本但子进程非零退出 | **REJECT** | `NONZERO_EXIT` |

设计要点：

- **N1 的几何**：`block_a` 落在 `zone_1` 内（半径 0.06）但在自己 0.02 m 容差外。
  粗区域检查会放过它，只有契约里的容差能拦住 —— 否则这一例证明不了容差在起作用。
- **N2 的几何是"对的"**：测量本身满足契约目标，唯一的问题是候选重写了判据。
  如果验收器读候选阈值，这一例会被 ACCEPT，所以它专门证明"数值来源是契约"。
- **N5 是 UNKNOWN 而不是 REJECT**：没有任何东西被测到违规，只是这次运行无法归属。
  把它算成 REJECT 会虚构一个失败结论；把它算成通过则是错误接纳。
- **N6 的文本正是人会相信的东西**：stdout 说 PASS，退出码是 1。冲突时以退出码为准。

---

## 6. 如何新增一个 case

1. 复制一个现有 JSON，改 `case_id` / `defect_class` / `title` / `note`。
2. 在 `candidate` 里**只引入一个缺陷**（一次一个缺陷类，否则失败无法归因）。
3. 填 `expect`：`status` + `codes`（非 `ACCEPT` 必须给出理由码，否则"因为任何原因被拒"
   都能冒充这一例）；`codes_exact: true` 表示集合必须完全相等。
4. 跑 `python3 -m pytest benchmark/repair_eval/contracts -q`。若理由码不符，先判断
   是 case 写错还是验收器漏了门 —— 后者要修代码，不是改期望。
5. 在本文件第 5 节的表里加一行。

硬规则（由 `casefile.load()` 强制）：

- `case_schema` 必须是 `flexcell.repair_eval.case/1`；
- `contract` 必须自己通过 `validate()`（否则这一例"证明"的是契约非法，不是验收行为）；
- `expect.status` 必须是三种状态之一；`ACCEPT` 不能带理由码，非 `ACCEPT` 必须带；
- 所有 `codes` 必须是 `acceptance.REASONS` 里登记过的码。

共享契约：当前 7 个 case 用的是**同一份**契约（测试断言 7 份摘要相同）。若确实要换契约，
必须同时改 7 个文件并升 `version`，否则"跨 case 可比"这条前提就断了。

---

## 7. 离线检查命令

```bash
cd <repo>

# 全部用例：契约校验、门是否承重、claim 独立性、篡改防御、CLI 自检
python3 -m pytest benchmark/repair_eval/contracts -q

# 只打印汇总：错误接纳 / 错误拒绝 / 用例数
python3 benchmark/repair_eval/contracts/test_contract.py --summary

# 按包导入（#252 以库方式使用；必须在仓库根成功）
python3 -c "import benchmark.repair_eval.contracts.acceptance"

# 按模块运行
python3 -m benchmark.repair_eval.contracts.test_contract --summary
```

summary 命令的输出固定为：

```text
{"false_accept": 0, "false_reject": 0, "cases": 7}
```

三种调用形式都必须工作：包导入、按模块运行（python3 -m）、直接跑脚本。模块顶部把自身
目录放进 sys.path，并**优先使用相对导入**，保证包导入时 task_contract 只有一份 ——
否则 isinstance(contract, TaskContract) 会拒绝调用方自己构造的契约。

`pytest` 结束时 `conftest.py` 也会打印同一行（前缀 `repair-eval cases:`）。
不需要网络、模型、ROS 或 Gazebo；只用到 Python 3 标准库与 pytest。

---

## 8. 已知限制

1. **合成夹具 ≠ 真实记录。** 位置、哈希、证据都是构造值。本层证明的是"判定逻辑不会
   错误接纳"，不是"机器人完成了抓放"。
2. **测量来源不在本层。** `evaluate()` 信任 `candidate_state` 里的测量值。谁能写这些值
   是 #249 可见性策略的范围；两层必须一起用。
3. **保护文件哈希目前来自夹具种子**（对 `flexcell fixture::<path>::v1` 取摘要），不是
   真实文件摘要。换成真实文件哈希是一行改动，但必须连同 case 一起升版本。
4. **单一任务、单一机器人语义。** 一个契约对应一类任务；跨任务不能复用摘要。
5. **回归记录是候选声明的 PASS/FAIL 文本。** 本层只检查"是否声明为 PASS 且数量够"，
   回归自身的可信度取决于执行侧。
6. **未接入 CI。** 仓库 `.github/` 不在本 issue 的授权路径内；接入建议见下一节。
7. **UNKNOWN 既不是通过也不是失败**，统计时必须单列。把它折进任何一边都会改变结论。

---

## 9. 集成注意点

- **冻结摘要进 run 记录**：把 `contract.sha256()` 写进运行清单；`Verdict` 里带
  `contract_sha256` / `task_id` / `contract_version`，事后比对即可发现"用改过的契约
  重新评级"。
- **与 #249 的分工**：可见性策略负责"谁能读到裁决、谁只能看允许的信息"；本层负责
  "判定只用契约的数字"。两者都不替代执行侧的证据采集。
- **与独立评估器**：`benchmark/evaluators/` 的 `evaluate.py` 继续负责 held-out 的几何
  判定；本层是修复实验的策略外壳，不修改、不弱化任何已冻结的评估器或阈值。
- **CI 接入建议**（需另开 issue 授权 `.github/`）：把
  `python3 -m pytest benchmark/repair_eval/contracts -q` 作为门禁，退出码即结论。
- **文件位置**：代码与用例在 `benchmark/repair_eval/contracts/`，文档即本文件
  `docs/repair_eval/TASK_CONTRACT.md`。
