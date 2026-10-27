# CI 分层说明：为什么 stage-1 只做「起得来 + 跑探针」

对应 `.github/workflows/sim-smoke.yml`，issue-03 / issue-04 / issue-10。
前提事实：`ci.yml` 已经覆盖离线阶梯（colcon build + colcon test + 静态扫描），但它**从不启动仿真**；
而 issue-04 要判的正是"Gazebo 里的 DetachableJoint 到底怎么行为"。两者之间必须有一层，
否则每次问"后端行不行"都要回到某台交付机上手跑。

## stage-1 断言什么

只回答一个问题：**这台托管容器能不能把无头 Gazebo 起起来，并把探针跑完。**

1. `ros:jazzy` 里 `ros-jazzy-ros-gz-sim` + `ros-jazzy-gz-tools-vendor` 装得上（apt 包名没写错）
2. `gz` CLI 在 PATH 上，`gz sim --versions` 的主版本是 8
3. `worlds/detachable_probe.sdf` 在无 GPU、无 `DISPLAY` 的服务器模式下起得来（`gz sim -s`）
4. 六项 DetachableJoint 断言（初始附着、自由落体 a≈−9.8、5 次 re-attach、刚体跟随、A/B 独立、接触态 attach 记录）

**不做**：colcon build 第一方包、MoveIt、controller_manager、机器人世界、传感器、抓取闭环。

## 为什么不在 stage-1 做完整 PICK 闭环

### 1. 成本（每次 PR 都付）

| 项 | 冷容器代价 | 说明 |
| --- | --- | --- |
| apt 依赖树 | 数百 MB | MoveIt + ros2_control + 各 controller + `ros-jazzy-ros-gz` 已经包含 Qt/gz-gui/gz-rendering，`container: ros:jazzy` 每次都是冷缓存 |
| colcon build | 分钟级 | `flexcell_interfaces` + `flexcell_skills` 每次重编，hosted runner 4 核 |
| 起整机 | 分钟级 | 机器人 world + `ros_gz_bridge` + controller spawner + 规划器，本身就有固定的启动等待 |

stage-1 全部加起来约 1 分钟（apt 之外），失败信息还能一句话读完。完整闭环是十几分钟日志——
而十几分钟日志的阅读成本，恰好会让人开始"红了先重跑一次"。

### 2. 渲染与实时因子的硬约束

PICK 闭环需要相机（夹爪/腕部）→ 需要 `gz-sim-sensors-system` + ogre2 渲染后端。
GitHub hosted runner 没有 GPU，只能走 llvmpipe 软渲染：RTF 掉到 0.1 量级，相机帧率不稳，
controller 的 `update_rate` 跟不上，规划器等 `/clock` 超时。这不是"配置一下就好"，
是把一个物理仿真塞进错误的硬件类别。

### 3. flaky 风险（按会踩到的顺序）

- **wall-clock sleep vs 仿真时间**：探针里 `follows()` 用 0.3 s 墙钟等瞬移生效。RTF 掉到 0.5 以下时，
  0.3 s 墙钟只推进 0.15 s 仿真时间，跟随判定会假红。这是 stage-1 已知的、最可能的偶发失败。
- **controller spawner 超时**：容器里 CPU 争抢时 spawner 经常卡在 `Waiting for '/controller_manager'`。
- **`/clock` 跳变**：仿真时间从 0 起步，任何在 `use_sim_time` 之前初始化的节点都会算错时间戳。
- **MoveIt 规划随机性**：RRT 类规划器同一 commit 两次成功率不同——流水线会变成掷骰子。
- **接触物理敏感性**：夹持结果对 `max_step_size`、求解器迭代数、初始穿透深度都敏感，跨机器不可复现。
- **容器内 DDS**：多播/discovery 在容器网络里偶发找不到对端，表现为"节点起了但没人收到"。

### 4. 失败信号的价值不对称

stage-1 覆盖的失败（包名写错、`gz` 不在 PATH、`child_link` 与文档不符、模型声明顺序、world 起不来）
都能在 30 秒内定位，而且**都是 issue-04 的决策输入**。
完整闭环的失败绝大多数是环境噪声，不是代码缺陷；把它放进 PR 门禁，等于用一个高噪声信号
去守一个低噪声的门——最后所有人都学会忽略红叉。

