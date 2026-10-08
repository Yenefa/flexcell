# 私有候选暂存与公开摘要

`setup/134_qualification_private.py` 在本机 Git 工作树外生成新的 T1/T3 候选包，
仓库只收录 commitment 和验证回执。它排除全部可用历史双物体状态以及显式登记的公开候选包，
不调用 ROS、推理、reset 或原生 task。每个包仍有 200 个布局、450 个配对及回测槽位；
这些是输入数量，新增原生 episode 和模型调用均为零，n≥50 仍 FROZEN。

公开的旧候选包保留，不能改名作为留出集。新包使用操作系统随机种子；种子和新坐标只留在
私有目录，命令行没有 seed 参数。两个物体都在 1mm 内即视为场景重合。
只在写包之前因公开场景重合拒绝种子，最多 20 次；不按执行结果筛选，也不重采失败任务。
历史缺失或损坏、身份错配、公开包摘要变化均拒绝准备。

**私有本机暂存尚未建立独立保管，也不是已接受的盲留出集。**
底层沿用未修改的 schema-1 工具及其保守 `NOT_INDEPENDENT` 模板；其中“已公开”文字是旧模板，
新包的实际存储可见性由 commitment 的 `PRIVATE_UNPUBLISHED_STAGING` 明确记录。
场景接触记录不完整、IK/物理可达性未验证，正式协议和预算仍未核定。
当前运行的 fleet 可以是 FSM；`--deployment` 在这里仅提供冻结的 Hybrid 配置与模型身份，
不能用它证明当前 Hybrid 在线。

## 操作

只使用 WSL 权威目录。私有输出必须在 Git 树和 workspace 外，不能经过软链接或 `..`。
工具新建的私有父目录和包目录权限为 0700，包文件为 0600；若父目录已存在，需已有 0700 权限。
包和 commitment 任一已存在都会拒绝覆盖。不要将私有目录复制进仓库。

```bash
cd /home/ros/agentic_workcell_ws
python3 setup/134_qualification_private.py prepare \
  --out /home/ros/fc_sync_logs/qualification_private_20261008/inputs \
  --commitment setup/acceptance/qualification_private_20261008/commitment.json \
  --published /home/ros/agentic_workcell_ws/setup/acceptance/qualification_inputs_20261007/inputs \
    3bc42291a1ee7a4b60d69a376619dd4e7835604f73c83dc764fc50e361983a5f \
  --history /home/ros/.ros/flexcell/episodes \
  --deployment /home/ros/.local/share/flexcell/mainline/runtime/20261007_132145/deployment.json \
  --calibration /home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json \
  --familiar-inputs setup/acceptance/transferbench_t1_20261006/plan/initial_states.json \
  --budget /home/ros/.config/flexcell/deepseek_budget_20261001.json \
  --workspace /home/ros/agentic_workcell_ws --revision <完整feature实现提交SHA>
```

准备返回外部预期 commitment SHA；复核必须提供原值，不接受重新计算摘要替代它。
可重复添加 `--published ROOT SHA256`，登记其他曾公开的候选包。
复核需要本机私有包、公开排除包和当前源码、历史、校准、预算全部匹配。
仓库中的摘要不包含私有输入，其他机器仅凭仓库不能复算场景或复核私有包。

```bash
python3 setup/134_qualification_private.py verify \
  --commitment setup/acceptance/qualification_private_20261008/commitment.json \
  --expected-sha256 <prepare返回的commitment_sha256> \
  --workspace /home/ros/agentic_workcell_ws \
  --history /home/ros/.ros/flexcell/episodes \
  --calibration /home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json \
  --budget /home/ros/.config/flexcell/deepseek_budget_20261001.json
```

预算文件从未重置。任何新增历史、校准或预算变化都会拒绝沿用当前快照，原包和所有失败回执保留。
工具没有采样执行入口，输出永远 `sampling_authorized=false`、`ready_for_large_test=false`。
正式资格 ledger、独立保管和协议 ratification 仍需完成；现有三个 Hybrid 开发槽位继续等待 GPU 在线。
