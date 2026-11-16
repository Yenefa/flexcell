# 离线执行证据审计入口（issue #246，第一个 PR）

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

## 边界

- 这是第一个 PR：统一入口、报告聚合、错误传播。**没有接 LONG_1 真实归档**，
  没有格式适配，因此 `derived_inputs` 为空。
- 不输出任何由本工具计算的任务通过结论；原验收结论如需展示必须标明是来源引用。
- profile 是日志格式清单，不是新的验收阈值。

## 验证记录

`python3 -m unittest discover -s scripts/tests -p 'test_offline_audit.py' -v`
覆盖：完整报告契约、UNKNOWN 退出 0 不得冒充完整、缺输入显式失败、子工具异常传播、
已有/输入内的输出目录拒绝、真实 `run_log_audit.py` 的端到端调用。
