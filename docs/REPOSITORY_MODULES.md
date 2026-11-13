# 模块、构建与证据边界

本轮是目录和构建边界整理。现有机器人源码尚未按这些职责完成进一步内部拆分。
目录归属以 [repository_layout.json](../config/repository_layout.json) 为准，
版本索引和分支约定见 [VERSION_CONTROL.md](VERSION_CONTROL.md)。

## 当前模块

| 层 | 位置 | 负责的事情 |
|---|---|---|
| 任务 Runtime | `runtime/` | 公开输入、规划和任务客户端 |
| 机器人接口与执行 | `src/flexcell/flexcell_interfaces/`、`flexcell_skills/` | ROS 接口、任务执行、技能和安全/返回状态契约 |
| 原生运动与仿真 | `src/flexcell/flexcell_mtc/`、`flexcell_gazebo/`、`worlds/` | 底层运动规划、物理插件、环境与原生遥测 |
| 独立验收 | `benchmark/` | 任务、隔离、独立评分；冻结规则继续按原约束维护 |
| 数据格式与导出 | `data/` | 数据集格式和离线工具，与实时执行分开 |
| 研发与经验 | `evolution/`、`development_skills/` | 提案和经验；编码 Agent 的开发实践与机器人技能分别记录 |
| 工程基础设施 | `infra/`、`scripts/`、`config/`、`.github/` | 构建、启动、部署、配置和仓库检查 |
| 历史证据 | `setup/acceptance/`、`experiments/pilot-001/runs/` | 原始记录、失败、执行快照和复核资料 |

`setup/` 的既有编号工具继续提供兼容入口。新的可复用工程工具放入 `scripts/`，
业务实现放入相应源码模块。`experiments/` 的研究定义与其 `runs/` 结果分开看待。

## 构建边界已执行

当前第一方 ROS 包只有四个：`flexcell_interfaces`、`flexcell_skills`、
`flexcell_mtc`、`flexcell_gazebo`，统一位于 `src/flexcell/`。

归档目录中还存在七份历史 `flexcell_skills` 包快照。它们保留原位置与内容，
由父目录的 `COLCON_IGNORE` 排除出根工作区的包发现。进入历史子工作区单独复现时，
仍可按该快照自己的说明构建；根目录的实时构建只选择当前源码。

推荐构建入口：

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths src/flexcell --symlink-install \
  --packages-select flexcell_interfaces flexcell_skills
```

需要原生插件时按目标增加 `flexcell_mtc`、`flexcell_gazebo`，并使用既有锁定的上游工作区。
`infra/Dockerfile.sim` 已在独立 `ws/src` 中构建，保持其原有环境与锁定依赖。

仓库检查：

```bash
python3 scripts/check_repository_layout.py --colcon "$(command -v colcon)"
python3 -m unittest discover -s scripts/tests -p 'test_repository_layout.py' -v
```

第一条同时检查声明的包、归档标记和实际根目录 colcon 发现结果；不启动仿真器。
没有 colcon 时可省略该参数做静态检查，输出会明确标记实际发现检查 `NOT_RUN`。
路径匹配的 push/PR 运行独立的 `repository-layout` CI，避免每次目录调整启动机器人实验。

## 数据边界

- 新的临时输出写入 `artifacts/<run-id>/`，或仓库外的运行目录；当前 `.gitignore` 已排除前者。
- 原始证据在归档时附带来源、完整性校验、失败记录和执行源码 SHA，另作 evidence 提交。
- 历史 `setup/acceptance/` 资料保留，不把旧源码快照当作当前实现，也不在本轮批量搬移。
- 构建树 `build/`、`install/`、`log/` 与源码分别管理。

后续若迁移大体积证据，需要先提供校验后的目标、稳定索引和兼容链接，再单独实施。
本轮不改变物理验收判据、运行默认值或能力状态。
