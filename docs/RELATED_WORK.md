# RELATED WORK — 现成方案评估与集成决策

> 目的：**不是**找替代 FlexCell 的框架，而是找出能填补我们闭环缺口的成熟组件，并记录取舍理由。
> 核验日期 2026-11-08。所有"能力"陈述只写**能在其仓库/论文/文档中直接核实**的内容；未核实的一律标注。

## 0. 三条方法论约束（回应此前的批评）

1. **不写"可复用度百分比"**。组件存在 ≠ 能集成 ≠ 同等可靠性。本文件只给**逐项集成判定**与**待验证假设**。
2. **成熟度分四级**，不再用"我们已有"笼统带过：
   - **M0 设计**：只有文档/接口设计。
   - **M1 代码**：有实现，未系统验证。
   - **M2 测试通过**：离线/CI 通过。
   - **M3 真实执行证据**：有真实（或高保真仿真）运行记录 + 独立验证。
3. **"闭环粘合层"不天然具有创新性**。它必须通过对照实验证明（见 [PILOT_001.md](PILOT_001.md)），否则只是架构叙事。

## 1. 集成状态定义（四态，互斥）

| 状态 | 含义 | 允许的动作 |
| --- | --- | --- |
| **Direct Reuse** | 可直接作为依赖/格式使用 | 锁定版本引入 |
| **Adapter Required** | 能力可用，但需适配层才能进我们的契约 | 写适配器 + 契约测试 |
| **Conceptual Reference** | 只借鉴思想/接口设计，不引入代码 | 写入设计说明 |
| **Rejected** | 不采用 | 记录原因与复评条件 |

## 2. 逐项评估

### 2.1 RoboForge / Agentic Robot Creation（arXiv 2610.17881，2026-10-13）
- **已核实（摘要原文）**：把高层意图变成可运行机器人，分两轴——**本体生成**（embodiment creation，多模态模型产出机械设计，并提出计算指标在制造前评估）与**行为生成**（behavior creation：生成参考运动 → 配置学习目标 → 训练策略；**rollout 反馈可回改参考运动或奖励**）；在四种机器人上对照 reward-refinement 与 one-shot motion 基线；并**制造了一台 agent 生成的 Gorilla 并部署学习到的行为**。
- **已核实（2026-11-09，arXiv HTML）**：其"verification"是 **execution/rollout 作为物理验证信号**（原文：*Execution therefore serves as a physical verification signal rather than merely the endpoint of learning*）；失败时区分"行为请求错误"与"学习方式错误"，修订运动或奖励并重训。**不是**与执行器分离的独立验证器。代码公开性仍未确认（项目页存在）。
- **对我们的含义**：**不能宣称"无人做生成-验证-修订"**；其执行反馈机制与我们的 C 臂同构。我们的差异候选是 **ROS 软件工程层**（模块化技能契约、独立验证器、证据追踪、回归门），且 P1.2 显示"独立验证"当前无额外增益 → 差异仍是假设。
- **状态**：**Conceptual Reference**（代码未公开前不引入）。

### 2.2 RoboOS（FlagOpen，Apache-2.0，arXiv 2505.03673）
- **已核实（README）**：Brain-Cerebellum 分层；三组件 = Embodied Cloud Model（MLLM 做全局感知与高层决策）+ **Cerebellum Skill Library**（模块化即插即用技能）+ **Real-Time Shared Memory**（多智能体状态时空同步）；真实场景实验覆盖餐厅/家庭/超市，支持单臂/双臂/人形/轮式异构本体；运行需 **Redis + master/slaver 多进程 + Gradio UI**；**RoboOS 2.0（stand-alone 单机轻量版）尚未正式发布**（README 写"推迟数天"）。
- **已核实（2026-11-09，arXiv v2 全文检索）**：论文**未出现** postcondition / independent verification / evidence 的表述（0 命中）；仅提到 FlagScale 的 TB 级历史数据支持 "task replay / anomaly backtracking"。因此可说"**论文未记录技能级后置条件与独立验证**"，不能说"其系统没有"。
- **对我们的含义**：跨本体与多机协作**不是空白**；其技能库是"即插即用执行单元"，与我们的 **Skill Contract + 独立验证** 的差别是**文档级候选差异**。部署形态（Redis/多机/云模型）与我们"单机可复现 + 证据留痕"取向不同。
- **状态**：**Conceptual Reference**（当前不引入；若将来做多机/多本体，重评是否 Adapter Required）。

