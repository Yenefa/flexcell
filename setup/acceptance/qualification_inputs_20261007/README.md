# TB-PREP-001：本机冻结候选输入

2026-10-07，WSL 权威目录 `/home/ros/agentic_workcell_ws`。
实现提交 `fe4e33b9e7a843ae2dd68f8c43dd8d13ac05a13f`，延续 RFC #15 的资格准备。
实际执行离线 prepare、verify 和独占输出覆盖拒绝对照，返回码分别为 0、0、2。
原生 episode、模型调用、reset 和策略部署均为 0。

本机扫描 369 个 episode 文件、2,484 个记录状态、483 个不同双物体布局。
冻结 T1/T3 各 100 个候选布局，以固定 AB/BA 配对为 400 个目标槽位，另有 50 个回测槽位。
T1 使用 RunDemo，T3 使用既有三段 RunComposite 交换；组件不充当独立成功样本。
输入通过历史 1mm 排除、物体/zone 间距约束和整链静态预检，没有 IK 或物理可靠性验收。

候选包清单 SHA256：
`3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f`。
原校准字节保留，身份仍为 `34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c`。
episode 文件集合/字节与已有预算字节在准备前后不变，覆盖拒绝后包摘要不变。
prepare/verify 明确返回 `sampling_authorized=false`、`ready_for_large_test=false`。

28 项新增针对性测试及 54 项既有离线仪器测试通过，共 82 项；它们不是机器人样本。
保留前后各次测试日志，以及格式化脚本语法错误和 Git 状态解析断言失败的开发记录。
两次开发命令都在相关操作前停止，随后明确纠正，未触发机器人或推理工作。
原有所有实录失败、校准、部署和封存包保持原样。

**公开候选为 PREPARED_NOT_RATIFIED，独立保管未建立。**
未记录的场景接触 UNKNOWN，不称盲留出集；统计假设、预算信封、NET-001、GRASP-B-001
仍待处理。v1 qualification、AC@90、n≥50 继续冻结，资格执行器未实现或调用。
实际账单和 GPU 成本 UNKNOWN；当前开发时间不能补造完整迁移成本。

```bash
cd /home/ros/agentic_workcell_ws
PYTHONDONTWRITEBYTECODE=1 python3 setup/132_qualification_prepare.py verify \
  --root setup/acceptance/qualification_inputs_20261007/inputs \
  --expected-sha256 3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f \
  --workspace /home/ros/agentic_workcell_ws \
  --history /home/ros/.ros/flexcell/episodes
```

`inputs/SHA256SUMS.json` 冻结候选包；本目录外层 `SHA256SUMS.json` 冻结全部回执、
日志和源码快照。包内 verify 无 ROS 或网络依赖。未来新增历史 episode 后外部历史复核
会拒绝沿用此快照；保留旧包并另建准备目录，不能覆盖。

详见 [准备入口与身份边界](../../../docs/QUALIFICATION_PREPARATION.md)。
