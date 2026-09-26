# FlexCell 第二轮深度调研报告：开源机器人生态中的 Skill / 规划 / 运行时 / 恢复 / 评测架构

> 状态：完成稿（六线全部到位）
> 调研方式：6 路并行 librarian 深度调研，GitHub 源码级分析，commit 已固定
> 确定性标注：**[已实现·源码]** = 在固定 commit 的源码中直接读到；**[官方文档]** = 官方文档/设计文档陈述；**[推测]** = 未能从源码或官方文档验证
> 约束：不换技术路线，不引入新框架；主线保持 ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2

---

## 1. Executive Summary

本轮调研覆盖六条线、约 20 个仓库/系统（全部源码级固定 commit 验证）：

1. **Isaac 生态 + Intrinsic Core**（Isaac Lab、Isaac ROS Manipulator、Isaac for Manipulation 参考架构官方页、intrinsic-core）
2. **ROS 2 任务规划与恢复正统**（MoveIt Task Constructor、BehaviorTree.CPP v4.10、Nav2 BT Navigator/nav2_behaviors）
3. **Open-RMF**（任务提交/竞标/授予五段链路、rmf_task 十态事件分类学、车队适配器统一接口、取消序列与崩溃备份、rmf_gym 场景测试）
4. **Agentic robotics / LLM-in-the-loop**（roboagent-os、quackd、ros-mcp-server、RoboOS、ROS-LLM、ros2-llm-safety-verifier 等 12 仓）
5. **学习栈接口与 replay**（LeRobot、robomimic、robocasa）
6. **Benchmark 栈**（ManiSkill、RLBench、BEHAVIOR-1K、OpenVLA）

**核心结论（11 条）：**

1. **FlexCell 的四层切分（WorldState → DecisionPolicy → deterministic Executor → Skill Servers）与工业界主流一致**：Isaac ROS 用 py_trees 编排层（policy）+ ROS 2 Action 技能边界 + 独立感知/运动服务器；Intrinsic 用 Executive（行为树+CLIPS）+ gRPC skill + 共享 Object World；Open-RMF 用任务层调度 + 车队适配器统一接口。**没有任何一个系统让 LLM/策略直接控制关节**。[已实现·源码]
2. **"skill = 带类型输入输出 + 状态码的黑盒"是跨系统通用抽象**：Isaac Lab 的 Term（func+params）、Intrinsic 的 skill（proto params + manifest）、Isaac ROS 的 ROS 2 Action（goal/result/feedback）、roboagent-os 的 SkillSpec dataclass、quackd 的 VerbSpec。FlexCell 的 Skill Server 设计方向正确，缺的是**类型化 schema 与声明式依赖**。[已实现·源码]
3. **失败表示的行业共识是 `(error_code, error_msg)` 结构对 + 人可读 comment**：Nav2 每个 action 定义 uint16 error_code + string error_msg，BT 节点写入输出端口；MTC 失败 = 非有限 cost + comment 字符串 + explainFailure() 树遍历；Intrinsic 用数值错误码 + ExtendedStatus。**布尔 success/failure 不够**。[已实现·源码]
4. **恢复是树结构，不是策略分支**：Nav2 双子节点 RecoveryNode（任务，恢复）+ number_of_retries 上限 + RoundRobin 轮换 + "恢复节点 SKIPPED ⇒ 整体 FAILURE"；Intrinsic RetryNode(max_tries, recovery 子树)；roboagent-os 复合技能自带 session_step_limit/recovery_budget，恢复轨迹进审计日志而不进 LLM 上下文。**有界恢复预算应实现为 error_code 上的谓词，而非无差别重试**。[已实现·源码]
5. **安全门必须是确定性的、在策略与执行器之间**：ros2-llm-safety-verifier（costmap 碰撞+运动学可行性检查，1472/1472 捕获、0 误报、~10µs）；quackd 置信度地板 + fail-closed 解析 + shadow mode；roboagent-os 两阶段 validate_start/validate_continue + 循环守卫。**RoboOS/ROS-LLM 反例：LLM 输出直接到执行器，只有 try/except**。[已实现·源码]
6. **WorldState 应是"带时间戳的、可序列化的快照"而非可变单例**：MTC InterfaceState 是纯值对象；BT.CPP 黑板条目带 sequence_id + 时间戳（Executor 可拒收陈旧观测）；robocasa ep_meta 是 JSON 场景图级序列化；Isaac ROS 黑板用 YAML 显式声明键。[已实现·源码]
7. **Benchmark/Replay 的确定性归 harness 所有，不归 policy**：robomimic env.reset_to(state_dict)、ManiSkill reset_kwargs 序列化 + state-replay 双模式、robocasa 动作回放偏差校验、LIBERO set_init_state 固定初始状态。**失败的 episode 必须能靠记录的 seed/初始状态精确复现**。[已实现·源码]
8. **统计严谨性可以直接抄**：LeRobot eval_stats.py 内置 Wilson 95% CI + Fisher 精确检验（stdlib-only）；每集记录 seed；robocasa 固定 eval 分布（held-out 实例 + 固定 layout/style + 每任务 horizon）。[已实现·源码]
9. **全生态共同缺失、FlexCell 可以占先的三块**：失败码/重试/恢复语义（学习栈三仓全部缺失）、token 成本追踪（四栈全部缺失）、证据链与策略级延迟/成本基准（无先例）。**FlexCell 的 DecisionPolicy 契约是在新增真实表面积，不是在重复造轮子**。[已实现·源码] + [推测：为本报告综合判断]
10. **DecisionPolicy 接口的最强参照组合**：quackd 的决策步进器（choice 分类、置信度地板、shadow mode）+ roboagent-os 的 Planner Protocol（FSM/Jev/LLM 可互换、CI 用确定性 mock）+ BEHAVIOR 的"结构化目标与指令渲染分离"（同任务喂 FSM 谓词 / Jev 目标 / LLM 生成 NL）。[已实现·源码]
11. **任务层的正统参照是 Open-RMF**：提交→竞标→授予→确认五段链路（DispatchCommand→DispatchAck 带过期重派）；**每个 phase 预声明 cancellation_sequence（取消=切清理序列，不是 abort）**；Event 十态里 Blocked/Error（需人救）与 Failed（救不了）分级是全生态唯一；backup_state/checkpoint/BackupFileManager 把崩溃恢复做成接口一等参数。FlexCell 的取消语义、失败分级、下发闭环、状态落盘四件事都可直接抄它。[已实现·源码]

