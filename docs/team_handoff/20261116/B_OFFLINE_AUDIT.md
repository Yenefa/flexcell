# B：离线执行证据审计入口

优先级 P0；第一步 D1，完整模块 D2。把已有的日志、进度核对和时间线工具组织成一个
可供开发 Agent 消费的诊断入口；它不产生机器人任务 PASS/FAIL。

分支：`feat/offline-audit-entry-20261116`。PR base：`chore/team-handoff-20261116`。
认领与提交关联：[issue #246](https://github.com/Yenefa/flexcell/issues/246)。

## 独占修改范围

- `scripts/offline_audit/`：入口、格式适配和自己的 fixtures。
- `scripts/tests/test_offline_audit.py`：新增聚合层检查。
- `config/offline_audit_profiles/`：新证据格式需要的日志清单。
- `docs/OFFLINE_AUDIT.md`：CLI、格式、限制和实际样例。

已有三个工具及其文档/配置已准备在分支上：`run_log_audit.py`、`push_progress_audit.py`、
`pose_stage_timeline.py`。优先调用它们的现有接口/CLI，不重新实现计算规则。
需要修改旧工具时先提一个独立修复 PR，说明原因。

## 第一个 PR：统一入口与错误传播

```bash
python3 -m scripts.offline_audit --run /path/to/run --out /path/to/new-output
python3 -m unittest discover -s scripts/tests -p 'test_offline_audit.py' -v
```

这是待实现的验收入口。首个 PR 用小型 fixtures 调用三个工具，按下面契约汇总报告。
CLI 退出码：0=所有要求的诊断步骤成功执行；1=数据缺项/不能对齐/无法计算；
2=参数、I/O 或子工具异常。三个码都不是机器人任务成败。

注意：已有进度核对工具在结果 UNKNOWN 时仍可能退出 0；不能只看子进程退出码，
必须保留其报告状态、reason code 和 stderr。任一失败仍保留已生成产物。

## 输出契约

输出新建目录中的 `report.json`，含：

- `schema_version: offline-run-audit/1`、`diagnostic_only: true`、
  `robot_task_outcome: NOT_EVALUATED`。
- `source`：输入目录、已知 run ID / 执行源码 SHA、输入文件摘要；缺失写 UNKNOWN。
- `checks`：retention/progress/timeline 各自状态、退出码、reason codes 和子报告路径。
- `issues`：缺文件、端点不足、时钟无法对齐、格式不支持等；不能自动填零或丢弃。
- `derived_inputs`：如需适配，将每个派生文件、原始来源和字段映射列明。

输入原样保留；输出必须是输入目录之外的新目录。已有目录拒绝覆盖，符号链接解析后
仍不得把输出写回输入。可复用的 profile 是日志格式清单，不是新的任务验收阈值。

## 第二个 PR：接一条真实归档

只要求支持当前 ContactPush 原生记录格式，不要求一次兼容所有历史实验。

- 样本在 `setup/acceptance/physical_reachable_contact_20261113/`，ZIP 与 SHA 在 `archive.json`。
- 解压到仓库外临时目录，选 `LONG_1`。核对 ZIP SHA 后安全解压，拒绝路径穿越。
- 可读取 `provenance.json`、`runtime/runtime_result.json`、`contact_goals/*/action_result.json`、
  `sim/skills/composites/*.jsonl` 和位姿/阶段记录。
- 尝试顺序用原生 composite 事件与 request ID 关联，不依赖 UUID 文件名排序。
- 适配结果写入输出的 `normalized/`。字段不存在就记 UNKNOWN；不插值、不制造接触/阶段证据。
- 归档 source SHA 与当前工具版本分别记录。历史控制源码和当前工具不同，不是篡改证据。
- 提交命令、输出和输入前后哈希；允许某些事实 UNKNOWN，必须解释来源不足。

## 验收情况

- 完整输入、缺文件、缺端点、乱序/重复时间、子工具非零退出均有案例。
- 子工具写出 UNKNOWN 但退出 0 时，聚合结果不能冒充信息完整。
- 空输入、格式不支持、已存在输出目录、输入内输出目录都明确失败。
- 中途失败保留原始输入与已生成诊断；不覆盖既有证据。
- 不出现本工具计算的任务通过结论；原验收结论如需展示，须明确标为来源引用。

可复制给开发者：

> 在分支 feat/offline-audit-entry-20261116 开发统一离线审计入口。先复用并运行已有三个
> 工具的验证脚本；第一 PR 完成 CLI、报告聚合和错误传播，第二 PR 再接 LONG_1 归档。
> 不改物理控制、任务、冻结验收器或原始证据；提交 PR 到 chore/team-handoff-20261116。
