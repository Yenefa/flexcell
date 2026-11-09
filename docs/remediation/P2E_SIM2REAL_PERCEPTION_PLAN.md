# P2-E — Sim2Real 感知准备（设计边界与验证计划）

> **状态：边界已厘清并用测试固化；真实相机闭环 NOT_VERIFIED（无相机硬件）。**
> 本轮**不**构建多后端继承体系——没有硬件反馈时那只是空壳。

## 1. 当前两条路径

### 1.1 Gazebo Ground Truth 路径（生产默认）
- 实现：`common.sample_gz_pose` / `sample_gz_pose_age`，读 gz `Pose_V` 流；
- 出口：`observe_server._snapshot()` → `WorldState`，`ws.source = "SIMULATION_GROUND_TRUTH"`；
- 新鲜度：`pose_age_s` + P1-A 的 `world_sampled_monotonic`；
- 消费者：安全门（P1-C 顺序 + 新鲜度）、FSMPolicy、verify_server。

### 1.2 相机 / AprilTag 路径（已实现几何，未接入执行）
- 实现：`vision_geometry.py`、`visual_region_plan.py`；
- 能力：外参 → optical 系转换、标定校验、按**同一 stamp** 匹配 image/camera_info/detections/TF；
- 输出：`{"source": "VISION_APRILTAG", "objects": {...}}`；
- **约束（已用测试固化）**：纯几何，**不导入 rclpy / moveit / gz**，**不创建任何 ROS 实体**。

## 2. 数据边界（这是本轮的核心结论）

| 维度 | Ground Truth | 相机 |
| --- | --- | --- |
| 真值性 | **是物理真值**（仿真内部状态） | 估计值，有噪声与丢失 |
| 可用性 | 每步都有 | 可能整帧缺失（`tag_missing` / `tag_quality_invalid`） |
| 拒识原因 | 只在"流不流动"时失败 | **12 种类型化原因**（见 `observations()`） |
| 新鲜度 | `pose_age_s` 单调增长 | 由 `image.stamp_ns` 决定，与 ROS 时钟同域 |
| 允许用于验收 | **是** | **否**——验收必须独立于被检验的感知 |

**硬规则**：
1. **验收必须用真值**。相机估计不能自己给自己打分。
2. **相机路径不得写执行器**（测试 `test_perception_boundary.py` 强制）。
3. **仿真里这两条路径不得混用**：`composite.py` 已拒绝 `source != SIMULATION_GROUND_TRUTH` 的观测。
4. **不一致时刻的同域比较**：相机路径只接受同一 `stamp_ns` 的 image/camera_info/detections/TF，
   过期 TF 永远不会提供位姿。

## 3. 真机接入的验证条件（前置门）

接入真实相机前必须逐项满足：

1. **标定证据**：内参 `p[0],p[5] > 0`、畸变 `d` 已矫正（代码当前对非零畸变直接拒绝，要求先矫正）；
2. **外参来源可追溯**：`camera_sdf_pose` 必须来自实测或标定文件，不能沿用仿真值；
3. **AprilTag 质量门**：`hamming == 0` 且 `margin > 0` 才接受；
4. **时间同步**：image / camera_info / detections / TF 四者 stamp 一致；
5. **与真值对比**：在有真值参照的环境（仿真或标定板）中，逐个 tag 测量位姿误差分布，
   并记录 `p50/p95/max`；
6. **拒识率**：统计各 `reason` 的占比，`tag_missing` 过高说明视野/光照问题；
7. **失败可见**：任何不可用都必须带类型化 `reason`，不允许静默返回单位位姿。

以上 1–7 全部满足前，相机路径**不得**接入 `task_fsm` 的决策或验收。

## 4. 为什么本轮不建多后端

没有真实相机时，"多后端"只能对着仿真相机自证，属于**为了架构而架构**。
当前设计已经足够：
- `observe_server` 的 `source` 参数已把来源显式化；
- 视觉几何是**纯函数**，接入时只需一个把 `observations()` 结果映射成 `WorldState` 的适配层；
- 因此正确顺序是：**先拿到硬件 → 按 §3 收集误差证据 → 再决定适配层的形状**。

## 5. 本轮交付

| 项 | 状态 |
| --- | --- |
| 两条路径的边界 | **已厘清 + 测试固化**（`test_perception_boundary.py` 9 项） |
| 视觉几何只读性 | **已验证**（AST 扫描：不导入 rclpy/moveit/gz，不建 ROS 实体） |
| 同 stamp 匹配与拒识 | **已验证**（未匹配帧返回 `camera_info_unmatched`，不给位姿） |
| 真机验证计划 | **本文档 §3** |
| 真实相机闭环 | **NOT_VERIFIED**（无硬件） |

## 6. 下一步（需要硬件或授权）
1. 取得相机 + 标定板，跑 §3 的 1–5；
2. 在同一场景下同时记录真值与相机估计，产出误差分布对比；
3. 只有误差与拒识率被量化后，才设计适配层并接入 `observe_server`。
