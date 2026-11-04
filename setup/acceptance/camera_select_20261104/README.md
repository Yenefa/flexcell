# 看图选物 + Observe 定位 + 已有技能搬运（#114）

日期：2026-11-04。代码：合并后的 main `f85e0ab`（#113），加相机信息接线分支
`fix/camera-info-bridge`（PR #116；本轮现场使用该分支）。场景：`three_boxes` +
`camera=True`，`detachable_joint + legacy + fsm`，domain 58 / bridge 9098，
独立 profile，同一世界，无 reset / set_pose。

## 相机信息缺口与修复

`gz` 相机把 `CameraInfo` 发布在 `/flexcell/camera/camera_info`，而 launch 桥接的是
`/flexcell/camera/rgb/camera_info`；后者没有 gz 发布者，`ros2 topic hz` 与
MCP `subscribe_once` 都超时。最小修复（PR #116）：桥接真实的 gz topic，并用 ROS
remap 保持公开话题 `/flexcell/camera/rgb/camera_info` 不变。修复后实测
`K=[467.7427, 0, 320; 0, 467.7427, 240; 0, 0, 1]`，640×480，frame
`dataset_camera/camera_link/rgb`。

## 颜色 fixture

为验证选择跟随画面而不是写死绿色=C，启动前只改 visual 颜色：A=绿、B=蓝、C=红
（默认 A=红、B=蓝、C=绿）。名称、初始位置、质量、碰撞几何不变；执行逻辑不读取
颜色→ID 表。记录见 `fixture-colors.json`。

## 图像选物

图像由 ROS-MCP `subscribe_once(topic='/flexcell/camera/rgb', expects_image='true')`
采集；CameraInfo 由同一 MCP 工具从 `/flexcell/camera/rgb/camera_info` 读取；
`/clock` 在采图前后各读一次。Observe 提供三只箱体的三维位置。用 CameraInfo 的 K
和 profile 相机外参（`dataset_camera` pose，RPY）把三个实测中心投影到图像；在投影
点周围 21×21 像素统计绿色掩码占比，最高且唯一者被选中。

| 物体 | 投影 (u,v) | 绿色占比 | 采图前图像 BGR | 结果 |
| --- | --- | --- | --- | --- |
| target_box_a | (351.73, 273.35) | **0.998** | (125, 181, 108) | **选中（绿）** |
| target_box_b | (262.84, 331.72) | 0.000 | (206, 134, 104) | 蓝 |
| target_box_c | (299.79, 269.54) | 0.000 | (109, 118, 205) | 红 |

绿色连通域只有一个：质心 (351.21, 272.62)，面积 763 px，距 A 投影 0.9 px。
zone_1 的投影为 (241.90, 293.62)，21×21 绿色占比 0.000；它是半透明绿色圆盘，
不与箱体绿色分量竞争，按投影匹配排除。采图前图像 16916 B，SHA256
`afd6b1d7635ffb7d055038f71655427410355d0729565f4c03f7f63dfcd6feca`，
仿真时间 77.495–77.950 s。

## 一次搬运

Goal：`target_box_a` → zone_1 `(0.12, −0.15, 0.0175)`，`demo_slow`，
`skip_verify=false`，`timeout=150`。全程仅此 1 次 `RunPickPlace`，无重试、无内建恢复。

| 项 | 结果 |
| --- | --- |
| 返回 | `outcome=0 / error_code=0 / object_at_place=true`，15.59 s |
| A 落点误差 | **2.536 mm**（≤10 mm） |
| B 位移 | **2.5e-9 m**（≤1 mm） |
| C 位移 | **2.5e-9 m**（≤1 mm） |
| 最终独立 Verify | A 2.525 mm、B 2.5e-9 m、C 2.5e-9 m，均 verified / measured |
| 最终位置 | A (0.12136, −0.15214)、B (0.20, −0.18)、C (0.15, −0.05) |
| zone 状态 | zone_1 被 A 占用；zone_2 空闲 |
| 最终 health | 19/19、IDLE、carry=false、hard_fail=[] |

采图后图像 13957 B，SHA256
`3dd5a9416aa3251dceb3f89558fec7d4be6fd05b42fa901b90c8afae4a159348`，
仿真时间 158.28–158.74 s；A 投影到 (241.44, 294.78)，绿色占比 1.0，仍在图像中
被识别为同一绿色箱体；B/C 的投影颜色与绿色占比不变。

## 结论与边界

结论是“**视觉选物 + Observe 定位 + 已有技能搬运**”。本轮只证明一次图像选物与一次
搬运的功能闭环，不是成功率，也不是纯视觉三维定位：三维位置仍来自 Observe 的
SIMULATION_GROUND_TRUTH，视觉只负责从画面里选绿色箱体。现场使用 legacy 后端；
MTC / velocity-servo 的 C 路径仍只做构建/配置验证。相机信息接线修复在 PR #116，
当前 GitHub CI 因账户付款/额度门禁在 0 step 失败，与本改动无关；本地相关 26 项
测试通过。

## 产物

- `before.jpeg` / `after.jpeg`：前后真实 RGB 帧。
- `select-before.annotated.png` / `select-after.annotated.png`：投影、绿色掩码与选中标注。
- `camera_info-before.json` / `camera_info-after.json`、`select-*.json`、`observe-*.json`。
- `verify-target_box_*.json`、`health-final.log`、`fixture-colors.json`。
- `profile-world.sdf` / `profile-params.yaml`：本轮 opt-in 场景（颜色已调整）。
- `pick.jsonl` / `place.jsonl` / `verify.jsonl`、`move-target_box_a.json`。
