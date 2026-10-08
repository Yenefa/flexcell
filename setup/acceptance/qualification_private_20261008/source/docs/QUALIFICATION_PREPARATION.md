# 批测候选输入准备

TB-PREP-001 延续 [RFC #15](https://github.com/Yenefa/flexcell/issues/15) 的实验准备工作。
`setup/132_qualification_prepare.py` 已实现离线 `prepare` / `verify`；它写出可复核的候选包，
不创建 ROS node、不调用模型、不 reset、不运行原生 task。
后续[受限执行器](BOUNDED_RUNNER.md)可独立登记并执行六个开发槽位；正式 n≥50 资格采样仍冻结。

每个包固定 T1、T3 各 100 个不同候选布局。同一 case 的 FSM/Hybrid 使用相同输入，
以 AB/BA 交替顺序配对，每 20 对各有 10 个 AB 和 10 个 BA。每 20 对之后插入源任务回测：
T1 回测 S1；T3 回测 S1、既有两份熟悉 T1 布局和 canonical 布局。
总清单为 400 个目标逻辑任务和 50 个回测槽位；目标原生 episode 计划数为 800。
这些数字是输入清单大小，实际新原生 episode 和模型调用均为 0。

T1 仍使用既有 RunDemo 双物体任务；T3 使用 RunComposite 的固定三段交换。
T3 的三个组件不是三个独立成功样本。布局通过整链静态预检，IK、抓取物理和成功率均未评估。
几何取 canonical 周围 ±25mm，物体间距至少 120mm，距 zone 中心至少 50mm；
使用 SHA256 流生成，排除与可用历史双物体状态以及本包其他候选同时在 1mm 内的布局。
历史输入无法读取、重复 JSON 键和非有限数都会拒绝准备，不静默忽略失败记录。

**候选包公开在仓库，独立保管尚未建立，不能称为盲留出集。**
后续[私有候选入口](PRIVATE_QUALIFICATION_INPUTS.md)在 Git 树外另建包，排除公开候选和最新历史，
仓库只保留摘要；它仍不建立独立保管、不授权采样，也不覆盖此处的公开原包。
扫描只覆盖已记录且可比较的双物体状态，未记录的场景接触未知。
正式评估前需确定独立保管、统计假设与成功谓词、预算、NET-001 和 GRASP-B-001 的处理。
既有 ¥5 预算不重置；包记录当前预算文件摘要、既有调用 ID 及已承诺上界，
新增 ¥0.25 是累积边界停止阈值，实际账单和 GPU 成本仍 UNKNOWN。

## 准备与复核

在 WSL 权威目录运行；`--revision` 填写包含准备工具的 Windows feature 完整提交 SHA，
不是 WSL checkout 的旧 Git HEAD。当前部署、校准及源文件必须匹配，输出目录存在即拒绝覆盖。

```bash
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 setup/132_qualification_prepare.py prepare \
  --out setup/acceptance/qualification_inputs_20261007/inputs \
  --history /home/ros/.ros/flexcell/episodes \
  --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261007_132145/deployment.json \
  --calibration /home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json \
  --familiar-inputs setup/acceptance/transferbench_t1_20261006/plan/initial_states.json \
  --budget "$FLEXCELL_LLM_BUDGET_FILE" \
  --workspace /home/ros/agentic_workcell_ws \
  --revision <完整feature提交SHA> --seed 2026100701
```

保存 prepare 返回的 `package_sha256`，复核时必须提供这个外部预期值。
只改清单再重算包内 hash 不能通过旧摘要；重新封存的错序或解锁标记也会被语义复算拒绝。
校准快照保留原始字节，部署指纹、配置摘要和源码集合一起固定；增加未登记源码也会拒绝。

```bash
python3 setup/132_qualification_prepare.py verify \
  --root setup/acceptance/qualification_inputs_20261007/inputs \
  --expected-sha256 <prepare返回的package_sha256> \
  --workspace /home/ros/agentic_workcell_ws \
  --history /home/ros/.ros/flexcell/episodes
```

省略 workspace/history 只做包内复核，报告会明确对应外部验证为 false。
历史新增或已有字节改变会拒绝沿用旧包；旧包保留，需另建准备目录，不能覆盖。
`frozen_package_ok=true` 只证明候选包可复核，`sampling_authorized` 和
`ready_for_large_test` 永远为 false。v1 成本账本仍拒绝 qualification。

[本机准备证据](../setup/acceptance/qualification_inputs_20261007/README.md)
记录原始扫描、CLI 输出、文件封存和离线测试；没有追加机器人样本。