### 2.3 LeRobot（huggingface，Apache-2.0，28.7k★，2026-11 活跃）
- **已核实**：官方文档含 **OMX 专章**（OpenManipulator-X 硬件装配、Dynamixel 支持、`lerobot-find-port`、leader/follower 遥操作、数据采集与策略训练流程）；`omx_leader` 遥操作实现存在于源码。**注意：这是真机 leader/follower 形态**，与我们的**仿真** OpenMANIPULATOR-X 不是同一运行对象。
- **已核实（我方）**：本仓库已按 LeRobot 数据集格式导出（`scripts/export_lerobot.py`），并有相机数据管线与对账。
- **对我们的含义**：是 W2「学习型技能」最现实的入口；但**必须先确认硬件版本与控制接口**（真机 OMX 是 Dynamixel 直驱 + leader/follower 遥操作；我们的仿真走 ros2_control），因此是**Adapter Required**，且需要"仿真数据 → 真机策略"或"真机数据 → 仿真验证"的桥接实验。
- **状态**：**Direct Reuse（数据格式，已用）** + **Adapter Required（学习型技能接入 Skill Contract）**。

### 2.4 SWE-agent（MIT，20.7k★，2026-11 活跃）
- **已核实**：issue → 自动改代码 → 跑测试的 agent 循环；Python/MIT；持续维护。
- **对我们的含义**：**L1 开发 Agent 的 harness 骨架**参考。其"测试"是单测；我们的"测试"是 `colcon build + pytest + 仿真窗口门 + 证据`。集成点是**把我们的门包装成它的可执行命令**，并**锁死验证器/阈值**（防止"改测试过测试"）。
- **状态**：**Conceptual Reference（harness 设计）**；若要复用代码则升为 Adapter Required。

### 2.5 OpenHands（MIT，92.9k★，2026-11 活跃）
- **已核实**：AI 驱动开发的通用 Agent 平台，持续发布。
- **对我们的含义**：可作 **Dev-Agent 运行时**的候选宿主（与 Nexent Harness 并列评估）。**不迁移框架**是当前决定：先用最小自建循环验证"机器人门能否提升开发成功率"，再决定是否换宿主。
- **状态**：**Conceptual Reference**（宿主候选，待 Pilot 001 结果再定）。

### 2.6 ROSA（NASA-JPL，Apache-2.0，1.7k★，2026-11 活跃）
- **已核实**：自然语言查询/诊断/操作 ROS1&2 的 Agent。
- **对我们的含义**：**外部 Runtime Baseline**（对照组），用于检验我们的 Runtime Agent 是否真有优势；不集成进核心。
- **状态**：**Conceptual Reference**（作为 baseline 复现对象）。

### 2.7 IsaacLab / Isaac-GR00T（NVIDIA）
- **已核实**：IsaacLab 为 GPU 加速机器人学习/仿真框架，license 字段为 **NOASSERTION（商用前必须人工核对）**；Isaac-GR00T 为 Apache-2.0 的通用机器人基础模型。
- **对我们的含义**：**不进入现有 CI**——它们引入 GPU 依赖与另一套物理栈，证据与指纹不可与我们 CPU/llvmpipe Gazebo 混用。仅在"需要大规模课程/数据生成"时评估。
- **状态**：**Rejected（当前范围）**；复评条件：有稳定 GPU 资源 + 需要生成式数据规模。

### 2.8 TARSphere（xuyicheng-zju，Apache-2.0，30★，2026-10）
- **已核实**：面向长程具身 Agent 的全栈框架（论文 + 项目页）。**规模极小、很新**。
- **状态**：**Conceptual Reference（观察）**。

