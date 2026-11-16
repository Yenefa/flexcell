# ASSUMPTIONS — 外部接口假设（v0.1 草案）

> **状态：DRAFT v0.1。全部为「计划接口」，一个字节都没有实现。**
> base `2ca40ebe` 上 **不存在** `benchmark/repair_eval/` 目录（已核实：`ls` 报 No such file or directory）。
> 本文档不是 API 文档，是**依赖声明**：本协议需要这两个模块提供什么，才能端到端执行。

## 1. 为什么要有这份文档

本协议的判定链有四道门，其中两道落在本仓库**尚未存在**的模块上：

| 门 | 依赖 | 现状 |
| --- | --- | --- |
| G1 目标门 | `benchmark/evaluators/evaluate.py` | **已存在**，冻结（sha256 见 [TASKS.md](TASKS.md) §6） |
| G2 回归门 | 同上 + 保留场景清单 | 评估器存在；场景清单见 [TASKS.md](TASKS.md) §4（`TBD` 部分由 #253 固定） |
| G3 契约门 | `benchmark/repair_eval/contracts`（#250） | **不存在** → 计划接口（§3） |
| 条件 A 的信息边界 | `benchmark/repair_eval/visibility`（#249） | **不存在** → 计划接口（§2） |
| G4 独立验收 | 独立验收脚本 | **不存在**（`TBD`，由 #252 落地） |

把「计划」写成「已实现」会让读者以为本协议今天就能跑。所以本文档的每一条都带
**「计划」**或 **`TBD`** 标记，并且**没有一条**被写成现状。

## 2. `benchmark/repair_eval/visibility`（#249）— 计划接口

### 2.1 本协议需要的 API（计划草案）

```python
# 计划接口 — 未实现。最终签名以 #249 交付为准。
from benchmark.repair_eval import visibility

policy = visibility.load_policy(policy_path: str) -> VisibilityPolicy
# VisibilityPolicy 计划字段：
#   policy_id: str                 # 版本化标识，如 'repair-visibility/0.1.0'
#   condition: str                 # 'A' | 'B' | 'C' | 'D'
#   readable_roots: list[str]      # 允许读的根（相对工作区）
#   denied_roots: list[str]        # 明确拒绝的根
#   allowed_record_fields: list[str]  # 允许下发的结构化字段名
#   alias_policy: str              # 别名/软链接/相邻 worktree 的处理策略

view = visibility.build_view(workspace: str, policy: VisibilityPolicy,
                             feedback_payload: dict | None) -> FeedbackView
# FeedbackView 计划字段：
#   payload: dict                  # 实际下发给修复者的信息包
#   payload_sha256: str            # 上者的摘要（写进记录）
#   withheld: list[str]            # 被扣下的内容类目（审计用）
#   leaks_detected: list[str]      # 若布局本身会泄漏，列出泄漏通道

verdict = visibility.assert_no_leak(workspace: str, policy: VisibilityPolicy,
                                    probe_paths: list[str]) -> LeakVerdict
# LeakVerdict 计划字段：
#   ok: bool
#   violations: list[dict]         # {path, channel, reason_code}
#   checked: int
```

### 2.2 本协议依赖的版本化契约（计划）

| 契约项 | 内容 | 为什么本协议需要它 |
| --- | --- | --- |
| 策略文件带版本号 | `policy_id` 形如 `repair-visibility/<semver>` | 记录里要写 `visibility_policy_id`，否则事后无法复现「当时能看到什么」 |
| 策略按条件分档 | A / B / C / D 各一档，档间差异**声明式**（列表），不靠代码分支 | 否则条件间差异无法审计 |
| 拒绝是**机制**而非提示 | 被扣下的内容在下发前就从视图里消失，而不是「请不要读」 | 条件 A 的有效性完全依赖这一点 |
| 泄漏通道枚举 | 至少覆盖：日志默认路径、软链接、相邻 worktree、残留产物、环境变量、缓存 | [PROTOCOL.md](PROTOCOL.md) §2 的 A 边界就是照这张表写的 |
| 拒绝可审计 | 每次拒绝产生结构化记录（路径 + 通道 + 码） | 条件 A 的 `INVALID` 判定需要证据 |

### 2.3 本协议会消费的拒绝理由码（计划）

| 码 | 含义 | 本协议如何使用 |
| --- | --- | --- |
| `VIS_DENY_DENIED_ROOT` | 访问落在 `denied_roots` 内 | 正常拒绝；不改变记录终态 |
| `VIS_DENY_ALIAS_CHANNEL` | 经软链接/别名/相邻 worktree 绕过 | **泄漏事件** → 该槽位 `INVALID` |
| `VIS_DENY_RESIDUAL_ARTEFACT` | 经残留产物（上次运行的旧文件）泄漏 | 同上 |
| `VIS_DENY_ENV_CHANNEL` | 经环境变量/缓存泄漏 | 同上 |
| `VIS_ALLOW_STRUCTURED_PAYLOAD` | 下发了协议允许的结构化信息 | 正常路径；写 `feedback_payload_sha256` |
| `VIS_POLICY_MISSING_CONDITION` | 策略未定义该条件 | **阻塞**：该条件不得开跑 |

> **注意**：上表的码名是**本协议的期望**，不是 #249 的既有约定。若 #249 用别的命名，
> 本协议**映射**过去（不改码的含义），并在 §5 差异表登记。

## 3. `benchmark/repair_eval/contracts`（#250）— 计划接口

### 3.1 本协议需要的 API（计划草案）

```python
# 计划接口 — 未实现。最终签名以 #250 交付为准。
from benchmark.repair_eval import contracts

contract = contracts.load_contract(path: str) -> TaskContract
verdict  = contracts.check(candidate_dir: str, contract: TaskContract,
                           evaluation: dict, evidence: dict) -> ContractVerdict
```

