# 团队可直接开工的模块

这是一份开发交接，不表示以下新模块已实现。A/B/C 是模块槽位。
用户已将 #245/#246 一并交给第一位开发者；新增 C 留给另一位开发者。
未指定 GitHub 用户名，不更改 GitHub assignees；认领信息以用户分工与 issue 记录为准。

架构基线：`fbf6245c66e45a0a161a3cb103dc2751b9fa8300`。
交接准备分支：`chore/team-handoff-20261116`。A/B 保留原 `bb2be782` 起点和现有分支；
C 从本次新增交接提交出发，不移动 A/B 分支。各任务的
PR 先指向交接分支；审阅后再将需要的提交集成到 `refactor/modular-workspace-20261115`。
已有物理工作树及 `main` 保持原样。

| 槽位 | 模块 | 难度 / 优先级 | 功能分支 | 交付说明 |
|---|---|---|---|---|
| A | 机器人动作技能目录与适用条件查询 · [#245](https://github.com/Yenefa/flexcell/issues/245) | D1 起步、整体 D2 / P1 | `feat/runtime-skill-catalog-20261116` | [A_SKILL_CATALOG.md](A_SKILL_CATALOG.md) |
| B | 离线执行证据审计入口 · [#246](https://github.com/Yenefa/flexcell/issues/246) | D1 起步、整体 D2 / P0 | `feat/offline-audit-entry-20261116` | [B_OFFLINE_AUDIT.md](B_OFFLINE_AUDIT.md) |
| C | 抓取→搬运→放置闭环稳定性 · [#247](https://github.com/Yenefa/flexcell/issues/247) | D2 复现、D3 修复 / P0 | `feat/physical-pick-place-reliability-20261116` | [C_PICK_PLACE_RELIABILITY.md](C_PICK_PLACE_RELIABILITY.md) |

A 提供执行 Agent 将来可查询的动作说明；B 提供开发 Agent 将来可读取的诊断报告。
C 是独立物理能力线，先复现与保留证据，再做证据支持的抓放修复。
A/B 归数据负责人，负责动作信息、数据、日志、异常与来源整合；物理能力负责人确认根因并闭环修复。
主线负责人继续负责接触推动；其他新物理能力按依赖顺序另开任务，不同时铺开。
三个模块的代码归属分开，物理开发和数据工具开发无需互相等待。

交接基线 `7fd115d9` 的 [team-handoff CI](https://github.com/Yenefa/flexcell/actions/runs/43806522767)
和 [repository-layout CI](https://github.com/Yenefa/flexcell/actions/runs/43806522701) 均通过。
这只证明准备资料与复用工具的检查完成；新模块由认领人实现，其 PR 必须带自己的测试。

C 的交接源 `f58c38f7` 经 [team-handoff CI 43807961917](https://github.com/Yenefa/flexcell/actions/runs/43807961917)
检查通过。当前只有任务说明和离线 PR 检查，尚未实现四槽驱动、运行新窗口或修复抓放能力。

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
# 另一位开发者使用 C：
# git switch --track origin/feat/physical-pick-place-reliability-20261116
```

同机开发可从公共仓库执行 `git worktree add ../skill-catalog feat/runtime-skill-catalog-20261116`
和 `git worktree add ../offline-audit feat/offline-audit-entry-20261116`，分别使用独立目录。
各自保持独立虚拟环境、构建和运行输出。本次交接没有在功能分支启动 Agent 或仿真。

## 公共约定

- A/B 的代码由第一位开发者维护，C 的代码由另一位开发者维护。公共接口、物理控制和验收规则的变更先交给主线负责人。
- A/B 仅需要 Python 环境。C 先做离线驱动测试，再按有界窗口在现有 ROS/Gazebo 环境运行；不调用付费模型。
- 缺数据明确报告 UNKNOWN；保持原始文件和历史判断原样；模块完成不等于机器人任务通过。
- 每个 PR 附：运行命令、正常例子、失败例子、输入未被改写的验证、已知限制。
- 候选代码放各自分支；开发记录放各自模块文档，公共状态和版本索引由集成负责人更新。

任务范围和认领状态见 [机器清单](../../../config/team_delegation_20261116.json)。
