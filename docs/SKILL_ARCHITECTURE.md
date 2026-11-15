# 开发技能、执行技能与物理能力研发

按职责分成三个域，在一个仓库中分别维护代码、依赖和验证。物理能力研发产出的
可复用算法另有独立安装包，作为执行层的依赖。现阶段保留单仓，逐步拆包。
迁移与集成跟踪：[issue #242](https://github.com/Yenefa/flexcell/issues/242)。

| 职责域 | 使用者与职责 | 代码位置 | 对外边界 |
|---|---|---|---|
| Development Skills | 开发 Agent 使用的诊断、构建、仿真生命周期和证据检查方法 | `development_skills/` | 开发工具与使用记录；不在机器人任务执行时加载 |
| Execution Skills | Runtime 规划、调度已安装的技能，管理预算、所有权、取消和返回状态 | `runtime/`、`src/flexcell/flexcell_skills/` | `flexcell_interfaces` 的 Action/Service/WorldState，以及明确的结果契约 |
| Physical Capability Development | 根据能力缺口提出候选，在隔离工作区开发、构建、执行和回归 | `evolution/`；候选工作树与实验驱动 | 输入任务失败记录和能力缺口；输出源码版本、适用范围与独立验证记录 |

物理能力的**研发流程**与其**可执行产物**分别管理。当前可复用物理模型在
`src/flexcell/flexcell_capabilities/`，包括手指接触几何、约束轨迹计算和只读接触遥测。
它只依赖 Python 标准库和 NumPy，可以单独安装与检查。

## 依赖与调用方向

正常任务执行的调用方向是：

`Runtime → Execution Skill → 能力模型 + 平台适配 → 机械臂`

`flexcell_interfaces` 提供 ROS 通信契约。动作结果继续区分推动结果、返回完成、
末端就绪、未知终态和独立验收。任务目标与最终成功判断不进入接触几何模型。

物理能力研发由另一条流程驱动：

`能力缺口/失败记录 → 开发 Agent + Development Skills → 隔离候选 → 验证与回归 → 固定候选版本`

执行层消费安装时选定的版本。开发工具、提案生成器与实验工作区不作为执行包的
依赖。运行失败可以输出记录供开发流程消费；运行时不直接导入研发脚本修改自身。
候选通过开发验证也不会自动成为正式基线。

现阶段沿用已有 ContactPush/MoveToPose 通信接口和证据格式；没有额外引入服务总线、
热加载协议或新的通用插件系统。

## 本次已经拆出的边界

- 新包 `flexcell_capabilities` 承接原 `contact_geometry.py`、`contact_trace.py`。
  算法体保持一致，遥测模块仅改为依赖新包的几何模块。
- 运行时的接触控制与 Action Server 直接消费新包；旧 Python 路径保留兼容导出，
  既有客户端获取同一组类与函数。
- `flexcell_skills` 声明对能力包的单向依赖；能力包无 ROS、执行包、研发工具依赖。
  colcon 当前包数由 4 增为 5；构建技能包使用 `--packages-up-to flexcell_skills`。
- [边界配置](../config/skill_boundaries.json) 和
  [检查脚本](../scripts/check_skill_boundaries.py) 检查静态导入、常见字面量动态导入、
  `sys.path` 修改和文件加载调用。Runtime 客户端不能直接导入物理能力或执行包实现；
  能力核心只允许标准库、NumPy 和自身依赖。

检查覆盖现有 Runtime 和 ROS 执行源码。2026-11-15 已将原 13 处加载研发/实验目录的
依赖迁出 Runtime 或改成共享纯模块，`legacy_exceptions` 现在为空；当前扫描 85 个 Python
文件，没有保留依赖例外。新增反向依赖继续失败。静态检查不构成任意动态文件访问的沙箱。

## 研发入口已退出 Runtime

| 内容 | 当前归属 | 执行层如何使用 |
|---|---|---|
| B/C 实验准备、B/A′ 批次计划、反例检查 | `experiments/baselines/` | 研发工具调用 Runtime 的公开规划函数 |
| 自评分、补评、重评、声明统计 | `experiments/baselines/assessment/` | 普通执行不加载这些实验工具 |
| v1 模型 CLI | `experiments/baselines/plan_v1.py` | `runtime/planner/agent_planner.py` 保留纯规划函数，chat 显式传入 |
| 有界恢复所需的失败分类 | `runtime/recovery/failure_classification.py` | `recover.py` 直接调用，不导入 `evolution/` |
| 同区域落点分散 | `runtime/planner/spread_destinations.py` | 运行时与研发端共用同一函数 |

旧研发分类和落点辅助路径保留兼容导出，依赖方向为研发 → 运行时纯策略。
共享函数体保持原样，诊断分类与落点约束没有重新调参。
迁移清单见 [research_entrypoints.json](../config/research_entrypoints.json)。
CLI 使用新路径；历史命令与原始证据保留在其原 checkpoint，不批量重写。
这里只把自评分实验移出执行目录，独立物理验收器、任务答案与冻结阈值均未修改。

## 接下来按模块迁移

1. 已完成原 13 处依赖迁移；后续用边界 CI 防止实验入口再次进入 Runtime。
2. 从 `flexcell_skills` 提取其余纯任务策略与结果契约；ROS 所有权、取消和隔离继续由
   执行适配器持有，避免在物理模型里复制状态机。
3. 按能力迁移接触控制、Pick/Place 的可复用算法；需要 ROS/MoveIt 的通信保留为
   平台适配，先拆除反向依赖再提包。独立验收器继续独立维护。
4. 每个候选记录其开发分支、固定源码、检查结果和集成目标。修改物理行为的候选补做
   实际任务与旧任务回归；纯结构拆分不作为新增机器人能力。

## 验证入口

```bash
python3 scripts/check_skill_boundaries.py
python3 -m unittest discover -s scripts/tests -p 'test_skill_boundaries.py' -v
python3 -m pip install ./src/flexcell/flexcell_capabilities
```

ROS 环境中：

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths src/flexcell --packages-up-to flexcell_skills
source install/setup.bash
python3 -m pytest -q -o addopts="" \
  src/flexcell/flexcell_capabilities/test \
  src/flexcell/flexcell_skills/test/test_capability_compatibility.py \
  src/flexcell/flexcell_skills/test/test_contact_control.py \
  src/flexcell/flexcell_skills/test/test_public_contact_runtime.py
```

精确验证状态以 `config/version_baselines.json` 的本次 source_refactors 记录和对应 CI 为准。

本轮 [CI 43405626430](https://github.com/Yenefa/flexcell/actions/runs/43405626430)
在 `441118e5` 三项作业全部通过：无 ROS 独立安装、94 个 Python 文件的依赖扫描与
12 项边界回归、接口/能力/执行包构建及 165 项既有与兼容回归。实际 colcon 根发现为
5 个当前包。原算法 AST 对齐；旧入口的类型和函数保持同一对象。
两个本地反例通过 CLI 得到非零退出码。未运行新的物理任务，完整拆分仍有上述迁移项。

2026-11-15 的进一步整理在独立架构分支完成。物理能力包、ROS 执行实现与接口、
物理实验驱动均保持 `81eed33c` 的字节内容；此次结构调整不产生新物理成绩。
完整 benchmark 的原版与候选采用相同环境逐项对比，已有失败单独列出；
差异检查通过只表示没有新增失败或减少测试覆盖，不表示整个历史测试套件通过。
工作树和环境的隔离约定见 [WORKTREES.md](WORKTREES.md)。
