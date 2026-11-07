# 用现成 Agent 操作 FlexCell（ROS-MCP）

使用上游 [ros-mcp-server](https://github.com/robotmcp/ros-mcp-server) 3.1.2，
通过 rosbridge 调用已有 ROS Action。MCP 的 Python 环境独立于 ROS，无需 GPU、
ASPIRE 或新增模型 API。先启动已有 FlexCell 仿真；以下命令不会启动、reset 或停止它。

## 1. WSL 终端：安装并启动桥接

在当前 FlexCell checkout 中执行。桥接进程的 **`ROS_DOMAIN_ID` 和
`RMW_IMPLEMENTATION` 都与当前仿真栈保持一致**。电脑端 `run105/run110` 已验证的
组合是 domain **46** + **CycloneDDS**；实际运行配置优先。

```bash
./scripts/ros_mcp.sh install
export ROS_DOMAIN_ID=46
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# 如果当前 install 不在本 checkout 的 install/，指定实际路径：
export FLEXCELL_ROS_SETUP=/home/ros/flexcell-merged/install/setup.bash
./scripts/ros_mcp.sh bridge
```

已有 ROS/install 环境的用户也可直接 source 后执行 `bridge`。
桥接只监听 WSL 的 `127.0.0.1:9090`；另选端口时设置 `FLEXCELL_MCP_PORT`。
启动日志会显示 domain 与 RMW。端口 OPEN 仅表示 WebSocket 已监听；若 Observe 超时，
先核对桥接与栈的 RMW、domain 和 install。现场曾出现同 domain 下桥接使用默认
FastDDS、栈使用 CycloneDDS，切到相同 RMW 后恢复 READY。
这些 ROS 配置属于桥接进程，Agent/MCP 客户端无需加载 ROS 环境。

### PyPI 下载慢时

可显式指定现场已可用的 Aliyun 镜像，同时打开安装器详细输出：

```bash
FLEXCELL_MCP_PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
FLEXCELL_MCP_VERBOSE=1 ./scripts/ros_mcp.sh install 2>&1 | tee /tmp/flexcell-mcp-install.log
```

这两个选项同时支持 uv 与 pip，只影响本次安装，不修改全局源。
不设置时沿用安装器原有源配置。OpenCV 等包较大，安装应允许数分钟并查看日志；
脚本没有为整个安装设置短超时，Action 的 150 秒超时不适用于依赖下载。

## 2. 另一个 WSL 终端：只读检查

```bash
./scripts/ros_mcp.sh check
```

应输出 `status: READY`、物体实测位置和区域信息。它核对三个自定义 Action，
只执行 Observe，**不会搬动机械臂**。连接失败时先检查 domain、仿真是否运行、
桥接进程的 RMW 是否匹配、是否 source 了当前 FlexCell install。

## 3. 接入现有 Agent

**WSL 中的 Codex CLI：**

```bash
./scripts/ros_mcp.sh codex
```

这会注册 `flexcell-ros` MCP，然后启动工具超时为 180 秒的 Codex。

**Windows WorkBuddy / Claude 等 MCP 客户端：**新增一个 stdio MCP，使用下面的配置，
把 checkout 路径及 WSL 用户名替换为实际值：

```json
{
  "mcpServers": {
    "flexcell-ros": {
      "command": "wsl.exe",
      "args": ["-u", "ros", "--", "bash", "-lc",
        "exec /home/ros/agentic_workcell_ws/scripts/ros_mcp.sh server"]
    }
  }
}
```

在客户端把工具超时设为至少 180 秒。支持该设置的名称以客户端为准。
Linux/WSL 原生客户端的 command 直接使用本 checkout 的 `scripts/ros_mcp.sh`，args 为 `["server"]`。
自定义端口时先让 Agent 调用 `connect_to_robot(ip="127.0.0.1", port=实际端口)`。

### 启用水平放置的三物体相机场景

#122 的水平放置功能可通过统一 profile 入口启用。生成器会把同一个角度限值传给
MTC 规划器和释放门禁；超过限值时保持夹持并报告失败。需要仿真机已构建当前源码，
使用 `mtc` 技能和 `detachable_joint` 搬运后端。

在已 source ROS 及当前 FlexCell install 的终端中执行：

```bash
export ROS_DOMAIN_ID=46
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export GZ_PARTITION=flexcell-camera-level
python3 scripts/sim_profile.py --out /tmp/flexcell-camera-level \
    --backend detachable_joint --skill-backend mtc \
    --camera --scene tagged_three_boxes --level-release-tolerance-deg 5
ros2 launch flexcell_skills trusted_sim.launch.py \
    world:=/tmp/flexcell-camera-level/world.sdf \
    params_file:=/tmp/flexcell-camera-level/params.yaml camera:=true
```

生成命令只写入新的 `params.yaml`、`world.sdf` 和 `vision.json`，并输出它们的 JSON
路径，不启动机器人。已有文件会拒绝覆盖；每次实验使用新目录。桥接终端沿用相同的
domain、RMW 和 install，再按上文启动 ROS-MCP。后续 Action 调用方式相同。

不传 `--level-release-tolerance-deg` 时保留原默认配置。该入口的配置和 CLI 已做离线
验证；#122 的物理窗口是两物体固定点测试，三物体相机场景的整链搬运需单独实跑。

## 4. 发给 Agent 的第一条指令

> 使用 flexcell-ros MCP 连接 127.0.0.1:9090。先读取本仓库 docs/ROS_MCP.md，
> 查询 Action 类型并观察场景。确认目标空闲后，把 target_box_a 放到 world 坐标
> (0.12, -0.15, 0.0175)，target_box_b 保持任务开始时的位置。
> 目标被占或无法确认空闲就停止报告。由你决定下一步，完成后分别独立验证两个物体；
> 已到目标就验证，动作失败或终态未知就停止并报告。

执行前观察当前场景，不假设旧坐标仍成立；已在目标处则只验证。

Agent 调用规则：

- 通过 `/observe`、`/run_pick_place`、`/verify_object` 操作，先用
  `get_action_details` 查看真实字段；一次只派发一个任务。
- 搬运 Goal 的 `place_pose.header.frame_id` 为 `world`，四元数 `w=1`，
  `motion_profile_id="demo_slow"`，`skip_verify=false`。
- `/run_pick_place` 和 `/run_demo` 在 PICK 前按 Observe 中所有箱体的实测几何
  检查目的地；被占返回 `ERR_SAFETY_REJECTED`，detail 含
  `destination_occupied:物体名`。几何不可用也拒绝。此检查保守包络搬运物体的
  可能转角，可能拒绝紧邻放置；它不保证沿途避障，也不覆盖直接调用底层 Pick/Place。
- `send_action_goal` **显式指定 `timeout=150`**，上游默认仅 5 秒。
  不自动重发已接受或接受状态未知的 Goal。
- 返回 `success=true` 只说明收到 Action 结果。搬运需要嵌套 `result.outcome==0`、
  `error_code==0` 和 `object_at_place==true`。最终分别调用 VerifyObject，容差沿用
  **0.06 m**，要求 `outcome==0`、`verified==true`、`has_measured_pose==true`，
  并读取实际 `position_error_m`。
- 取消请求已发出不等于终态已确认。未知终态后停止后续运动、reset 和清理运动。
- Agent 选择任务与工具，现有技能负责运动规划、执行和实际验证。
  不通过直接发布关节命令、修改碰撞场景或 set_pose 绕过技能。

### 三物体场景（可选）

默认 profile 仍是两物体。需要三物体时，用 `scene="three_boxes"` 生成独立
profile；它会加入 `target_box_c`，并把对象集声明给 Observe、Pick、Place、Carry、
MTC 与物理守卫。使用独立的 `ROS_DOMAIN_ID`、`GZ_PARTITION` 和桥接端口，
不要覆盖已有的两物体运行：

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, '/home/ros/agentic_workcell_ws/scripts')
from sim_profile import profile
profile('/home/ros/run116/profile', backend='detachable_joint',
        skill_backend='legacy', decision_policy='fsm', scene='three_boxes')
