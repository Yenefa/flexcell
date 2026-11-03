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

## 4. 发给 Agent 的第一条指令

> 使用 flexcell-ros MCP 连接 127.0.0.1:9090。先读取本仓库 docs/ROS_MCP.md，
> 查询 Action 类型并观察场景。把 target_box_b 放到 world 坐标 (0.22, 0, 0.0175)，
> target_box_a 保持任务开始时的位置。由你决定下一步，完成后分别独立验证两个物体；
> 已到目标就验证，动作失败或终态未知就停止并报告。

这是 `run105` 后可接续尝试的指令；实际执行前仍要观察当前场景，不假设旧坐标仍成立。

Agent 调用规则：

- 通过 `/observe`、`/run_pick_place`、`/verify_object` 操作，先用
  `get_action_details` 查看真实字段；一次只派发一个任务。
- 搬运 Goal 的 `place_pose.header.frame_id` 为 `world`，四元数 `w=1`，
  `motion_profile_id="demo_slow"`，`skip_verify=false`。
- `send_action_goal` **显式指定 `timeout=150`**，上游默认仅 5 秒。
  不自动重发已接受或接受状态未知的 Goal。
- 返回 `success=true` 只说明收到 Action 结果。搬运需要嵌套 `result.outcome==0`、
  `error_code==0` 和 `object_at_place==true`。最终分别调用 VerifyObject，容差沿用
  **0.06 m**，要求 `outcome==0`、`verified==true`、`has_measured_pose==true`，
  并读取实际 `position_error_m`。
- 取消请求已发出不等于终态已确认。未知终态后停止后续运动、reset 和清理运动。
- Agent 选择任务与工具，现有技能负责运动规划、执行和实际验证。
  不通过直接发布关节命令、修改碰撞场景或 set_pose 绕过技能。

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

本入口不修复 #104 的第三次放置几何错误。任务能否完成仍以本次实际结果为准。