---

## 2. Existing Architecture Patterns

### 2.1 Isaac 生态 + Intrinsic Core

**Isaac Lab（commit 24a2ebfd）**[已实现·源码]

- A. 架构：Manager-based 环境——任务拆成独立 manager 各管 MDP 一切片。`ManagerBasedEnv`（仿真+场景，MDP 无关）与 `ManagerBasedRLEnv`（加 reward/termination/curriculum）显式分离。核心单元是 **Term = func + params**（`ManagerTermBaseCfg`）。
- B. 接口：`ActionTerm` 两阶段契约——`process_actions()` 每决策一次，`apply_actions()` 每仿真步一次。**这正是 DecisionPolicy（慢）→ Executor（快）的分拍**。Termination term 带 `time_out` 标志区分"预算耗尽"与"任务失败"。
- C. Replay：`RecorderManager` 四生命周期点录 HDF5；成功/失败 episode 分文件导出。

**Isaac ROS Manipulator（commit f5c47880）**[已实现·源码]

- A. 架构：Visual Input → Nvblox 感知 → Robot Config → 目标状态估计 → cuMotion（MoveIt 2 插件）→ 硬件。**编排层 = py_trees 行为树**（`isaac_ros_manipulation_orchestration`），叶子是包 ROS 2 Action 客户端的 `BaseActionBehavior`。
- B. 接口：**skill = ROS 2 Action**（goal/result/feedback 三元组，如 `PickAndPlace.action` result 仅 `bool success` + feedback `int32 progress`）。状态 = YAML 显式声明的黑板键。恢复分层：`py_trees.decorators.Retry` + action server 掉线重连（`handle_server_recovery()` 保守默认 FAILED）+ 陈旧检测阈值。感知与运动在 `FailureIsRunning` 下并行。
- C. Replay：`mock_servers/` 假 action 服务器支持无硬件测行为树。

**Intrinsic Core（commit fb90b295）**[已实现·源码]

- A. 架构：skill = gRPC 服务，操作共享 **Object World**（唯一状态源）；**Executive** 用行为树 + CLIPS 规则引擎调度；Python Solutions 是创作 API。
- B. 接口：skill = proto 参数 + manifest（id/依赖/参数/返回类型）+ C++ 实现；`SkillInterface = Execute / Preview / GetFootprint`。**Predict-before-execute**：Projector 返回执行后世界状态概率分布。失败 = 数值错误码 + ExtendedStatus；恢复 = 行为树 RetryNode(max_tries, recovery 子树)。**Footprint 预留模型**（对象 WRITE/READ、扫掠体积、设备锁）是最强的安全门理念——并发技能冲突由声明式足迹拒绝，而非拍平的布尔门。
- C. Replay：world_id 隔离支持分支/回滚 what-if 分析；`google.longrunning.Operation` 统一异步+取消。

**Isaac for Manipulation 参考架构（官方 release-4.5 页）**[官方文档]

- 六层：视觉输入 / 环境感知 / 机器人配置（URDF+XRDF）/ 目标状态估计 / 运动规划（cuMotion，MoveIt 2 插件）/ 硬件。已测机械臂 UR5e/UR10e/Franka/Flexiv Rizon 4s。组件是"可多实现的功能块"。Intrinsic.ai 用它 30ms 内生成运动计划。
- [推测] `FollowCartesianPose`/`MoveAndGrasp` 疑似来自闭源 Isaac Manipulator SDK，开源仓中无法验证。

### 2.2 MoveIt Task Constructor / BehaviorTree.CPP / Nav2

**MTC（commit f527048b, Jazzy 0.1.x）**[已实现·源码]

- 规划期 DAG 搜索框架（非运行时执行器）。`InterfaceState` = PlanningScene 指针 + PropertyMap + 优先级，**状态是值对象在 stage 间流动，不是全局单例**。
- 属性系统：scoped + typed + 继承（DEFAULT/MANUAL/PARENT/INTERFACE），优于 Nav2 扁平黑板。
- 失败表示：`cost 非有限 = 失败` + comment 字符串；`explainFailure()` 树遍历输出"第一个失败 stage + 原因"。
- `ExecuteTaskSolution` **单飞门**：执行中拒绝新目标。`success_or` 部分成功语义：有任何解就报成功（哪怕被抢占/超时）。
- `Task::init()` 图校验：执行前验证 stage 接口兼容性 → **策略↔技能端口契约应在加载期校验**。
- 恢复是结构性的（Fallbacks/Alternatives），**无运行时重试**——运行时恢复要靠 Nav2 的 RecoveryNode 补。

**BehaviorTree.CPP v4.10.0（commit ca4edbf3；v5 未发布）**[已实现·源码] / [推测：v5 仅设计文档]

