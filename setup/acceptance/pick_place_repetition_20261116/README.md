# velocity_servo 抓放重复性：五次有界运行

这五次运行回答一个问题：同一个抓放任务、同一个世界、同一个后端，重复跑五次，
是否每次都闭环。**不回答**成功率、泛化、夹持力或摩擦。

执行源码：`fbf6245`（工作树另含本分支 `feat/offline-triage-20261116` 的脚本改动；
原生插件由该工作树构建，安装于 merge-install 的 `install_merged`）。
主机：WSL2 Ubuntu 24.04，ROS 2 Jazzy，Gazebo（gz vendor），MoveIt 2.12.4。
每跑一次是一道有界任务、一次尝试、不做替换、不做模型调用。

| 运行 | 状态 | FSM | 末位误差 | 物理行数 |
|---|---|---|---|---|
| PHYS-1 | PASS | `PICK_A:OK / PLACE_A:OK / VERIFY_A:OK` | **4.065 mm** | 2,735 |
| PHYS-2 | PASS | 同上 | **12.258 mm** | 2,781 |
| PHYS-3 | PASS | 同上 | **2.195 mm** | 2,665 |
| PHYS-4 | PASS | 同上 | **6.863 mm** | 2,683 |
| PHYS-5 | PASS | 同上 | **9.873 mm** | 2,551 |

容差 60 mm。五次最大值 12.258 mm，最小值 2.195 mm。

## 这组证据能支撑什么

五次运行都是 `velocity_servo`：世界插件对物体施加逐步的位置与速度约束，重力打开，
物理步真实推进。所以"末位误差"是在引擎里走出来的，不是把物体摆过去算出来的。

每次的 `data/physics.jsonl` 是物理插件逐步写下的引擎记录（20 ms 窗口、5 ms 内步），
`result.json` 是任务层的 RESULT。两者都在这里，可以独立复核。

## 这组证据不能支撑什么

- **不是成功率**：五次是同一场景的重复，不是样本矩阵；没有对照组，没有替换规则，
  没有置信区间。它只能说"这五次都闭环"。
- **不涉及夹持力**：五次运行的 `contact_force_observed` **每一行都是 false**，
  `joint_component` 也是 false。这条任务链不测接触力，所以 PASS 对夹持力、
  摩擦、滑移没有任何说法。
- **不是 `teleport` 后端**：`teleport` 的 PASS 只是参照，不计入物理证据。
- **不代表 `detachable_joint`**：那个后端是独立档案，结论仍是 `NO_GO`。

## 关于 rosbag 的排除（明说）

每个运行目录都保留了 `data/physics.jsonl`、`result.json`、`world.sdf`、
`params.yaml`、`identity.stdout`、`skills/` 与 `episodes/`，
但**排除了 `data/raw/`**（rosbag 的传输副本，五次合计约 45 MB）。

代价要说清楚：**这些运行无法从 bag 重放了**。保留的引擎级证据是
`physics.jsonl`（物理插件自己写的逐步记录），本任务链没有相机（`frames.jsonl` 为空），
所以 bag 里没有 physics.jsonl 之外的新事实。如果将来需要逐消息重放，这五次得重跑。

## 复核方式

```bash
python3 - <<'EOF'
import json, hashlib
from pathlib import Path
archive = Path('setup/acceptance/pick_place_repetition_20261116')
recorded = json.loads((archive / 'results.json').read_text())
for run in recorded['runs']:
    root = archive / 'runs' / run['label']
    for name, key in [('result.json', 'result_sha256'),
                      ('data/physics.jsonl', 'physics_sha256'),
                      ('world.sdf', 'world_sha256'),
                      ('params.yaml', 'params_sha256')]:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        assert digest == run[key], (run['label'], name)
    result = json.loads((root / 'result.json').read_text())
    assert result['status'] == run['status']
    assert abs(result['task']['final_position_error_m'] - run['final_position_error_m']) < 1e-12
print('all five runs match results.json')
EOF
```

`results.json` 里每条都带 `result_sha256` / `physics_sha256` / `world_sha256` /
`params_sha256`，任一文件被替换都会对不上。

## 与既有档案的关系

PHYS-1 与 PHYS-2 此前已在 `docs/diagnosis/CARRY_BACKEND_PHYSICAL_20261116.md` 里
以数字形式引用（4.07 / 12.26 mm），但**运行目录没有归档**，那份文档也自述
`n = 2 per backend`。本档案补齐了 PHYS-3/4/5 的目录，并把五次集中在一处，
使 `n = 5` 从会话内的口头声称变成可核记录。

本档案不修改任何冻结证据、不改变任何阈值，也不是正式封存盲测。
