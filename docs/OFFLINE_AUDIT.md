# 离线执行证据审计入口（issue #246，第一个 / 第二个 PR）

一个**只读**的诊断入口：调用仓库里已有的三个工具，把它们的报告聚合到输入目录之外
的一个新目录。它不计算任务是否成功，也不改物理控制、任务定义、验收规则或原始证据。

## 命令

在仓库根目录执行：

```bash
python3 -m scripts.offline_audit --run /path/to/run --out /path/to/NEW_output
python3 -m unittest discover -s scripts/tests -p 'test_offline_audit.py' -v
```

- `--run`：一个已经归档的 run 目录；只读，输入前后都会算 SHA256。
- `--out`：必须不存在，且解析符号链接后仍必须位于 `--run` 之外。
- `--profile`：可选，证据格式清单（文件名列表），默认 `config/offline_audit_profiles/native.json`。
- `--source-sha`：可选，已知执行源码 SHA；缺省写 `UNKNOWN`。

退出码只描述**诊断是否跑通**，不是机器人任务成败：

| 码 | 含义 |
| --- | --- |
| 0 | 三个要求的诊断步骤都成功执行 |
| 1 | 数据缺项 / 无法对齐 / 无法计算（含子工具报告 UNKNOWN 但退出 0） |
| 2 | 参数、I/O 或子工具异常 |

## 复用的三个工具

| check | 工具 | 子报告 |
| --- | --- | --- |
| retention | `scripts/run_log_audit.py` | `retention/audit.json` |
| progress | `scripts/push_progress_audit.py` | `progress/summary.json` |
| timeline | `scripts/pose_stage_timeline.py` | `timeline/summary.json` |

profile 里的 `requires` 只说明该 check 需要哪类日志。没有匹配输入时不调用子工具，
记 `status: NOT_APPLICABLE` 和 issue `INPUT_ABSENT`，**不填零、不猜值**。
子工具即使退出 0，只要报告里是 UNKNOWN，聚合结果仍记 issue 并以码 1 退出。

## 输出契约

`<out>/report.json` 含：

- `schema_version: offline-run-audit/1`
- `diagnostic_only: true`
- `robot_task_outcome: NOT_EVALUATED`
- `source`：输入目录、run ID、源码 SHA（缺失为 UNKNOWN）、每个输入文件的 SHA256/字节数
- `checks`：每项的状态、退出码、reason codes、stdout/stderr、子报告相对路径
- `issues`：缺文件、端点不足、时钟无法对齐、子工具异常等，逐条带 check 与 code
- `derived_inputs`：第一个 PR 为空；第二个 PR 接归档时在此列出派生文件、来源和字段映射

中途失败仍保留已生成的产物；已有输出目录会被拒绝，不覆盖既有证据。

## 第二个 PR：接一条真实归档（LONG_1）

```bash
python3 -m scripts.offline_audit \
  --archive-zip setup/acceptance/physical_reachable_contact_20261113/raw-43455056965.zip \
  --manifest  setup/acceptance/physical_reachable_contact_20261113/archive.json \
  --out /path/to/NEW_output --tool-sha "$(git rev-parse HEAD)"
```

`--archive-zip` 与 `--run` 互斥。流程：核对 ZIP 的 SHA256 与 `archive.json`
记录值 → 拒绝绝对路径 / `..` / 盘符成员 → 解压到**仓库外**临时目录 → 定位 `LONG_1`
→ 生成 `normalized/` → 按第一个 PR 的契约写 `report.json`。

`normalized/` 的五个文件（全部是只读字段映射，没有计算）：

| 文件 | 内容 |
| --- | --- |
| `identity.json` | 标签、task SHA、执行源码修订、归档 SHA、**当前工具版本** |
| `composite_sequence.json` | 原生 `seq` 排序的事件序列；`goal_uuid` / `component_goal_uuid` / `component_run_id` |
| `contact_goals.json` | 用 `request_id` / `goal_uuid` 与运行时清单关联的子目标，目录名不用于排序 |
| `source_claims.json` | 四个来源的结论**并列**为 `source_reference`，分歧不合成 |
| `observations.json` | 世界状态记录数、通道计数、原生 summary 状态；不生成阶段或接触证据 |

字段不存在写 `UNKNOWN`，并记 `SOURCE_FIELD_ABSENT`；关联不上记 `SOURCE_LINK_ABSENT`。
归档源码修订与当前工具版本分别存于 `source.normalization`，二者不同不是篡改证据。