- `NodeStatus` 五态：IDLE/RUNNING/SUCCESS/FAILURE/**SKIPPED**。SKIPPED 让策略能说"不适用"而不算失败——DecisionPolicy 输出应有三终态 SUCCESS/FAILURE/SKIPPED。
- 类型化端口 `providedPorts()`（名称/方向/类型/默认值）→ 支持加载期契约检查。
- 黑板条目带 `sequence_id` + 时间戳 → WorldState 新鲜度校验。
- RetryNode 重试间返回 RUNNING 让树保持可中断；`_while`/`_skipIf`/`_failureIf` 前后置条件 = 声明式安全门（`_while` 可打断 RUNNING 节点）。
- `num_attempts=-1` 无限重试是坑，FlexCell 有界预算不应暴露。
- **不采用**：Nav2 式扁平无类型黑板、无限重试、XML 作为唯一组合语言。

**Nav2 BT Navigator + nav2_behaviors（commit 7b9bcb4c, 1.5.0/Jazzy）**[已实现·源码]

- 三层：bt_navigator（lifecycle 插件宿主）/ nav2_behavior_tree（BT 引擎 + ~60 节点插件 + BtActionServer 桥）/ nav2_behaviors（独立 BehaviorServer：Spin/BackUp/Wait…）。
- **技能契约 = `(uint16 error_code, string error_msg)`**，每个 BtActionNode 声明 error_code_id/error_msg 输出端口；BtActionServer 按优先级聚合、轮间清理。
- **RecoveryNode（双子节点）**：子1=主任务，子2=恢复；恢复成功→重试，重试数上限；子2 SKIPPED ⇒ 整体 FAILURE。RoundRobin 轮换恢复动作防止连撞同一招。
- **恢复资格谓词** `WouldAControllerRecoveryHelp`：error_code ∈ {UNKNOWN, PATIENCE_EXCEEDED, FAILED_TO_MAKE_PROGRESS, NO_VALID_CONTROL} 才值得恢复——**"什么失败了"与"是否值得恢复"分离**。
- 技能两阶段生命周期 `onRun`（验证一次）→ `onCycleUpdate`（循环至终态）= preflight 验证先于运动。
- 已知缺陷：behavior 抢占未实现（直接 abort）——FlexCell 需要真抢占，参照 MTC `preempt()`/PREEMPTED。

### 2.3 Open-RMF（任务层调度）

源码固定：`open-rmf/rmf_ros2@a0ca627`、`rmf_internal_msgs@2a7f01b`、`rmf_task@3a6af29`、`rmf_demos@7851a57`、`rmf_gym@aa185b4`。**架构分层**[已实现·源码]：

**请求 → 调度 → 任务 → 适配器 → 执行的五段链路：**

1. **提交**：`rmf_task_msgs/srv/SubmitTask.srv`（requester + TaskDescription → success + task_id + message）打到 dispatcher 节点；另有 `ApiService.srv`/`ApiRequest.msg` JSON API。`TaskProfile = task_id + submission_time + TaskDescription`；TaskDescription = start_time + priority(`Priority.msg` uint64 value=0) + task_type 联合体（Station/Loop/Delivery/Clean 四选一，注释明确"对应字段必须填充"）。任务描述 JSON 经 **nlohmann json-schema 校验**（`rmf_task_sequence/schemas/ErrorHandler`，失败返回 pointer+instance+message 三元组）。
2. **竞标**：`Auctioneer`（`rmf_task_ros2/bidding/`）串行开标（`request_bid`/`ready_for_next_bid`），`BiddingResultCallback(task_id, optional winner, errors)` 出结果。**评审策略是抽象接口** `Auctioneer::Evaluator::choose(Responses)`，自带三个实现：`LeastFleetDiffCostEvaluator`（Auctioneer.hpp 注释称默认）、`LeastFleetCostEvaluator`、`QuickestFinishEvaluator`（Dispatcher.hpp 注释称默认——**两处文档对默认值描述不一致，属官方文档级差异**[官方文档]）。消息流：`BidNotice`（time_window 开标窗口 + dry_run 只练不授）→ `BidProposal`（prev_cost/new_cost/finish_time）→ `BidResponse`（has_proposal + errors[]）；topic 固定为 `rmf_task/bid_notice`、`rmf_task/bid_proposal`、`rmf_task/dispatch_request`、`rmf_task/dispatch_ack`（StandardNames.hpp）。
3. **授予**：`DispatchCommand`（TYPE_AWARD=1 / TYPE_REMOVE=2，带 timestamp 过期机制"dispatch requests may expire with an error"）→ 车队回 `DispatchAck`（success + errors[]）。
4. **状态**：`DispatchState` 五态枚举 `STATUS_QUEUED/SELECTED/DISPATCHED/FAILED_TO_ASSIGN/CANCELED_IN_FLIGHT`（+UNINITIALIZED=0），带 `Assignment(is_assigned, fleet_name, expected_robot_name)` 与 **`errors` 数组**（C++ 侧为 `vector<nlohmann::json>`，msg 侧 string[]）；`Dispatcher` 维护 active/finished 两张 DispatchState 表 + `on_change` 回调。`TaskSummary.msg` 是车队回报的执行态六枚举：`STATE_QUEUED/ACTIVE/COMPLETED/FAILED/CANCELED/PENDING` + 人读 `status` 字符串 + submission/start/end 时间（end_time 注释区分"进行中=预估、终态=实际"）+ robot_name。
5. **执行**：车队适配器经 `rmf_fleet_msgs`（/fleet_states、destination/mode/path/pause_requests）驱动车队驱动层；适配器内部用 rmf_traffic 谈判 + 自己的事件机（`events/ExecutePlan`、`GoToPlace`、`Error`、`EmergencyPullover`）。

**任务模型（rmf_task / rmf_task_sequence）**[已实现·源码]：

- `rmf_task::State : CompositeData`——**类型化可选组件**（RMF_TASK_DEFINE_COMPONENT：CurrentWaypoint/Orientation/Time/ChargingPoint/BatterySoC/IsIdle，全部 optional），`load_basic`/`extract_plan_start` 与规划器互转。
- `rmf_task::Event::Status` 十态枚举 = **全调研中最细的失败分类学**：`Uninitialized / Blocked(需人工介入) / Error(实现不认识、需人工) / Failed(即使人工也无法挽回) / Standby / Underway / Delayed / Skipped / Canceled / Killed / Completed` + 组合子 `sequence_status(earlier, later)`（序列整体状态推导）。
- `Event::State` 接口 = `id() + status() + name() + detail() + log() + dependencies()`——**每个事件挂一条结构化 Log**；`Event::Snapshot` 线程安全快照供 UI 并发读。
- `rmf_task::Log`：Tier=Info/Warning/Error，Entry 带 `seq(自增序号)+time+text`；`View` 快照（"读取期间新增不可见"）、`Reader` 去重游标（"每个 Reader 读过的条目唯一"）——**证据链原语**。
- **`rmf_task_sequence::Task::Builder.add_phase(description, cancellation_sequence)`——每个 phase 自带一条取消序列**：取消不是 abort，而是切换到该 phase 预声明的清理动作序列；`Activator::Activate` 回调五元组（update 快照 / checkpoint 备份点 / phase_finished / task_finished + `backup_state` "if the Task is being restored from a crash or disconnection"）——**崩溃恢复是接口签名的一等参数**。
- 事件组合：`Bundle`（Type::Sequence 已实现；ParallelAll/ParallelAny 源码中注释着"Not implemented yet"）+ 具体事件 GoToPlace/PickUp/DropOff/WaitFor/PerformAction/Placeholder。
- 工厂注册：`Activator` 按 `std::type_index` 注册类型→激活器；`RequestFactory`（如 `ParkRobotIndefinitely`）自动生成收尾停车任务。
- **`BackupFileManager`**：root 目录 + `clear_on_startup/shutdown` + Group(fleet)/Robot 层级备份文件——任务状态落盘，重启可恢复。

**适配器统一接口**[已实现·源码]：

- `EasyFullControl`（官方推荐入口）：`add_robot(name, initial_state, configuration, callbacks)`——回调集 = `NavigationRequest/StopRequest/LocalizationRequest`，命令进度经 **`ActionExecution` 回传**（两阶段：执行中持续 update，终态回执）；`ActionExecutor = (category, nlohmann::json description, ActionExecution)` 接收带 JSON Schema 的直接动作（`submit_direct_request` 按 `rmf_api_msgs` 的 task_request.json schema 校验）；`consider_*_requests()` 过滤可接任务类型；`AssignmentStrategy` 复用 rmf_task::TaskPlanner 策略；`more()` 下探 FleetUpdateHandle。
- **失败/中断/人工覆盖 API（RobotUpdateHandle）**：`error(optional<string>)` = "Set task status to error and optionally log a message (error tier)"；`log_error(text)`；`Interruption interrupt(...)` **RAII 句柄——带 labels 说明为何中断，析构即恢复**；`Stubbornness override_schedule(...)` **RAII 拒绝一切调度妥协**（注释警告"过多 stubborn 会死锁"，用于遥操作）；`Unstable` 扩展 + stubborn_buddies failover（`RMF_ENABLE_FAILOVER=1` 条件编译）；`Alert.msg` 三级 tier（INFO/WARNING/ERROR）+ `responses_available` 可选项 + task_id = **人工确认回路的消息格式**。
- **状态/日志流**：`task_state_update`、`task_log_update`、`task_api_requests/responses`（transient_local QoS）→ `rmf_websocket` 广播 → rmf-web 仪表盘。

**Replay/eval**[已实现·源码]：

- `rmf_gym`（独立仓）：rmf_gym_worlds 预制测试世界 + **"pre-determined tasks to replicate tricky scenarios, or infinitely send random tasks to see how long the system lasts"**（确定性场景重放 + 随机 soak）+ 按 waypoint 标签可复现生成机器人 + 自动化测试 launch + hardware-in-the-loop。
- `rmf_demos_tasks` 脚本：`wait_for_task_complete.py` / `cancel_task.py` / `cancel_robot_task.py`——仅有任务级完成/取消轮询。
- **缺口（明确缺席）**：无 seed 级策略回放、无基准统计（CI/显著性检验）、无策略间对比表；事件 Log 与 backup 文件是审计/恢复设施，不是 benchmark harness。

**Lessons for FlexCell（Open-RMF 线）：**

- 取消/中断是**预声明的结构**（per-phase cancellation_sequence、Interruption labels、Interruption RAII），不是运行时 if-else——FlexCell 的中止清理动作应进 skill/phase 描述。
- 失败分类要区分"**需人工介入**（Blocked/Error）"与"**人工也救不了**（Failed）"——比布尔失败多出的操作语义，直接可抄进 DecisionPolicy 终态。
- 每个事件挂一条 `seq+time+tier` 的 Log 且 Reader 去重——这是现成的证据链数据结构。
- crash/disconnect 恢复 = `backup_state` 一等参数 + checkpoint 回调 + BackupFileManager 落盘——FlexCell 若要求 Executor 崩溃恢复，这是成熟配方。
- 竞标-授予-确认（Award→Ack→过期）是"调度器与执行器双向确认"模式——对应 FlexCell 决策下发需 ack + 超时重派。
- 默认评审器两处文档矛盾（LeastFleetDiffCost vs QuickestFinish）——提示**默认策略必须由测试钉死，不能信文档**。

### 2.4 Agentic Robotics / LLM-in-the-loop（12 仓）

**roboagent-os（DaveByteAI，6★）**[已实现·源码] —— 与 FlexCell 架构最接近

- 一次一个动作的循环，max_steps 有界（默认 12，上限 30）。Planner 是 **Protocol**：`decide(context, tools, image) -> AgentDecision`，LLM 实现与确定性 mock 实现同接口可换（CI 用 mock）。
- `SkillSpec` dataclass：name/description/executor/action_space/requirements/operator_required/execution_mode/session_step_limit/**recovery_budget**；JSON Schema `strict:true` + 边界写进 schema，LLM 连越界动作都表达不出来。
- 两阶段安全策略：`validate_start()`（任务前：电量/定位新鲜度/温度/地图匹配）与 `validate_continue()`（每回合）。
- **复合技能自带重试**：有界私有循环 + recovery_budget=2；会话轨迹进审计日志、**明确不进 planner 上下文**。
- 循环守卫：3 个相同动作签名 → 中止。失败以 `{ok:false, error_code}` 追加进历史让 LLM 看见。
- append-only 类型化事件日志 + 内容哈希 artifact。
- 缺陷：runtime.py/recorder.py/supervisor.py 仍是 1 行桩。

**quackd（rokbenko，241★）**[已实现·源码] —— DecisionPolicy 步进器最佳参照

- `RobotManifest`/pydantic `VerbSpec`：params JSON Schema、safety_class、timeout_s、datasheet（物理参数带 official|estimate|measured 置信标注）。**"不在 manifest 里的动词不存在"**（ADR-0017）；stop 永远放行。
- 步进器：参数全闭集才算 _choice_（交给分类器），出现数字/对象 → 归 LLM。**分类置信度地板按动词类**：brake=0.50 / read=0.60 / motion=0.85 / confirm=0.90 / never=1.01（危险动词不提供）。
- 门顺序：unreadable → done → need_human → escalate → repeat → streak-handover → below_floor → taken；ESCALATE 每回合必提供。
- **Fail-closed 解析**：NaN/None/True 不是概率——答案缺失把回合还给模型，而不是动身体。
- **Shadow mode**：并排记录分类器"本来会怎么选"（choice/confidence/gate/agree），先测量一致率再信任。
- 缺陷：自己的文档承认置信地板是"风险偏好而非校准"；决策 LLM 未上真机。

**ros2-llm-safety-verifier（7★）**[已实现·源码] —— Executor 安全门范本

- C++ 验证器置于 LLM planner 与 Nav2 之间：离图 → 断点（瞬移）→ 曲率 → 扫掠碰撞（footprint 采样）→ 未知区域；返回 `Verdict{safe, violation, waypoint_index}`。
- 离线种子化基准：**1472/1472 不安全全捕获、0/599 误报、中位延迟 ~10µs**。

**ros-mcp-server（1474★）**[已实现·源码]：MCP 工具暴露 ROS 2 topic/service/action；运行时自省（rosapi 发现接口）；YAML `prompts:` 块承载技能散文文档；安全门薄（destructiveHint 注解），安全靠机器人规格散文——反面教材的一半。

**RoboOS（626★）**[已实现·源码]：master GlobalTaskPlanner（LLM, temp=0）分解子任务 → slaver smolagents ReAct 循环。**无确定性安全门**，错误码 E303/E304 喂回 LLM "Now let's retry"。

**ROS-LLM（829★）**[已实现·源码]：`getattr(self, function_name)` 派发 = 节点任何方法都可被 LLM 按名调用；无白名单、无边界、无世界状态序列化——**明确反模式**。robochain 的 `exec(code)` 更极端，玩具可、真机否。

**其他验证过的仓**：ros2_nanollm（VLM 节点，无 agent 循环）、ros2_llm_if（JSON schema + 人工按回车确认门）、Voyager（技能库模式，非 ROS）、SayCan 复刻（均非 ROS 2 原生）。**CoinAgent/AWS RoboRunner/Isaac Agent Skills 等候选确认不存在或闭源，未分析**。

### 2.5 学习栈接口与 Replay（LeRobot / robomimic / robocasa）

**LeRobot（commit e595b790）**[已实现·源码]

- `PreTrainedPolicy` 抽象面：`reset()` / `forward()` / `predict_action_chunk()` / `select_action()`——**reset() 是一等接口方法**（episode 边界清队列/隐藏态），Action chunk 队列在 `select_action` 内部管理。
- 世界状态 = 扁平张量字典，规范键（`observation.state`、`next.success`…）；**归一化在策略外的 processor 管道**（stats 在数据集里）。
- 评测：批量化种子 rollout、每集记录 seed、**Wilson 95% CI + Fisher 精确检验**（eval_stats.py，stdlib-only，可整段抄）。
- **失败/重试：缺席**——报告明确要求"State this as absent"。replay 是开环动作回放，**不校验状态收敛**。

**robomimic（commit d309eae）**[已实现·源码]

- `env.reset_to(state_dict)` = **replay harness 原语**（模型 XML + 展平状态 + ep_meta 三元组恢复，源码注释自称 "hack necessary for deterministic action playback"）。
- modality 在构造期声明 schema（`obs_key_shapes` + `ac_dim` 传入而非发现）；`mask/<key>` 过滤键做免复制数据切分。
- `rollout_exceptions` 兜底：坏策略降级为失败集而非崩掉基准——但只兜底不重试。

**robocasa（commit 456174f）**[已实现·源码]

- `ep_meta` = **规范世界状态序列化**（layout/style/object_cfgs/fixtures/lang/cameras/机器人位姿，JSON 场景图级）——FlexCell WorldState 的模型。
- GR00T `modality.json` 类型化动作切片（start/end/rotation_type/absolute/dtype/range）= "类型化 skill action" 的直接模型。
- **动作回放偏差校验**：回放逐步比对 sim 状态，发散打印 norm 告警——信任 replay 对比前先验证确定性。
- 固定 eval 分布：held-out 实例（split "B"）+ 固定 layout/style 组合 + 每任务 horizon。

### 2.6 Benchmark 栈（ManiSkill / RLBench / BEHAVIOR-1K / OpenVLA）

**ManiSkill（commit 62ff3a58）**[已实现·源码]：真值 success 在 env 内 `evaluate()` 每步计算，是 terminated 与 sparse reward 的**单一事实源**；`.h5+json` 序列化 `reset_kwargs`（可复现是数据格式契约）；**双 replay 模式**（动作回放 vs 环境状态回放）；`source_type` 溯源字段（human/motionplanning/rl）。

**RLBench（commit 02720bb）**[已实现·源码]：任务类返回**每变体多条同义指令列表**（测指令鲁棒性）；可组合成功条件 + **显式 fail conditions**（四栈中唯一把失败当一等概念——掉落易碎品等，记录哪个条件触发）；replay = 保存完整 `np.random` 状态 + variation index。

**BEHAVIOR-1K（commit 6cbf70b0）**[已实现·源码]：**任务即数据**——BDDL 声明式谓词树，同一任务可喂 FSM（谓词）/规划器（目标）/LLM（生成 NL）而不改写任务；**Q-score 部分得分**（新满足谓词比例，在 or 分支上取 max）；`normalized_time`（人类步数/智能体步数）效率指标；termination 条件名区分 terminated/truncated。

**OpenVLA（commit c8f03f48）**[已实现·源码]：策略 = 纯函数 `(image, instruction, unnorm_key) → action`，与环境完全解耦；归一化统计随 checkpoint 走；LIBERO `set_init_state` 固定初始状态回放；**token 成本追踪全生态缺席**——FlexCell 可占的空白。

**四栈横切**：真值成功位置 / 任务表示（类 vs 谓词树 vs 指令串）/ 失败分类（仅 RLBench 显式）/ 部分得分（仅 BEHAVIOR）/ 回放单元（seed vs RNG 状态 vs 场景实例 vs 初始状态表）/ 日志格式 / 聚合指标 / token 成本（全缺）。

### 2.7 横切对比小结（六线合并）

- **接口形态收敛在四类**：ROS 2 Action/Topic（Isaac ROS、Open-RMF、FlexCell 现状）、库内抽象类（MTC/BT.CPP/LeRobot/robomimic）、JSON/YAML Schema 契约（Intrinsic、quackd、roboagent-os、rmf task_request.json）、gym 注册式（ManiSkill/RLBench）。没有任何一条线采用"自由文本 skill 调用"——**所有可落地系统都有机器可校验的契约层**。
- **失败语义分三个梯队**：①bool/枚举（Isaac ROS、Nav2 error_code、ManiSkill fail）；②结构化 status+detail+log（Intrinsic ExtendedStatus、rmf Event::State、roboagent-os error_code 历史）；③**人工介入分级**（rmf 的 Blocked/Error vs Failed 是全场唯一区分"需人救"与"救不了"的）。
- **恢复策略四类**：BT 式重试节点（BT.CPP/Nav2/py_trees）、结构化 fallback 序列（MTC、rmf per-phase cancellation_sequence）、人工回路（rmf Alert、quackd ESCALATE）、无（学习栈普遍缺席）。
- **证据链设施最成熟的是 rmf_task::Log（seq+time+tier+Reader 去重）与 LeRobot 的逐 seed 评估记录**；两者合起来才是 FlexCell 需要的"执行留痕 + 可复算"。
- **replay/benchmark 完全集中在学习栈与 rmf_gym（场景级）**，ROS 2 任务栈（MTC/BT/Nav2/Open-RMF 正式接口）无 seed 级回放——FlexCell 若做策略对比 harness 属**自建填补区**，可直接抄 LeRobot（统计）+ rmf_gym（场景注入）。

---

## 3. Comparison Table

六条线全部到位。

### 3.1 Skill / 技能接口

| 系统                                | Skill 定义                                                                     | 状态机制                                           | 失败表示                                            | 恢复                                                                                              |
| ----------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| FlexCell（现状）[已实现·源码]       | ROS 2 Skill Server（observe/pick/place/verify…）                               | WorldState                                         | 布尔/字符串                                         | Executor 内重试（M2 计划）                                                                        |
| Isaac ROS Manipulator [已实现·源码] | ROS 2 Action goal/result/feedback                                              | YAML 声明黑板                                      | bool success（较弱）                                | py_trees Retry + server 恢复钩子 + 陈旧检测                                                       |
| Intrinsic Core [已实现·源码]        | proto+manifest+gRPC skill                                                      | Object World（world_id）                           | 数值错误码+ExtendedStatus                           | 行为树 RetryNode+recovery 子树；Footprint 并发门                                                  |
| Isaac Lab [已实现·源码]             | Term=func+params 配置                                                          | GPU 张量缓冲                                       | termination 布尔+time_out 标志                      | Event/Curriculum manager（训练语义）                                                              |
| MTC [已实现·源码]                   | C++ Stage 类                                                                   | InterfaceState 值对象                              | 非有限 cost+comment                                 | 结构性 Fallbacks（无运行时重试）                                                                  |
| BT.CPP v4 [已实现·源码]             | 类型化端口节点                                                                 | 带时间戳黑板                                       | 5 态 NodeStatus 含 SKIPPED                          | Retry/Timeout 装饰器                                                                              |
| Nav2 [已实现·源码]                  | BtActionNode/Behavior 插件                                                     | 黑板（goal/error_code/恢复计数）                   | uint16 error_code+error_msg                         | RecoveryNode+RoundRobin+资格谓词                                                                  |
| Open-RMF [已实现·源码]              | SubmitTask.srv / ActionExecutor(category+JSON Schema) / EasyFullControl 回调集 | DispatchState 5 态 + TaskSummary 6 态 + Event 十态 | errors[] 数组 + error(text) error-tier + Alert 三级 | 每 phase 自带 cancellation_sequence + Interruption/Stubbornness RAII + BackupFileManager 落盘恢复 |
| quackd [已实现·源码]                | VerbSpec manifest                                                              | 具名 JSON 状态预算                                 | fail-closed 解析                                    | streak 上限+ESCALATE                                                                              |
| roboagent-os [已实现·源码]          | SkillSpec dataclass+JSON Schema                                                | context dict（含 safety_budget）                   | {ok:false,error_code} 进历史                        | 复合技能私有预算+循环守卫                                                                         |
| LeRobot [已实现·源码]               | PreTrainedPolicy 方法集                                                        | 张量字典                                           | **缺席**                                            | **缺席**                                                                                          |
| robomimic [已实现·源码]             | Algo.get_action                                                                | modality 键                                        | rollout_exceptions 兜底                             | 无                                                                                                |
| ManiSkill [已实现·源码]             | gym 注册任务类                                                                 | obs 字典                                           | fail 布尔                                           | replay max_retry（采集侧）                                                                        |
| RLBench [已实现·源码]               | Task 类+Condition 库                                                           | Observation 数据类                                 | **显式 fail conditions**                            | 采集重试（attempts=10）                                                                           |
| BEHAVIOR-1K [已实现·源码]           | BDDL 谓词树                                                                    | OmniGibson 状态                                    | 无（timeout+feedback）                              | 无                                                                                                |
| OpenVLA [已实现·源码]               | 纯函数 predict_action                                                          | image+state 拼接                                   | 无                                                  | 无                                                                                                |

### 3.2 评测 / Replay 能力

| 系统                      | 确定性原语                                  | 统计                                               | 部分得分 | 成本/延迟追踪                             |
| ------------------------- | ------------------------------------------- | -------------------------------------------------- | -------- | ----------------------------------------- |
| LeRobot [已实现·源码]     | 每集 seed 记录                              | Wilson CI+Fisher 精确检验                          | 无       | eval_ep_s（仅耗时）                       |
| robomimic [已实现·源码]   | reset_to(状态三元组)                        | 成功率+视频                                        | 无       | 无                                        |
| robocasa [已实现·源码]    | reset_to+回放偏差校验                       | 固定 eval 分布                                     | 无       | 无                                        |
| ManiSkill [已实现·源码]   | reset_kwargs+状态回放双模式                 | extract_scalars                                    | 无       | 无                                        |
| RLBench [已实现·源码]     | np.random 状态+variation                    | 仓外                                               | 无       | 无                                        |
| BEHAVIOR-1K [已实现·源码] | 预缓存场景实例                              | **Q-score+normalized_time**                        | **有**   | 有（时间指标）                            |
| OpenVLA [已实现·源码]     | set_init_state 初始状态表                   | 成功率/task+total                                  | 无       | **token 成本：全生态缺席**                |
| Open-RMF [已实现·源码]    | rmf_gym 预定场景重放+随机 soak+可复现 spawn | **无统计**（仅 wait_for_task_complete 等轮询脚本） | 无       | backup/Log 落盘（审计设施，非 benchmark） |

---

## 4. FlexCell Gap Analysis

对照 FlexCell 现状（docs/ARCHITECTURE.md，M2.1 边界：决策层只出 task-level decision objects，不碰关节/轨迹/参数/安全）：

**已对齐（保持，勿改）：**

1. 四层切分与 Isaac ROS / Intrinsic / Open-RMF 同构 [已实现·源码]。
2. "Skill Servers 走 ROS 2 Action/服务边界"与 Isaac ROS 一致 [已实现·源码]。
3. 确定性 Executor 做安全门的直觉正确——三个独立系统（safety-verifier、quackd executor 门、roboagent-os policy 校验）都验证了它 [已实现·源码]。
4. DecisionPolicy 慢拍 / Executor 快拍与 Isaac Lab `process_actions`/`apply_actions` 两阶段同构 [已实现·源码]。

**缺口（按优先级）：**

1. **失败契约未类型化**：现状无 `(error_code, error_msg)` 结构对，无 SKIPPED/不适用终态，无 "第一个失败 stage+原因" 诊断报告。行业共识已明确（Nav2/MTC/Intrinsic 三证）。
2. **恢复预算未落在 error_code 谓词上**：需要"哪些错误值得恢复"的资格谓词 + RoundRobin 式轮换 + "恢复不可用 ⇒ 整体失败"语义，而非无差别重试。
3. **WorldState 无时间戳/无 schema 声明**：缺 sequence_id+stamp（拒收陈旧观测）、缺 YAML/类型化键声明（策略与技能加载期对齐）。
4. **安全门未验证量化**：缺 safety-verifier 式离线种子化基准（捕获率/误报率/延迟）；缺 quackd 式 shadow mode（先测量再信任 LLM/新策略）。
5. **Replay harness 未定**：缺确定性原语选型（seed vs 初始状态表 vs 全状态快照）、回放偏差校验、每集 seed 记录。
6. **基准统计未定**：缺 Wilson CI/Fisher、固定 eval 分布（held-out+horizon）、失败原因分类（timeout/约束违反/策略异常）、Q-score 式部分得分。
7. **证据链/token 成本无先例可抄**：学习栈与 benchmark 栈均缺席——这是 FlexCell 要自己设计的新表面积 [已实现·源码（缺席即证据）] + [推测：设计建议]。
8. **单飞执行/真抢占**：MTC 单飞门 + Nav2 "抢占未实现" 反例提示 Executor 需要显式拒绝执行中新目标 + 真抢占语义。
9. **中止无预清理动作、失败无"需人救/救不了"分级**：现状取消=中断当下动作；Open-RMF 证明成熟做法是**每个 phase 预声明 cancellation_sequence**（取消=切清理序列），失败需区分 Blocked/Error（人工介入可救）与 Failed（救不了）两档操作语义 [已实现·源码]。
10. **决策下发无 ack/超时重派、状态无落盘恢复**：Open-RMF 的 Award→DispatchAck→过期重派闭环与 backup_state/checkpoint/BackupFileManager 崩溃恢复在 FlexCell 均缺席 [已实现·源码]。

---

## 5. Concrete Recommendations

（每条标注来源与确定性；不改主线、不引入新框架）

**R1. 决策接口用 Protocol + 确定性 mock**：`decide(context, skills, evidence) -> Decision`，FSM/Jev/LLM/Hybrid 同接口，CI 跑 mock。[来源 roboagent-os，已实现·源码]
**R2. 失败契约升级为 `(uint16 error_code, string error_msg)` + 三终态（SUCCESS/FAILURE/SKIPPED）+ 人可读 comment**；Executor 聚合错误码并产出"第一个失败技能+原因"报告。[来源 Nav2 BtActionNode / BT.CPP NodeStatus / MTC explainFailure，已实现·源码]
**R3. 恢复 = 双子节点结构 + 资格谓词 + 轮换**：RecoveryNode(task, recovery) 有界重试；`recovery_eligible(error_code)` 谓词决定是否值得恢复；RoundRobin 防重复；恢复不可用 ⇒ 整体失败；恢复轨迹进审计不进策略上下文。[来源 Nav2 recovery_node/WouldAControllerRecoveryHelp/RoundRobin + roboagent-os，已实现·源码]
**R4. 安全门做成可验证组件**：为 Executor 安全检查建离线种子化基准（不安全样本捕获率/误报率/延迟 p50）；上真机前对任何新策略跑 shadow mode。[来源 ros2-llm-safety-verifier（1472/1472, 0 FP, ~10µs）+ quackd，已实现·源码]
**R5. WorldState = 带 stamp 的类型化快照**：每条目 sequence_id+时间戳；键用声明式 schema（YAML/类型化）；序列化采用 ep_meta 式 JSON 场景描述而非裸观测向量；归一化层与原始层分离。[来源 BT.CPP blackboard / Isaac ROS 黑板 YAML / robocasa ep_meta / LeRobot processor，已实现·源码]
**R6. 技能契约补齐**：每个 Skill 声明类型化输入输出（可比照 GR00T modality 的 start/end/range 切片）、preflight 验证阶段（onRun/onCycleUpdate 两阶段）、conflict footprint（对象写集+扫掠体积，供 Executor 拒绝并发冲突）。[来源 Intrinsic footprint / nav2 TimedBehavior / robocasa modality.json，已实现·源码]
**R7. Replay harness 三档确定性**：per-episode seed 记录（复现失败）+ 固定初始状态表（策略间公平对比）+ 全状态快照（调试）；回放时做偏差校验。[来源 LeRobot seed / LIBERO set_init_state / robomimic reset_to / robocasa divergence check，已实现·源码]
**R8. 基准统计直接抄 LeRobot eval_stats**（Wilson CI + Fisher exact，stdlib-only），加固定 eval 分布与每任务 horizon；失败按原因分类记账。[来源 LeRobot / robocasa，已实现·源码]
**R9. 任务表示分离"结构化目标"与"指令渲染"**：同一任务以谓词/目标结构表达，FSM 读谓词、Jev 读目标、LLM 由结构生成指令（可配 RLBench 式多同义指令测鲁棒性）；多步任务用 Q-score 部分得分。[来源 BEHAVIOR-1K BDDL + RLBench paraphrase，已实现·源码]
**R10. 策略工具 schema 内嵌边界**：`strict:true`、越界值在 schema 层不可表达；危险动词按类设访问门槛，ESCALATE 永远可选；循环守卫（连续相同动作签名）。[来源 roboagent-os JSON Schema + quackd 置信地板/_route，已实现·源码]
**R11. 占领三块空白**：证据链、token 成本追踪（每策略每次决策的输入/输出 token 与美元成本入基准表）、策略级延迟/成本对比——全生态无先例，属 FlexCell 新表面积。[缺席证据：LeRobot/robomimic/robocasa + 四 benchmark 栈均无；设计细节为本报告推测]
**R12. 反模式清单（勿犯）**：`getattr` 按名派发、LLM 代码 `exec`、无门直达执行器、手写重复 schema、仅靠对话历史当状态、无限重试、抢占即 abort、恢复全部进 LLM 上下文。[来源 ROS-LLM/RoboOS/robochain/Nav2 反例，已实现·源码]
**R13. 取消与中断做成预声明结构**：skill/任务描述里带 `cancellation_cleanup`（取消时要跑的清理动作序列）；中断用带 labels（为什么断）的 RAII 句柄，析构即恢复；中止语义 ≠ abort 当前动作。[来源 Open-RMF rmf_task_sequence Task::Builder / RobotUpdateHandle::Interruption，已实现·源码]
**R14. 失败终态扩为可操作分级 + 下发闭环**：在 R2 三终态之上加 BLOCKED（需人工，挂 Alert 三级 tier 等响应）与 FAILED（终局）；决策下发必须 ack + 过期重派（DispatchCommand→DispatchAck 模式）；任务状态 checkpoint 落盘，重启恢复。[来源 Open-RMF Event::Status 十态 / Alert.msg / DispatchAck / BackupFileManager，已实现·源码]

---

## 附录：调研覆盖与确定性说明

- 六路调研全部 GitHub 源码级、commit 固定（各线 SHA 见正文）。
- 各线原始报告的确定性机制统一为 [SOURCE: repo/file#L] → 本报告映射为 **[已实现·源码]**；[DOCS] → **[官方文档]**；[SPECULATIVE] → **[推测]**。
- 明确未覆盖/失败项：BehaviorTree.CPP v5（无发布分支，仅官网设计文档且抓取失败）[推测]；`FollowCartesianPose`/`MoveAndGrasp`（疑闭源 SDK）[推测]；openvla-oft（无权威仓，视为社区变体）[推测]；BEHAVIOR `eval_with_jobqueue` 模块（克隆中缺失）；CoinAgent/AWS RoboRunner/Isaac Agent Skills（不存在/闭源，未分析）。
- 本轮全部为只读调研：无迁移建议、无新框架引入，主线保持 ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2。
