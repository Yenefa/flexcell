# 用现成 Agent 操作 FlexCell（ROS-MCP）

使用上游 [ros-mcp-server](https://github.com/robotmcp/ros-mcp-server) 3.1.2，
通过 rosbridge 调用已有 ROS Action。MCP 的 Python 环境独立于 ROS，无需 GPU、
ASPIRE 或新增模型 API。先启动已有 FlexCell 仿真；以下命令不会启动、reset 或停止它。

## 1. WSL 终端：安装并启动桥接

在当前 FlexCell checkout 中执行。`ROS_DOMAIN_ID` 必须与仿真一致，
例如电脑 Agent 的 `run105` 使用 **46**。当前实际运行的 domain 优先。

```bash
./scripts/ros_mcp.sh install
export ROS_DOMAIN_ID=46
# 如果当前 install 不在本 checkout 的 install/，指定实际路径：
export FLEXCELL_ROS_SETUP=/home/ros/flexcell-merged/install/setup.bash
./scripts/ros_mcp.sh bridge
```

已有 ROS/install 环境的用户也可直接 source 后执行 `bridge`。
桥接只监听 WSL 的 `127.0.0.1:9090`；另选端口时设置 `FLEXCELL_MCP_PORT`。

## 2. 另一个 WSL 终端：只读检查

```bash
./scripts/ros_mcp.sh check
```

应输出 `status: READY`、物体实测位置和区域信息。它核对三个自定义 Action，
只执行 Observe，**不会搬动机械臂**。连接失败时先检查 domain、仿真是否运行、
桥接进程是否 source 了当前 FlexCell install。

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

本入口不修复 #104 的第三次放置几何错误。任务能否完成仍以本次实际结果为准。
