# TransferBench 记录器验收：TB-001

本轮完成官方资料核验、FlexCell 分层迁移设计、T1 草案与离线成本账本。
用户选择的范围是“设计 + 最小实现”。它没有执行新的机器人任务或调用模型 API。

实现位于 `setup/125_transfer_cost.py`，设计与来源在
[TRANSFER_BENCHMARK.md](../../../docs/TRANSFER_BENCHMARK.md)。
独立审查发现的 API 回执重复计费、计时包含锁/校验等待问题已修正；共同配置在
plan 中封存，每个 trial/API 只使用一个独立主回执。WSL 重启后的未知时长可显式
关闭并续写，缺失区间仍保留为 INCOMPLETE，不补造零分钟。

## 验证与证据边界

- `validation/unit_attempt01.log`：最初 15 tests passed；不是最终修订的验证。
- `validation/unit_attempt02.log`：修订后的 **18 tests passed**。覆盖拒绝覆盖、hash
  篡改、重复 trial/API receipt、失败保留、身份分组、SIGABRT、非有限/强制类型、
  单调时钟、pure wait 重叠、未知区间续写、累计 diff 不重加及 AC@90 保持 NOT_RUN。
  同一命令已接入现有 `.github/workflows/ci.yml`；本轮没有运行远端 CI。
- `fixture/`：真实执行 CLI 的流程记录，但所有任务/API 输入都明确标记为
  **SYNTHETIC_TOOL_FIXTURE**。包括 5 个合成 attempt，按两种指纹/校准身份分 cell；
  一个较早 JSON 成功但 rc=-6 的输入按 ABORTED_PROCESS 报告；HARNESS_ERROR 单列。
  合成费用中的一个 unknown 使费用汇总为 INCOMPLETE。重复 API 主回执和 report
  覆盖两个操作预期返回 2，其输入和错误输出都保留。
- coding_agent session 的时长只表示 CLI fixture 演练区间，**不是 T1 适配工程时间**。
  没有补算历史人工分钟、物理成功率、真实 tokens 或费用。
- `validation/previous_receipts_attempt01.json` 保留旧证据复核工具的 manifest 格式异常；
  兼容路径到摘要字符串/元数据对象两种格式后，attempt02 确认此前三个 receipt 的
  46/171/219 个封存文件在三棵树中均未变化。没有修改旧证据或重新采样。

迁移实验、AC@90、实体安全及本轮决策时延均为 **NOT_RUN**，n≥50 保持冻结。
`pilot_draft_v1.json` 没有实际留出布局/成功谓词清单，不能当已登记实验。
既有校准/profile/运行栈未由本工具重启或替换；先前学校 clef 实际接管的证据
仍在独立的 `school_clef_route_20261006` / `route_hardening_20261006` /
`place_transport_20261006` receipts 中，未改写或并池。

## 复核

账本引用的绝对路径来自权威 WSL 工作区，运行以下命令会重新核验所有内容摘要：

```bash
cd /home/ros/agentic_workcell_ws
python3 setup/125_transfer_cost.py report \
  --ledger setup/acceptance/transferbench_foundation_20261006/fixture/cost.jsonl
```

stdout 报告不会修改已封存的 fixture/report.json。若换机器，原始文件仍可通过
相对路径 SHA256SUMS.json 复核；不能修改原账本中的绝对路径伪装成原始记录。
封存文件集合与字节复核：

```bash
python3 setup/acceptance/transferbench_foundation_20261006/scripts/verify_frozen.py
```

fixture 的生成器为 `scripts/create_fixture.py`，拒绝覆盖已有 fixture 目录。
`validation.json` 记录本轮源文件身份及验收范围；SHA256SUMS.json 在 prettier 后封存。