PY
```

可直接发给 Agent 的用户目标：

> 先观察并记住 A、B、C 的实际起始位置。把 A 放到 B 的起始位置，B 放到 C 的
> 起始位置，C 放到 A 的起始位置。目标互相占用时，由你决定顺序并选择空闲暂存
> 位置。完成后暂存位置应为空，三个箱体身份不能互换。每只箱体距各自指定目标
> 不超过 10 mm；朝向不作要求。

约束：最多 6 次 `/run_pick_place`（含被拒绝的调用）；每次搬运后独立核对全部
三个物体，非目标物体位移 ≤1 mm；全程同一世界，不 reset、不 set_pose。未运动
且无抓持的拒绝可调整暂存选择；实际运动失败或终态未知则停止并保留现场。

### 相机图像选物（#114）

用 `profile(..., scene='three_boxes', camera=True)` 生成带相机的 profile，启动时加
`camera:=true`。图像在 `/flexcell/camera/rgb`，标定在
`/flexcell/camera/rgb/camera_info`；后者由本仓库桥接 gz 的真实
`/flexcell/camera/camera_info` 并 remap 到文档话题（见 PR #116）。

```python
# 通过 ROS-MCP 的 stdio 客户端调用；图像会保存到 MCP 服务进程的
# ./camera/received_image.jpeg，下一次调用会覆盖，需立即复制到独立文件名。
subscribe_once(topic='/flexcell/camera/rgb', msg_type='sensor_msgs/msg/Image',
               expects_image='true', timeout=20)