字段与理由码见 [TASKS.md](TASKS.md) §5（`TaskContract` / `ContractVerdict` / 七个 `CONTRACT_*` 码）。
本节不重复，只补充**本协议这边**的假设。

### 3.2 本协议对 #250 的额外假设（计划）

| # | 假设 | 若不成立的后果 |
| --- | --- | --- |
| A1 | 契约文件**独立于任务 spec**，且带 `contract_version` | 版本化失效，旧记录会被新契约追溯改写 |
| A2 | `check()` **不读**修复者的声称作为判定依据，只把声称用于算 `false_accept` | 错误接纳指标失去意义 |
| A3 | `check()` 对**合法修复**返回 `ok=True` 且 `false_reject=False`；否则本协议的错误拒绝率会被系统性抬高 | 无法区分「协议太严」与「修复者不行」 |
| A4 | 理由码是**稳定标识**，不是自由文本 | 无法做跨记录聚合 |
| A5 | 保护文件用**内容 hash**而非 mtime/路径白名单 | 可被 `touch` 或移动绕过 |
| A6 | 契约能表达「保留场景全部 PASS」这一条 | G2/G3 会重叠或漏判 |

### 3.3 六类负例与理由码的对应（计划）

| #250 负例类 | 期望理由码 | 本协议侧观察点 |
| --- | --- | --- |
| 声称成功但目标未达 | `CONTRACT_CLAIMED_SUCCESS_TARGET_MISSED` | `false_accept` |
| 目标或阈值被篡改 | `CONTRACT_GOAL_OR_TOLERANCE_TAMPERED` | `edited_paths` 越界 |
| 目标过而回归失败 | `CONTRACT_REGRESSION_BROKEN` | `gate_regression` 有 FAIL |
| 保护文件变更 | `CONTRACT_PROTECTED_FILE_CHANGED` | `protected_paths_digest` 变化 |
| 证据缺失或 run ID 不匹配 | `CONTRACT_EVIDENCE_MISSING` / `CONTRACT_RUN_ID_MISMATCH` | 记录字段缺项 |
| PASS 文本伴随非零退出 | `CONTRACT_PASS_WITH_NONZERO_EXIT` | 运行记录里的退出码 |

## 4. 本协议**不**假设的东西

| # | 不假设 | 说明 |
| --- | --- | --- |
| N1 | 不假设 #249/#250 **已经**实现 | base `2ca40ebe` 上目录不存在 |
| N2 | 不假设 #249/#250 的接口与本文件的签名一致 | 一致只是期望；[ADMISSION.md](ADMISSION.md) F3 要求做差异表 |
| N3 | 不假设评估器会变 | G1/G2 用的是**已冻结**的评估器；若评估器变了，本协议作废重来 |
| N4 | 不假设保留场景已固定 | 清单在 [TASKS.md](TASKS.md) §4 是 `DRAFT-FIXED`，具体 spec/seed 由 #253 定 |
| N5 | 不假设有真机 | 本协议只涉及仿真；真机（M3-R）不在范围内 |
| N6 | 不假设历史结果是本协议的基线 | 见 [PROTOCOL.md](PROTOCOL.md) §10 |

## 5. 接口差异表（计划；#249/#250 交付后回填）

| 项 | 本协议期望 | #249/#250 实际 | 差异 | 处理 | 状态 |
| --- | --- | --- | --- | --- | --- |
| visibility 策略版本字段 | `policy_id` | `TBD` | `TBD` | `TBD` | **未填** |
| visibility 拒绝码命名 | 见 §2.3 | `TBD` | `TBD` | 映射不改义 | **未填** |
| contracts 契约版本字段 | `contract_version` | `TBD` | `TBD` | `TBD` | **未填** |
| contracts 理由码命名 | 见 [TASKS.md](TASKS.md) §5.1 | `TBD` | `TBD` | 映射不改义 | **未填** |
| `check()` 的入参形状 | `(candidate_dir, contract, evaluation, evidence)` | `TBD` | `TBD` | 适配层，不改语义 | **未填** |

## 6. 允许与拒绝的例子（依赖层）

| 情形 | 判定 | 理由 |
| --- | --- | --- |
| #249 提供了一个**机制**级拒绝，A 条件读不到 `verdict.json` | **允许作为前提** | §2.2「拒绝是机制而非提示」 |
| #249 只提供了一个提示词「请不要读日志」 | **拒绝作为前提** | 同上；A 条件会失效 |
| #250 的 `check()` 在合法修复上返回 `ok=True` | **允许** | A3 |
| #250 的 `check()` 无法区分「目标篡改」与「目标未达」 | **拒绝作为前提** | 错误接纳会被误分类 |
| 本协议把 `CONTRACT_*` 码改个名字写进论文 | **拒绝** | §5「映射不改义」 |
| 在 #249/#250 未验收时先跑 b 条件「试试」 | **拒绝** | [ADMISSION.md](ADMISSION.md) F1/F2 是硬前提 |

## 7. 已知限制

- 本文件里**没有一行**是现状；所有签名、字段、码名都是**本协议单方面的期望**。
- 两个模块在 base `2ca40ebe` 上不存在，因此**本协议目前不可端到端执行**；
  `ADMISSION.md` 的 F1/F2 也因此不可能被满足。
- 若 #249/#250 交付的接口与本文件差异较大，**改本文件并升版本**，不改它们的语义。
- 独立验收（G4）目前没有落点，只有 `TBD`；它必须由一个**未参与该条修复**的步骤执行，
  具体实现由 #252 在准入时补齐。