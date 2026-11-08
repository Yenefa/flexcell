# 演示与佐证材料台账（可复跑）

> 均为**本机 WSL 原生 ROS/Gazebo（Mesa llvmpipe，无 GPU）** 实跑结果；不是云端单测替代。
> 机时：2026-11-08。源码 `main`（文档改动不影响运行包）。

## 构建
| 项 | 值 |
| --- | --- |
| 包 | 4 个（含 `flexcell_interfaces`/`flexcell_skills`/`flexcell_mtc` 等） |
| 命令 | `colcon build --merge-install --parallel-workers 6` |
| 用时 | 2m22s（U1/U2 后）；增量约 1m30s–2m |

## 单任务 smoke
| 场景 | 结果 | 落点误差 | 用时 | 运行时指纹 |
| --- | --- | --- | --- | --- |
| velocity_servo / normal / target_box_a | **PASS** | 0.514 mm | 15.9 s | `bccc9338…f96501` |
| 同上 + `--camera` | **PASS** | 10.85 mm | 22.8 s | `45daaaa0…c5285b` |

相机路径：`frames.jsonl` 442 帧、live 写 296（有效 209）、`reconcile` **RECONCILED** 回填 **146** 帧（软渲染慢、丢帧更多 → 对账在重负载下成立）。

## 核心 5 任务功能窗口
`scripts/sim_window.py --manifest infra/core-window.json --backend velocity_servo --skill-backend legacy` → **`FUNCTIONAL_WINDOW_PASS`**

| trial | case | 结果 | 落点误差 |
| --- | --- | --- | --- |
| 01 | normal A | PASS | 5.48 mm |
| 02 | normal B | PASS | 4.35 mm |
| 03 | dual_object | PASS | — |
| 04 | recovery_once | PASS | 9.32 mm |
| 05 | budget_exhaustion | EXPECTED_FAILURE | — |

`window_id=5e683f14557f4283a27e0e7896437e77`，declaration `49443988…af0eb`，全部 trial 指纹 `bccc9338…f96501`。

## composite（U3，创意"多任务链"能力）
- `RunComposite` 单 stage 链：**`OUTCOME_SUCCEEDED`**，`completed_stage_ids=["one"]`，`component_run_ids=["pick_place_v1-e813727b"]`，14.5 s。
- 同栈原路径回归：plain `sim_smoke` PASS，落点 11.30 mm，指纹 `60ffdbcb…`（composite 接入未扰动原路径）。

## CI
- `ci`（构建 interfaces+skills + 全部离线测试）与 `trusted-simulation`（全包构建 + native 四作业）在合并提交上均 **success**。


## 最新刷新（current main，2026-11-08）
在**当前 main 源码**上重新构建并跑核心 5 任务窗口：

| trial | 结果 | 落点误差 |
| --- | --- | --- |
| normal A | PASS | 7.47 mm |
| normal B | PASS | 2.78 mm |
| dual_object | PASS | — |
| recovery_once | PASS | 10.22 mm |
| budget_exhaustion | EXPECTED_FAILURE | — |

- `status=FUNCTIONAL_WINDOW_PASS`；`window_id=8b1c18af664c41d1bcf736c0745d0f66`。
- 统一运行时指纹：**`dd456b9b…accdbf790`**（含 composite 合并后的当前运行时；取代文档轮次前的旧指纹）。
- 说明：仍是一次有界功能窗口（n=1），非成功率。

## 相机 smoke（current main，2026-11-08）
- `sim_smoke --camera`（velocity_servo / normal / target_box_a）：**PASS**，落点 **5.25 mm**。
- 相机帧 **557**，有效 388，`reconcile=RECONCILED`，**回填 39** 帧。
- 运行时指纹 **`f04e37e2…`**（camera 配置独立于无相机的 `dd456b9b…`，属预期）。

## composite 探针（current main，2026-11-08）
- `composite_probe` 单 stage 链：**OUTCOME_SUCCEEDED**，`completed_stage_ids=["one"]`，`component_run_ids=["pick_place_v1-2f479ab1"]`，**14.6 s**。
- 构建指纹 `dd456b9b…`（与核心窗口同一当前构建）。
## 复跑命令（本机）
```bash
# 构建
rsync -a --exclude=.git <repo>/src/flexcell/flexcell_skills/ /home/ros/flexcell-u3/src/flexcell/flexcell_skills/
(按 scripts 里的 wsl_u3_build.sh 构建)
# 核心窗口
python3 scripts/sim_window.py --manifest infra/core-window.json --out /tmp/win --backend velocity_servo --skill-backend legacy
# 相机 smoke
python3 scripts/sim_smoke.py --out /tmp/cam --backend velocity_servo --case normal --object target_box_a --camera
# composite 探针
python3 src/flexcell/flexcell_skills/test/composite_probe.py --object target_box_a --place 0.12 -0.15 0.0175
```