subscribe_once(topic='/flexcell/camera/rgb/camera_info',
               msg_type='sensor_msgs/msg/CameraInfo', expects_image='false', timeout=15)
subscribe_once(topic='/clock', msg_type='rosgraph_msgs/msg/Clock',
               expects_image='false', timeout=10)
view_saved_image(image_path='./camera/received_image.jpeg')
```

选物流程：先 Observe 取得各箱体三维位置，再用 CameraInfo 的 K 与 profile 的
`dataset_camera` 外参把中心投影到图像，在投影点邻域统计绿色像素；最高且唯一者
作为目标。不要从 SDF 材质表或固定坐标决定“绿色是哪只”，也不要写死绿色=某个 ID。
zone_1 本身也是绿色半透明圆盘，按“投影到实体箱体中心”匹配可将其排除。

已验证（一次功能演示）：颜色 fixture 为 A=绿/B=蓝/C=红，图像唯一命中 A；A→zone_1
一次搬运误差 2.536 mm，B/C 位移 2.5e-9 m；最终 health 19/19、IDLE、carry=false。
三维位置来自 Observe 的 `SIMULATION_GROUND_TRUTH`，因此结论是“视觉选物 + Observe
定位 + 已有技能搬运”，不是纯视觉三维定位；n=1，不是成功率。

## 5. 每个 Action 的实际结果字段

`get_action_details` 返回字段定义；实际值来自 `send_action_goal` 的返回。
Python MCP SDK 优先读取 `reply.structuredContent`，没有时解析 `reply.content` 的
text JSON，然后读取其中的 **`result`**。若这个 `result` 是 JSON 字符串，先解析一次。

在仓库根目录运行的 Python 客户端可复用现有解码函数：

```python
from scripts.ros_mcp_check import tool_value, action_fields