原生归档不含三个旧工具认识的日志名，所以 `long1.json` profile 让三项检查记为
`NOT_APPLICABLE` + `INPUT_ABSENT`，而不是伪装成工具异常；诊断退出码为 1
（数据不适用），仍不是机器人任务结论。

## 决策记录（自行判定，2026-11-17）

交接时留下两个开放问题。按仓库内代码自行判定，不再回问；依据均可复查。

### D1：四个来源结论不一致时如何取舍

**决定：不取舍。四个值并列保留，工具不合成任何任务结论。**

- 判定"任务通过"需要的信息不止这四项。`experiments/physical_capabilities/t08_*/run_window.py`
  里 `passed` 的条件是：驱动退出码为 0、`runtime.agent_claimed_success` 为真、
  `verdict.passed` 为真，并且 `verdict.evidence.gates` 恰好 9 道且全部 ok。
- 也就是说"通过"是**验收层的合成结果**，依赖 gate 明细。审计工具拿不到 gate 明细，
  挑任何一个来源当结论都等于伪造这个合成。
- 因此 `source_claims.json` 只记 `kind: source_reference` 与 `conflicts`，
  `robot_task_outcome` 恒为 `NOT_EVALUATED`；四条并列即为最终形态，不是待办。
- 若将来需要单一权威结论，应由验收负责人指定来源，再在 `source_claims.json`
  增加 `authoritative: <source>` 字段；不由审计工具推断。

### D2：verdict.json 由哪一层生成

**决定：由独立验收层生成并写入 trial 目录根；不是 run 层，也不是窗口层根。**

- `setup/acceptance/evobot_t08_evidence_loop_20261112/scripts/build_trial_evidence.py`
  中，`from benchmark.evaluators import evaluate as evaluator` 之后调用
  `evaluator.evaluate(spec, evaluator_input)`，并把返回值写入
  `(trial_dir / "verdict.json")`；`trial_dir` 是该脚本的第一个位置参数。
- 历史归档印证：`setup/acceptance/evobot_t01_baseline_b_20261111/verdict.json`、
  `evobot_t05_b_20261111/verdict.json` 均直接位于 trial 目录根。
- `scripts/sim_window.py`（执行层）全文不含 `verdict` 字样，只调用 `sim_smoke.py`
  跑 episode 并汇总窗口结果，不生成独立验收结论。
- 因此审计一个 run 时在 run 层找不到 `verdict.json`，是**真实缺失**（该次执行没有走
  独立验收），不是路径写错。工具行为维持不变，报错文案已写明
  "a passing run must retain the independent verdict that says it passed"。
- 若要让窗口层自动产出该文件，需要在窗口流程中显式调用验收步骤，而不是由审计工具补写。

## 边界

- 不输出任何由本工具计算的任务通过结论；原验收结论如需展示必须标明是来源引用。
- profile 是日志格式清单，不是新的验收阈值。
- 只支持当前 ContactPush 原生格式，不兼容所有历史实验。
- 适配器只读原始证据；输出必须是新目录，已有目录拒绝覆盖。

## 验证记录

`python3 -m unittest discover -s scripts/tests -p 'test_offline_audit.py' -v`
共 11 例，覆盖：完整报告契约、UNKNOWN 退出 0 不得冒充完整、缺输入显式失败、
子工具异常传播、已有/输入内的输出目录拒绝、真实 `run_log_audit.py` 的端到端调用、
乱序与重复时间戳的披露（`OUT_OF_ORDER` / `DUPLICATE_COPY` / `DUPLICATE_SOURCE_STAMP`
照样计数，不丢行、不重排）；
以及 ZIP SHA 校验与路径穿越拒绝、原生 ID 关联与 `seq` 排序、来源分歧并列、
缺字段写 UNKNOWN、归档 CLI 端到端且输入前后哈希不变。

真实样本（2026-11-17）：

- 命令见上；ZIP SHA 前后均为
  `5bc6ae24e5c24be0f5d0acf185230e87c1565ab75b082c0414d905598cba09d4`。
- 输出：`issues=4`、`exit_code=1`、`robot_task_outcome=NOT_EVALUATED`，
  四项 issue = 三个 `INPUT_ABSENT` + 一个 `SOURCE_CLAIM_CONFLICT`。
- 原生来源互相分歧：`verdict.passed=true`、
  `runtime_result.status=TASK_COMPLETED`、`run_status.status=EXECUTED`、
  `worldstate/summary.status=INTERRUPTED`。四个值并列保留，本工具不判定机器人任务成败。
