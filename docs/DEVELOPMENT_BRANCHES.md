# 开发分支与模块分工

共同源码基线：`3e81f956e4559edc4d7d17e8ef6df6f3eb798f27`。保留旧实验分支与原始证据。新分支从同一分配 checkpoint 出发；当前只有物理能力线 active，其余 RESERVED 表示已建立、尚未分配开发者。

| 工作线 | 模块 | 分支 | 状态 |
|---|---|---|---|
| physical | 既有物理技能、接触推动 | `develop/physical-capabilities-20261113` | ACTIVE |
| runtime | Runtime 执行、决策与任务编排 | `develop/runtime-execution-20261113` | RESERVED |
| agent | 开发 Agent | `develop/agent-development-20261113` | RESERVED |
| development_skills | 开发 Skill | `develop/development-skills-20261113` | RESERVED |
| experience | 经验与学习 | `develop/experience-learning-20261113` | RESERVED |
| perception_data | 感知与数据 | `develop/perception-data-20261113` | RESERVED |
| validation | 验证与工程 | `develop/validation-infrastructure-20261113` | RESERVED |
| architecture | 模块化架构 | `refactor/skill-layer-boundaries-20261113` | CHECKPOINTED |

可机读分工与主要路径见 [development_branches.json](../config/development_branches.json)。分支用于隔离开发，包与接口继续约束依赖；建立分支不代表启动并发 Agent，也不提升能力等级。

公共 ROS 接口、预算/取消/隔离契约和跨模块构建变更，在相关工作线上提交最小改动，集成时连同依赖审查。冻结验收规则、历史任务与证据继续保持原样。目标集成分支是当前架构线；`main` 不自动合入。

物理能力当前关口：固定源码下重复完成公开推动任务，同时执行普通抓放回归。记录每次结果和失败，不替换失败；存在未知动作终态时停止后续调度。