payload = tool_value(reply)  # reply = await session.call_tool(...)
fields = action_fields(payload)
```

| Action | `fields` 中的实际字段 | 完成判断 |
| --- | --- | --- |
| Observe | `outcome`, `error_code`, `world_state` | outcome/error_code 为 0，读取可用物体的实测位姿 |
| RunPickPlace | `outcome`, `error_code`, `object_at_place`, `final_position_error_m`, `detail` | outcome/error_code 为 0 且 object_at_place 为 true |
| VerifyObject | `outcome`, `error_code`, `verified`, `has_measured_pose`, `position_error_m`, `measured_pose` | outcome/error_code 为 0、verified 与 has_measured_pose 为 true，误差为有限值且在容差内 |

VerifyObject Goal 的 `expected_pose` 是 **Pose**：直接包含 `position` 与 `orientation`，
不再包一层 `pose` 或 `header`。容差字段是 `position_tolerance_m=0.06`。
现场一次“验证字段为 null”已定位为 Goal 字段传错；应先修正 Goal，再检查结果解码。

例如 VerifyObject 的布尔值在标准结构中是
`reply.structuredContent["result"]["verified"]`，不是
`reply.structuredContent["verified"]`；JSON 字符串结果按上面先解码。
字段缺失或实际为 null 时保留原始返回并报告“验证结果无法读取”，不能默认当作
false 或 true，也不能为重新取得报告而重复已完成的搬运动作。

## 6. 已验证范围

电脑端在相同目标 A→zone_1 下，CLI 与 MCP 的最终独立验证均通过，B 均保持原位。
报告中的 CLI 15.53 s / 2.423 mm、MCP 14.94 s / 2.229 mm 是单次读数，
不足以推断速度或精度的统计差异。首次 MCP 试跑因验证解析失败，虽然物体已搬到目标，
仍应作为额外试跑计入并保留记录，不能被后续报告完整的一次覆盖。

目前已验证的是等价 stdio 客户端的 MCP 链路。WorkBuddy 配置已由电脑端写好，
连接器面板的 Trust 和第一次 UI 调用仍由本机用户确认，不能据 stdio 成功宣称 UI 已通过。
日常任务优先使用 MCP；排障仍可使用 CLI、`skills/*.jsonl` 与 ROS 日志。

修复前，电脑端报告同一配置中首次搬运 12/12 成功，二次抓取 5/5 在 PLACE hover
失败；另有目标被占却推开非目标物体的反例。#107 保留实测四元数、绑定前刷新姿态、
放置后同步实测场景，并增加上述占用拒绝。多步操作是否恢复，仍需同一世界的三步交换
和全物体验证证明；离线回归或首次搬运成功不能替代这项现场验证。

三物体配置驱动已在电脑端完成一次现场验收（`detachable_joint + legacy + fsm`，
domain 56 / 桥接 9096，同一世界、无 reset / set_pose）：Observe 从开始即返回
A、B、C；每次 PICK 前 `pick.jsonl` 的 `scene_synced` 都包含其余全部箱体
（包括尚未搬过的 C），`scene_sync_skipped=[]`。Agent 选择 A→暂存
(0.12, −0.15)、C→A 原位、B→C 原位、A→B 原位，共 4 次 `RunPickPlace`，
全部 `outcome=0 / error_code=0 / object_at_place=true`；每步非目标物体
Δxyz ≤1e-5 m。另用第 5 次调用把 A 指向 C 当前占用点，0.09 s 内被
`ERR_SAFETY_REJECTED=53` 零运动拒绝，detail 为
`destination_occupied:target_box_c`。最终独立 VerifyObject：A 2.445 mm、
B 3.281 mm、C 0.749 mm，均 ≤10 mm；暂存点已清空，最终 health 19/19、
IDLE、carry=false。
这是 n=1 的功能演示，不是成功率或统计结论。默认两物体行为、历史 profile
哈希与原有场景序列保持不变；三物体场景必须通过 `scene="three_boxes"` 显式启用。

## 7. 可选：用现成 AprilTag 做只读三维定位（#115）

使用 [christianrauch/apriltag_ros](https://github.com/christianrauch/apriltag_ros)
及官方 AprilRobotics 标记，CPU 即可。它与 MCP 搬运入口独立；输出不会替换 Observe，
也不进入 Pick/Place。以下模式仅启动箱体、相机、桥接和检测节点，没有机械臂或控制器。
需要 Jazzy + Gazebo Harmonic；相机桥接包含 #116 的 CameraInfo 修复。

```bash
sudo apt-get install ros-jazzy-apriltag-ros ros-jazzy-cv-bridge \
  ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge python3-opencv
source /opt/ros/jazzy/setup.bash
colcon build --base-paths src/flexcell/flexcell_skills --packages-select flexcell_skills
source install/setup.bash
export ROS_DOMAIN_ID=63                 # 所有相关终端一致，避开正在工作的栈
export GZ_PARTITION=flexcell-vision-115  # 所有相关终端一致，隔离其他 Gazebo 世界
export FLEXCELL_VISION_RUN=$(mktemp -d /tmp/flexcell-vision-115.XXXXXX)
printf '%s\n' "$FLEXCELL_VISION_RUN"
python3 - "$FLEXCELL_VISION_RUN/profile" <<'PY'
import sys
from scripts.sim_profile import profile
profile(sys.argv[1], backend='detachable_joint', scene='tagged_three_boxes',
        camera=True, perception_only=True)
PY
ros2 launch flexcell_skills apriltag_readonly.launch.py \
  calibration:="$FLEXCELL_VISION_RUN/profile/vision.json" \
  world:="$FLEXCELL_VISION_RUN/profile/world.sdf"
```

另一个同 ROS 环境/domain/partition 的终端，将 `FLEXCELL_VISION_RUN` 指向上一步
打印的实际目录，然后执行。无 GPU 的云端可在启动前执行
`export LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless`。

```bash
python3 scripts/apriltag_capture.py \
  --calibration "$FLEXCELL_VISION_RUN/profile/vision.json" \
  --out "$FLEXCELL_VISION_RUN/capture" --frames 5
```

已有带标记相机栈时，省略 launch 的 `world` 参数，仅接入检测和固定相机 TF。
本配置使用可靠 QoS，RGB 与 CameraInfo 的上游发布者也须为 RELIABLE；
标准 parameter_bridge 默认符合。云端大图曾在 best-effort 传输中丢失，不能补帧掩盖。
已实际运行 Jazzy `apriltag_ros` 3.4.0、AprilTag 3.4.5。
三个 ID 0/1/2 对应 A/B/C；黑色标记边长 25 mm，含白边 visual 31.25 mm，
标记平面高于箱体中心 17.7 mm。新场景使用 1280×960、2 Hz 斜上方相机及真实外参，
原有无标记颜色场景及默认世界不变。纹理按上游推荐作 nearest-neighbor 等值放大；
直接使用 10 像素原图会因渲染插值而模糊。

`vision.json` 只含相机标定和 tag→中心几何，不含箱体 world 真值。
读取器先等待元数据端 DDS 发现并收到首条 CameraInfo，再订阅 RGB、取最先收到的五张不同时间戳画面，
启动不以检测成功或 tag 可见为条件。保存 PNG 与 `observations.json`，
逐物体输出 `available/reason/world_center_m`，坐标单位为米，来源 `VISION_APRILTAG`。
RGB/CameraInfo/检测/TF 必须同帧；丢检、重复匹配、旧 TF、无标定或畸变未校正均不可用，
不可用项没有坐标。需要畸变校正时应先复用 image_proc；当前仿真相机无畸变。

`OBSERVATIONS_AVAILABLE` **仅表示五帧数据齐全，不表示定位达标**；
报告固定保留 `accuracy_assessed=false`。独立比较端另取静止箱体真值，计算每帧三维
误差，再按 ≤10 mm 验收；真值不能输入上述节点或读取器。保留失败画面，不补帧替换。
这是有标记、已知尺寸物体的定位验证；10 mm 目标也不构成运动授权，
不放宽现有 2 mm / 1° 附着一致性门禁。