## 3. 与 FlexCell 的架构映射（按成熟度诚实标注）

| 工作包 | 我们的实际成熟度 | 依据 | 现成可借 | 缺口 |
| --- | --- | --- | --- | --- |
| W1 开发 Agent | **M0（无闭环）** | 代码由人写、人看日志修 | SWE-agent/OpenHands 循环、ROScribe 的 spec→ROS 思路 | 机器人门接入、证据驱动修复、迭代轨迹 |
| W2 技能与组合 | **M2 部分** | composite 单链在本机仿真 M3 级验证过；**pause/resume 未端到端验收** | LeRobot（数据/策略） | pause/resume 验收、学习型技能接入契约 |
| W3 Runtime Agent | **M2** | FSM/Jev/LLM/Hybrid 有实现与离线测试；核心窗口 M3 | ROSA（baseline 对照） | 与外部 baseline 的**对照实验**、资格统计 |
| W4 证据与复现 | **M2–M3** | episode/decision/evidence/指纹/回放已在 CI 使用 | —（此块外部最弱） | 人类可读失败归因报告 |
| W5 经验与改进 | **M0–M1** | 有失败码与 TransferBench 度量雏形，**无自动改进闭环** | Voyager/Eureka 的"可验证改进"思想 | 归因→提案→回归门 |
| W6 跨场景迁移 | **M1** | TransferBench 设计 + T1/T3 试点 | — | 五轴成本自动化 |
| W7 跨硬件迁移 | **M0** | 仅设计意图 | RoboOS（跨本体抽象） | 适配层 + T5 实验 |

> 说明：上表的 M 级是**保守判定**；"有测试"只记到 M2，只有具备真实/高保真执行记录且独立验证通过才记 M3。

## 4. 差异化定位（待实验检验，不作为结论）

**候选差异（需 Pilot 001 支持或推翻）**：
1. **机器人门驱动的开发闭环**：把"仿真执行 + 独立验证 + 证据"作为 Dev-Agent 的测试反馈，而非仅单测。
2. **执行成功 ≠ 任务成功的强制分离**：独立验证器裁决，阻止"跑完就算成功"。
3. **证据可回放**：同输入可复跑、判定一致，支撑教学/科研复核。

**已知会被质疑的点**：这些是否是"工程包装"而非研究贡献？→ 用**对照实验**回答（Pilot 001 两臂设计）。

## 5. 集成决策汇总

| 项目 | 状态 | 决策 | 复评条件 |
| --- | --- | --- | --- |
| LeRobot（数据格式） | Direct Reuse | 继续使用 | — |
| LeRobot（学习型技能） | Adapter Required | 待硬件/接口确认后做接入实验 | 有真机 OMX 或仿真遥操作数据 |
| SWE-agent | Conceptual Reference | 借循环与 ACI 设计，不引入代码 | 若自建循环成本过高 |
| OpenHands | Conceptual Reference | 作为 Dev-Agent 宿主候选 | Pilot 001 结果 |
| ROSA | Conceptual Reference | 作为 Runtime 外部 baseline | 需要对照实验时 |
| RoboOS | Conceptual Reference | 不引入（Redis/多机/2.0 未发布） | 做多机/多本体时 |
| RoboForge | Conceptual Reference | 精读论文后再判 | 代码公开或论文精读完成 |
| IsaacLab / GR00T | Rejected（当前） | 不进入 CI | 有稳定 GPU + 需生成式数据 |
| TARSphere | Conceptual Reference | 观察 | 代码成熟度提升 |

## 6. 待办（把"未核实"变"已核实"）

- [ ] 精读 RoboForge 全文：verification 的具体机制、是否开源、ROS 集成方式。
- [ ] 精读 RoboOS 技术报告：技能库是否要求后置条件验证、证据是否可回放。
- [ ] 核对 LeRobot OMX 的硬件版本与接口（Dynamixel 直驱 vs 我们的 ros2_control 仿真）。
- [ ] 复现 ROSA 的最小"NL→ROS 操作"用例，作为 Runtime baseline 的第一条数据。
