# W5 自改进 — 可复现演示

## 1. 离线回放（无需 API Key / Gazebo）

```bash
python3 experiments/pilot-001/demo/replay.py
```

输出：每条记录的迭代数、token、修改后的 `zone_2_x`、目标门/回归门状态、result SHA；
任一记录不是 PASS 则退出码非 0（演示同时是校验）。

## 2. 现场重跑（需要 Windows + WSL + Gazebo + API Key）

```powershell
$env:FLEXCELL_PILOT_API_KEY = "<your key>"
pwsh -NoProfile -File experiments/pilot-001/demo/run_live_w5e2d.ps1
```

脚本会：1) 在工作区注入缺陷 `zone_2_x=0.45`；2) 让 deepseek-chat agent 读证据并修改；
3) 由 `gate/acceptance.py` 独立跑真实 Gazebo 判定目标 + normal + regrasp 三门；
4) 把结果写到 `demo-output/`。

## 3. 结果解读
- `target` = dual_object 场景；`regression_normal`/`regression_regrasp` = 既有能力回归；
- **只有三门全 PASS 才算 verified improvement**；任一回归失败即拒绝该改进；
- 记录与协议：`docs/W5E2D_PREREGISTRATION.md`、`docs/W5E2B_PREREGISTRATION.md`。
