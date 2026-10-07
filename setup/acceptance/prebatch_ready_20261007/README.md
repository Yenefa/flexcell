# 大批测前开发检查点与原始失败保留

2026-10-07，本轮主线开发范围完成：整链预检、暂停回执查询、严格 JSON/终态类型审计、
统一只读就绪报告。345 项 skills 单元/回调测试、54 项离线仪器测试及 skills 构建通过。
这些测试计数不是机器人批次；本轮只有 **2 份原生 episode 和 1 条预登记负向请求**。

- 一段组合：成功，Clef 接管 3 次，DeepSeek 0，GPU 4135 个报告 tokens。
- S1 源任务：成功，Clef 6 / DeepSeek 1，GPU 10100 个报告 tokens。
- 非法后续占用链：在第一条 Observe/原生动作前被错误 60 拒绝；所有 JSONL 增量均为 0。
- 18 个 controller 终态均为 4，未知传输/隔离事件为 0；收尾 task state=IDLE。
- 38 个 Python 安装源码与权威源码逐字节一致；原模型、校准及 prompt 摘要不变。

[完整报告](report.json)、[预注册](plan/manifest.json)、[成本账本](cost.jsonl)、
[资格草案](plan/qualification_v2_draft.json)与冻结 source/ 一并保留。
原生任务与负向控制请求分开报告：账本共有 3 条 trial，负向请求仍标 FAILED，
不能把“负向门正确拒绝”改写成机器人任务成功。

## 首轮脚本错误及受限继续

原控制客户端错误地要求 ABORTED=5，安装 ROS 实际为 CANCELED=5、ABORTED=6。
真实控制 goal 已按 error=60、outcome=1、status=6 返回，component IDs 为空，
动作/策略日志全部零增量；客户端 rc=2，原 pilot 失败，均保留。

[只读状态纠正](validation/control_audit_v2.json)与 scripts/adjudicate_control.py 使用
原 goal、原父回执和原日志快照确认负向条件。它拒绝 -6/134、未知/其他退出码、
任何动作增量及错误指纹，原 FAILED trial 和原 driver 字节保持。
随后 scripts/continue_registered.py 独占续跑标记，只完成此前登记且尚未执行的
一段组合与一次 S1，没有重发负向请求或追加替换样本。
修正版控制客户端单独保留，未运行。该源修正不是重复采样。

validation/ 还保留一次源码镜像 SameFileError：权威文件误拷到自身，原文件未修改，
随后只复制到 task/Windows 树。部分墙钟开发区间包含构建、等待、纠正和封存；
此前规划未计量，人工/助手 tokens/费用 NOT_RUN，实际 API 和 GPU 费用 UNKNOWN。

## 停止边界

运行前后 `read_only_preflight_ok=true`，**`ready_for_large_test=false`，`large_tests_started=false`**。
资格草案只计算拟定门槛，不生成留出状态或执行任务。NET-001、B 抓取根因、独立资格输入、
正式统计与预算协议仍待处理；网络稳定性 NOT_ACCEPTED、B 根因 UNKNOWN。
n≥50、AC@90、实体安全验收和运动中崩溃恢复继续冻结。

[操作与完整交接](../../../docs/PRE_BATCH_CHECKPOINT.md)。只读封存检查：
`python3 scripts/verify_frozen.py`，不驱动机器人。
