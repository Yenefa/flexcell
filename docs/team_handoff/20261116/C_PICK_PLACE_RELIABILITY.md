# C：抓取→搬运→放置闭环稳定性

优先级 P0；首个 PR 为 D2 固定回归与复现，证据支持的控制修复为 D3。
按物理能力分工：本任务负责人维护抓放闭环，主线负责人继续维护接触推动。
数据负责人通过 #245/#246 整理动作说明、原始日志、异常时间线与证据链接。

开发分支：`feat/physical-pick-place-reliability-20261116`。
PR base：`chore/team-handoff-20261116`。不依赖 #245/#246 完成即可开始。
任务认领与交付：[issue #247](https://github.com/Yenefa/flexcell/issues/247)。

## 独占修改范围

- `experiments/physical_capabilities/pick_place_reliability/`：窗口定义、驱动、离线驱动测试。
- `.github/workflows/pick-place-reliability.yml`：新增独立、显式触发的仿真工作流。
- `docs/PICK_PLACE_RELIABILITY.md`：复现、范围、结果和失败解释。
- 有复现证据后，第二个 PR 可最小修改 `src/flexcell/flexcell_skills/flexcell_skills/pick_server.py`、
  `place_server.py` 与新增 `src/flexcell/flexcell_skills/test/test_pick_place_reliability.py`。

ContactPush、接触几何、contact_* 控制、TaskFSM 公共所有权/取消协议继续由主线负责人维护。
若根因涉及这些共享模块，先提交证据与所需接口，不在本任务中自行跨范围改动。
原任务、默认参数、门限、冻结验收器和历史失败数据保持原样。

## 第一个 PR：冻结一个四槽窗口

读取现有入口 `scripts/sim_smoke.py`；直接复用原有 `normal` 和 `dual_object`，
`--backend velocity_servo --skill-backend legacy`，不改物体位置、目标位置或容差。
每槽独立初始化、独立输出、顺序执行；不要构造新的简单场景替换已有任务。

| 顺序 | label | case |
|---|---|---|
| 1 | NORMAL_1 | normal |
| 2 | DUAL_1 | dual_object |
| 3 | NORMAL_2 | normal |
| 4 | DUAL_2 | dual_object |

运行前提交源码 SHA、四槽顺序、后端、配置/镜像和预算。单槽外层上限 360s，
窗口任务总上限 1440s；CI 总上限 60min（包含镜像构建）。维持原任务内部预算和超时，
不可用外层较大预算延长原任务。首次窗口后不以补跑覆盖失败。

复用 `infra/Dockerfile.sim` 的锁定依赖和旧实验工作流模式。新工作流先只支持
`workflow_dispatch`，使用 `concurrency.group: physical-capabilities`、
`cancel-in-progress: false`，与当前推动实验串行共享资源；单次容器 CPU=2。
工作流必须在当前功能分支上显式运行，不自动合并 main 或提升正式基线。

不要重写旧实验归档中的驱动。可参考
`experiments/physical_capabilities/t08_repetition_20261113/run_window.py`，
将需要的最小包装写到自己的新目录。

## 驱动容易踩的坑

- `sim_smoke.py --out DIR` 将结果写入 `DIR/run-<id>/result.json`，不是 `DIR/result.json`。
  必须恰好一个 run 子目录、case 与声明一致；缺失或多份都明确报错。
- 外层超时不等于动作已经停止。发生未知终态、停止未确认或外层超时后，
  停止后续槽，保留部分结果并标记 UNKNOWN；不盲目发送下一目标。
- 每槽保存 driver 退出码、任务结果、原始阶段轨迹、物体/关节状态和日志目录。
  运行失败、启动失败和缺文件均保留；不能只归档成功。
- 运行前后核对源码不变；源码、镜像、配置和每个结果均关联 run ID，产物附 SHA256 manifest。
- 先用假的子进程结果与临时目录做离线测试：成功、任务失败、嵌套目录、多份结果、
  缺文件、外层超时和未知终态必须覆盖。之后才执行一次真实四槽 Gazebo 窗口。

## 第二阶段：有失败才做最小修复

从实际 trace 分清：未抓住、运输中丢失、释放未完成、释放后偏移、末端未返回、
观测陈旧、任务验收未满足；证据不足就是 UNKNOWN。

数据负责人汇总错误码、阶段、原始测量与来源；本能力负责人确认物理/控制根因，
写出可证伪假设与候选。只改已有证据支持的动作逻辑，保留冻结判据、夹爪门限和任务预算。
修改后重跑同一四槽定义，并提交正常抓放回归与相关单测。旧窗口作为对照保留。

若四槽均通过，不为了“交修复”而修改控制器：交付限定回归证据、说明未复现旧失败，
不将其描述成历史释放问题已经根治或总体可靠性已证明。

## 数据负责人的交接包

能力负责人提交：运行清单、执行 SHA/镜像/配置、全部原始目录、每槽结果和失败时刻。
数据负责人用 #246 整理日志缺项、位移/位姿、阶段与错误信息；用 #245 维护动作说明中的
适用条件和证据范围。汇总字段未知时保留 UNKNOWN，不把时间相关当作因果。
两个角色都引用同一 run ID；不复制修改后的日志冒充原始输入。

## 验收边界

- 第一个 PR 的交付是：驱动与离线测试、预注册四槽、一次完整或有据停止的真实运行、
  全部原始产物和失败清单。出现真实任务失败仍可完成复现阶段，但不算能力修复成功。
- 修复阶段必须有前后可比的实际任务结果；单测通过不能代替它。
- 当前 ordinary 搬运使用仿真专用后端；此窗口属于 FUNCTIONAL_SMOKE_ONLY，
  不是推动任务的完整 9 门验收，也不证明真实硬件抓取或泛化。
- 四槽证据不能称为“完整普通任务回归”；它是该能力模块的第一批限定回归。

可复制给开发者：

> 在 feat/physical-pick-place-reliability-20261116 分支负责抓放闭环。先读现有 sim_smoke
> 与物理窗口驱动，按本文冻结四个槽，补离线测试，再显式运行一次 Gazebo 窗口。保留所有失败，
> 未知终态就停止。与数据负责人按 run ID 交接；有证据后再做 pick/place 最小修复，
> PR 到 chore/team-handoff-20261116。不要改推动主线、冻结标准、任务或原始日志。