## stage-1 的已知局限（别当成整机验证）

- 父体是 `static` 模型，靠 `set_pose` 瞬移模拟机械臂；没有运动学、控制器时延、500 ms 租约。
- 接触场景只有"静置在顶上"，没有侧向夹持；`attach_while_in_contact` 只记录、不断言。
- 没有双物体同时搬运，没有 legacy Pick/Place 兼容回归（那是 issue-07）。

## stage-2 的触发条件

四条**同时**满足才开：

1. stage-1 连续 3 次绿（含一次 `workflow_dispatch` 重跑），证明它本身不是 flaky 的。
2. issue-04 定案为 GO，且 issue-07（legacy 兼容）需要自动化回归——即有"必须每次验"的用例，
   而不是"想看看整机行不行"。
3. 有 self-hosted runner：GPU，或至少是独占 CPU、能撑住 RTF≈1 的机器。hosted runner 不满足，
   不要用 stage-2 去证明它会满足。
4. 探针已经**长成契约测试**：断言的是 carry_server 真正依赖的行为（attach/detach 时序、
   通道隔离、脱离后 `self_collide`），而不是复述文档。

stage-2 形态（写成这样才不会变成永久红）：

- 触发：`schedule` nightly + `workflow_dispatch`，**不挂 PR 必过**。
- 内容：colcon build → 起机器人 world（带相机，所以需要条件 3）→ controller_manager + bridge →
  一次 PICK → 只断言状态机推进与 attach/detach 事件序列，**暂不断言末端位姿精度**。
- 判定：跑 3 次、2 次通过算绿；单个用例要进 PR 门禁，必须先在 20 次重跑里复现 ≥18 次。

## 附：apt 包名核对（2026-10-27）

- `ros-jazzy-ros-gz` 是 **metapackage**，`Depends` 为 `ros-gz-bridge`、`ros-gz-image`、`ros-gz-sim`、`ros-gz-sim-demos`（版本 1.0.24）。
- `ros-jazzy-ros-gz-sim` 的 `Depends` 里有 `gz-sim-vendor`、`gz-transport-vendor`、`gz-common-vendor`、`gz-msgs-vendor`、`sdformat-vendor`。
- `ros-jazzy-gz-sim-vendor` = **gz-sim8 8.15.0**（与本地安装一致），其 `Depends` 含 `gz-tools-vendor`。
- `ros-jazzy-gz-tools-vendor` = gz-tools2 2.0.4，提供 `gz` CLI（`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`）。
- 反面证据：`ros-jazzy-ros-gz` 的 `Depends` 含 `ros-gz-sim-demos`，后者 `Depends` 含 `rviz2`、`rqt-image-view`、`rqt-plot`、`rqt-topic`、`image-transport-plugins`——纯 GUI/工具链，无头探针一个都用不上。

结论：**Gazebo Harmonic 8.15 + `gz` CLI 由 `ros-jazzy-ros-gz-sim` + `ros-jazzy-gz-tools-vendor` 提供**，
两者是同一棵树（前者靠 `gz-sim-vendor` 把后者拉进来）。三个 vendor 包不是"另一种装法"，
它们是 `ros-gz-sim` 的下游依赖，单独装只会少掉 `ros_gz_sim` 那一层，不会多出 Gazebo。
装 `ros-jazzy-ros-gz` metapackage 也能跑，代价是多拉 rviz2/rqt 几百 MB，冷容器里几分钟——
所以工作流选了窄集合，并保留 `ros-jazzy-ros-gz` 作为解析失败时的退路。

依据：

- <https://raw.githubusercontent.com/gazebosim/ros_gz/jazzy/README.md>（对照表：Jazzy / Harmonic / binaries at packages.ros.org；安装命令 `sudo apt install ros-jazzy-ros-gz`）
- <http://packages.ros.org/ros2/ubuntu/dists/noble/main/binary-amd64/Packages.gz>（上面所有 `Depends` 与版本号均取自该索引）
- <https://index.ros.org/p/ros_gz/#jazzy>
