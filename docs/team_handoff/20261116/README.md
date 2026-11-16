# 两人可直接开工的模块

这是一份开发交接，不表示以下两个新模块已实现。未指定 GitHub 用户名，A/B 是任务槽位，
当前状态为 READY_UNASSIGNED。先在 issue 记录认领，再开始代码开发。

架构基线：`fbf6245c66e45a0a161a3cb103dc2751b9fa8300`。
交接准备分支：`chore/team-handoff-20261116`。两个功能分支从同一个交接提交出发，
PR 先指向交接分支；审阅后再将需要的提交集成到 `refactor/modular-workspace-20261115`。
已有物理工作树及 `main` 保持原样。

| 槽位 | 模块 | 难度 / 优先级 | 功能分支 | 交付说明 |
|---|---|---|---|---|
| A | 机器人动作技能目录与适用条件查询 · [#245](https://github.com/Yenefa/flexcell/issues/245) | D1 起步、整体 D2 / P1 | `feat/runtime-skill-catalog-20261116` | [A_SKILL_CATALOG.md](A_SKILL_CATALOG.md) |
| B | 离线执行证据审计入口 · [#246](https://github.com/Yenefa/flexcell/issues/246) | D1 起步、整体 D2 / P0 | `feat/offline-audit-entry-20261116` | [B_OFFLINE_AUDIT.md](B_OFFLINE_AUDIT.md) |

A 提供执行 Agent 将来可查询的动作说明；B 提供开发 Agent 将来可读取的诊断报告。
首版都是离线模块，不连接在线调度。输入、输出和文件归属分开，双方无需等待对方接口。

交接基线 `7fd115d9` 的 [team-handoff CI](https://github.com/Yenefa/flexcell/actions/runs/43806522767)
和 [repository-layout CI](https://github.com/Yenefa/flexcell/actions/runs/43806522701) 均通过。
这只证明准备资料与复用工具的检查完成；两个新模块由认领人实现，其 PR 必须带自己的测试。

## 已有工作不再重写

#231–#234 都已有实现，集中在待审 [PR #244](https://github.com/Yenefa/flexcell/pull/244)。
#232 另有 `aux/232-push-net-displacement` 的独立实现，尚未统一；本交接没有把它们当作新任务。
这里只挑选 PR #244 的三个纯工具提交，以 `cherry-pick -x` 保留来源：

| 原提交 | 复用工具 | 本地核对 |
|---|---|---|
| `4676775` | `scripts/push_progress_audit.py` | 合成用例脚本通过，23 个 fixture 案例 |
| `2ba87fe` | `scripts/pose_stage_timeline.py` | 合成用例脚本通过，21 个 fixture 案例 |
| `13afd29` | `scripts/run_log_audit.py` | 13 项 unittest 通过 |

这些是工具检查，不是新物理验收；PR #244 的其他改动没有一并引入，原 issue 不自动关闭。

## 开工

各自在自己的 clone 中运行：

```bash
git fetch origin
# A
git switch --track origin/feat/runtime-skill-catalog-20261116
# B 在另一份 clone 中使用：
# git switch --track origin/feat/offline-audit-entry-20261116
```

同机开发可从公共仓库执行 `git worktree add ../skill-catalog feat/runtime-skill-catalog-20261116`
和 `git worktree add ../offline-audit feat/offline-audit-entry-20261116`，分别使用独立目录。
各自保持独立虚拟环境、构建和运行输出。没有人在这两个分支启动 Agent 或仿真。

## 公共约定

- A 只改 A 的目录；B 只改 B 的目录。公共接口、物理控制和验收规则的变更先交给主线负责人。
- 两个模块都可用 Python 标准库实现；首个 PR 不要求 ROS、模型服务或新仿真。
- 缺数据明确报告 UNKNOWN；保持原始文件和历史判断原样；模块完成不等于机器人任务通过。
- 每个 PR 附：运行命令、正常例子、失败例子、输入未被改写的验证、已知限制。
- 候选代码放各自分支；开发记录放各自模块文档，公共状态和版本索引由集成负责人更新。

任务范围和认领状态见 [机器清单](../../../config/team_delegation_20261116.json)。
