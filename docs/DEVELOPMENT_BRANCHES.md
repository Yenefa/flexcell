# 开发分支与模块分工

最初分配源码基线：`3e81f956e4559edc4d7d17e8ef6df6f3eb798f27`。
2026-11-15 的架构工作从最新物理 checkpoint `81eed33c` 开始，当前主工作为架构整理。
物理线保留干净 checkpoint；RESERVED 表示已建立、尚未在本会话分配开发者。
工作树不等于并发 Agent，实时 Git 状态用 `python3 scripts/worktree_inventory.py` 查看。

| 工作线 | 模块 | 分支 | 状态 |
|---|---|---|---|
| physical | 既有物理技能、接触推动 | `develop/physical-capabilities-20261113` | CHECKPOINTED |
| runtime | Runtime 执行、决策与任务编排 | `develop/runtime-execution-20261113` | RESERVED |
| agent | 开发 Agent | `develop/agent-development-20261113` | RESERVED |
| development_skills | 开发 Skill | `develop/development-skills-20261113` | RESERVED |
| experience | 经验与学习 | `develop/experience-learning-20261113` | RESERVED |
| perception_data | 感知与数据 | `develop/perception-data-20261113` | RESERVED |
| validation | 验证与工程 | `develop/validation-infrastructure-20261113` | 远端有新提交；活动状态未知 |
| architecture | 模块化架构 | `refactor/modular-workspace-20261115` | ACTIVE |

可机读分工与主要路径见 [development_branches.json](../config/development_branches.json)。分支用于隔离开发，包与接口继续约束依赖；建立分支不代表启动并发 Agent，也不提升能力等级。

原架构分支 `refactor/skill-layer-boundaries-20261113` 及 T08 历史分支保留。
验证分支已观察到远端 `65814292`，本轮不自动合入，也不覆盖其独立开发。
公共 ROS 接口、预算/取消/隔离契约和跨模块构建变更，在相关工作线上提交最小改动，集成时连同依赖审查。冻结验收规则、历史任务与证据继续保持原样。目标集成分支是当前架构线；`main` 不自动合入。

物理线已获得重复推动和一处可达范围扩展的限定证据；后续关口为更多初始条件、
完整普通任务回归及长程动作预算。旧成绩仍绑定实际执行源码，不能移记为架构分支的新成绩。
工作树布局、兼容路径和独立环境见 [WORKTREES.md](WORKTREES.md)。
