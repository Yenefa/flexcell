# 已提交前缀暂停与跨重启续跑：有界仿真试点

2026-10-07，一次预注册组合任务、一次 S1 回测，共 4 份原生 episode。
第一段返回 OUTCOME_PAUSED=3（请求完成但全链尚未成功）；仅重启拥有的 fleet，
Gazebo、运动服务和现场对象保持。重启前后指纹相同，续跑继承 1 段、只执行剩余 2 段，
最后完成联合观察。三段原生 ID 唯一，第一段未重放。

- 目标链：Clef 9 / DeepSeek 0；GPU 9 次调用、12545 个报告 tokens。
- S1：成功，Clef 6 / DeepSeek 1；GPU 7 次调用、10107 个报告 tokens。
- 再次使用同一暂停回执：ERR_RESUME_REJECTED=65，没有新增决策、Observe、Skill 或控制器动作。
- 30 个控制器终态均为状态 4，没有未知传输或隔离事件。
- skills 330 项、既有 benchmark 仪器 42 项通过；接口及 skills 构建通过。

原始回执在 execution/；独立审计在 execution/composite/audit.json，
[完整报告](validation/final_report.json)、[前瞻注册](plan/manifest.json)、
[追加式成本账本](cost.jsonl)及 source/ 中冻结的代码一并保留。
计划最多 4 份原生 episode，实际为 4；没有替换失败或补采。

所有失败保留在 validation/：首次构建误扫描证据接口包，限定正式 src 后通过；
ROS 测试夹具的整数/双精度计划表示及 STARTED 测试钩子修正后通过；
首次 fleet switch 因仿真依赖未运行被预检拒绝，恢复基础服务后才注册试点；
仪器从工作树执行时旧回执的绝对路径绑定不符，从权威工作区执行通过。
这些均没有替换机器人执行。文档在试点完成后更新，source/ 保留执行前文档。

只接受确认的 PAUSED 前缀，不接受运动中崩溃、未知 STARTED、失败或取消回执。
一次性 claim 在失败或中断后也不撤销；现场漂移拒绝继续。
该结果属于仿真控制流和路由证据。n≥50、AC@90、实体安全验收冻结；
网络稳定性与运动中崩溃恢复未验收，GPU/实际 API 账单 UNKNOWN。
部分墙钟区间包含构建和等待，不能当作完整人力成本；人类分钟及助手 tokens/费用 NOT_RUN。

只读封存检查：`python3 scripts/verify_frozen.py`。它不驱动机器人。
