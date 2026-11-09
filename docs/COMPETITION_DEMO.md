# 比赛演示 — W5 自主修复闭环（可复现）

> 目标：用**真实 Gazebo**演示"执行失败 → 读证据 → 改文件 → 目标验收 + 回归验收 → 独立判定"，
> 并能在无 API Key 时用离线回放复核全部记录。

## 1. 三分钟叙事
1. 工作区 `config/week1.yaml` 被注入缺陷：`zone_2_x=0.45`（机械臂可达 <0.30 m）；
2. 双对象任务在 `PLACE_B` 失败，normal 仍通过（回归基线）；
3. Agent（deepseek-chat）读 telemetry + config，用 `edit_file` 把 `zone_2_x` 改为 0.25；
4. `gate/acceptance.py` **独立**重跑真实 Gazebo：目标 `dual_object` + 回归 `normal` + `regrasp`；
5. 三门全 PASS 才记 verified improvement；任一回归失败即拒绝。

## 2. 离线回放（推荐给评委，零依赖）

```bash
python3 experiments/pilot-001/demo/replay.py
```

输出每条记录的迭代数/token/修改值/三门状态/result SHA；退出码非 0 表示有记录未通过。

## 3. 现场重跑（需要 Windows + WSL2 + Gazebo + API Key）

```powershell
$env:FLEXCELL_PILOT_API_KEY = "<key>"
pwsh -NoProfile -File experiments/pilot-001/demo/run_live_w5e2d.ps1
```

预期：3–5 轮、~3–5k tokens；输出目录 `demo-output/` 含 `result.json`、`events.jsonl`、`verdict.json`、`workspace/config/week1.yaml`。

## 4. 证据与协议
| 项 | 位置 |
| --- | --- |
| 协议（E2b/E2d） | `docs/W5E2B_PREREGISTRATION.md`、`docs/W5E2D_PREREGISTRATION.md` |
| 成功记录 | `experiments/pilot-001/runs/p1.5-w5e2b-20261109/`（3/3）、`p1.5-w5e2d-20261109/`（2/2） |
| 失败留档 | `runs/p1.5-w5e2-20261109/`（3 次失败 + transcript）、`p1.5-w5e2c-20261109/`（0/2） |
| 统计口径 | `docs/STATS_AUDIT.md` |
| 总状态 | `docs/PROJECT_STATUS.md` |

## 5. 边界（必须说明）
- 缺陷是**人工注入**的受控实验；不是自发发现；
- 单模型（deepseek-chat）；E2d 的"显式行动指令"是 prompt-level 干预，已在协议中披露；
- n=2–3，探索性；未做真机（M3-R）。
