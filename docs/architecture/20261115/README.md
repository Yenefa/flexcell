# 工作树与模块解耦检查点

本轮把开发实验工具从 Runtime 中迁出，并隔离工作树、Python 环境和构建输出。
实施源 `18473aa8ee4d3142bf97efc29b85f5771489fa3a` 基于物理 checkpoint `81eed33c`；
工作树清单工具的容器兼容修复为 `c504ff1de9e276b028a144949d8bc9d08f71b06c`。

- 原 13 处 Runtime → 研发目录的依赖例外已清零；当前扫描 85 个 Python 文件。
- 12 个研发入口迁至 `experiments/baselines/` 及 `assessment/`，纯规划与有界恢复 API 留在 Runtime。
- 失败分类和同区域落点分散为 Runtime 纯模块，旧研发导入导出同一函数对象；经验路由随实现迁移。
- 14 个保留或提取的函数 AST 与原版相等。两个 benchmark 测试仅调整导入/源路径，断言不变。
- `src/`、ROS 接口、物理控制、物理实验驱动、九个冻结文件、推动算术与原始证据均未改。
- 工作树集中到 `/workspace/worktrees/`，保留旧路径链接；本轮没有删除分支或历史数据。

独立验证结果：

| 检查 | 结果与边界 |
|---|---|
| [skill-boundaries CI 43721840130](https://github.com/Yenefa/flexcell/actions/runs/43721840130) | 四项作业全部 PASS：依赖方向、研发兼容比较、能力包独立安装、ROS 执行兼容 |
| ROS | 接口/能力/技能三包实际构建成功；根发现为五个第一方包；170 项相关回归 PASS |
| 独立能力包 | 无 ROS 安装及导入成功；6 项检查 PASS |
| 完整离线 benchmark 对比 | 两边各 352 项，339 PASS、13 FAIL；失败身份相同，新增失败 0，缺失/新增测试 0，跳过 0 |
| 仓库、边界、工作树与入口 | 本地最终 32 项 PASS；原实现的反例验证全部捕获 |
| [repository-layout CI 43722188657](https://github.com/Yenefa/flexcell/actions/runs/43722188657) | 修复后 PASS，含真实根包发现及容器内工作树读取 |

“差异比较通过”不是整个 benchmark 通过；13 个已有失败仍在，详见 ZIP 内的完整日志与 XML。
它们包含旧版本声明/冻结索引不同步，以及本环境未附带的历史批次/外部 runner 等问题。
本轮未修改独立验收器来消除这些失败。

首轮 repository-layout CI 43721840143 失败于新增清单工具的 Git 读取（退出 128）。
随后仅对明确选中的 checkout 设置 Git 信任，并增加所有权拒绝反例；修复后的容器 CI 通过。
最初复用了旧能力包的 venv，现已采用当前工作树独立环境。全量测试中一个旧测试会重生成
能力报告；产生的改动已恢复，独立 CI 在临时检出中运行完整比较。原物理工作树保持干净。

`archive.json` 绑定原始 CI ZIP、全部成员哈希及执行源码。
`local_validation.json` 保留执行 CI 之前的本地状态；`ci_validation.json` 是后续确认。
离线复核不运行测试、仿真或模型：

```bash
python3 docs/architecture/20261115/verify_reports.py
```

当前架构与操作入口：[SKILL_ARCHITECTURE.md](../../SKILL_ARCHITECTURE.md)、
[WORKTREES.md](../../WORKTREES.md)、[研发入口迁移](../../../experiments/baselines/ENTRYPOINTS.md)。
后续仍可按契约、任务编排与平台适配继续拆分；本轮没有宣称整个仓库全部解耦。
这是结构性改进，不是新的物理能力验收；原机器人结果仍绑定其实际执行源码，正式基线未晋升。
