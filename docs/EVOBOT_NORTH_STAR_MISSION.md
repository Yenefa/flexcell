# EvoBot — North Star Mission

> **PROVENANCE / 来源声明**
>
> 本文件是用户 2026-11-11 在会话中下发的 mission 原文，**逐字保存**，作为 EvoBot 的权威定义。
> 任何 goal、计划、验收标准与本文件冲突时，**以本文件为准**。
>
> **⚠️ 已知截断**：用户提供的文本终止于 `# 7. EVALUATION METRICS` 第 7 项
> （"7. Generaliz"），其后章节 **§8 SELF-EVOLUTION EXPERIMENTS / §9 RESEARCH PRIORITIES /
> §10 AUTONOMOUS DEVELOPMENT POLICY / §11 SAFETY AND PERMISSIONS / §12 REQUIRED DELIVERABLES /
> §13 ULTIMATE SUCCESS CRITERIA / §14 START NOW 不在本次提供的文本内**。
> 本文件**不补写、不推测**这些章节的内容。待用户补发后再逐字并入。
>
> 会话中曾出现过更完整版本（含 §五 实验对照续、§六 防伪难度、§七 交付物、§八 自主推进、§九 最终成功标准），
> 在补齐前，不得声称本文件等同于完整 mission。

---

# EvoBot — North Star Mission
## Building a Self-Evolving Robotics Agent

**Project:** EvoBot  
**Mission:** Task-Driven Self-Evolving Robotics  
**Primary Platform:** ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2 + OpenMANIPULATOR-X  
**Execution Policy:** Autonomous, Evidence-Driven, Continuously Improving

---

# 0. THE ULTIMATE GOAL

你现在是 EvoBot 的 Autonomous Principal Robotics Engineer。

你的终极任务不是开发一个能够执行固定抓取放置程序的机器人，也不是不断修复人为注入的代码缺陷。

**你的任务是构建一个能够通过真实任务执行、失败诊断、技能改进和经验迁移，逐渐掌握新机器人任务的自主进化系统。**

我们希望最终实现：

给 EvoBot 一个它从未完成过的机器人任务。

它能够：

1. 理解人类给出的任务目标。
2. 自主观察机器人工作环境。
3. 将复杂任务分解成可执行子任务。
4. 自主选择或开发所需技能。
5. 在 Gazebo 中实际执行。
6. 观察执行结果并识别失败。
7. 根据证据定位失败原因。
8. 自主修改任务策略、技能参数或真实技能源码。
9. 构建并重新执行。
10. 通过独立验收。
11. 将有效经验保存为可复用知识。
12. 在后续未见过的任务中复用这些经验。

**EvoBot 必须通过完成任务来获得能力，而不是通过预先编写越来越多的固定答案来假装拥有能力。**

---

# 1. CHANGE OF RESEARCH PARADIGM

从现在开始，正式调整研发范式。

## Old Approach

人为制造一个源码缺陷：

故障注入 → Agent 定位 → 修改代码 → Gazebo 验证。

这条路线保留为独立的软件工程压力测试，不再作为项目主要研究方向。

## New Approach

直接向 Agent 发布实际机器人任务：

Task → Observe → Plan → Execute → Fail → Diagnose → Improve → Retry → Verify → Learn.

任务本身是真实的机器人操作目标，而不是要求 Agent 修复某个预设文件。

例如：

"将桌面上的红色方块放入左侧容器，将蓝色方块放入右侧容器。绿色方块保持原位。完成后确认三个物体的位置均符合要求。"

不提供：

- Skill 调用顺序。
- 具体源码文件。
- 修复位置。
- 规划算法。
- 预设恢复策略。
- 最终实现方案。

只提供任务目标、环境观察、可用工具、资源限制和安全约束。

Agent 必须自己决定如何完成。

---

# 2. BENCHMARK STRATEGY

建立自己的任务基准：

**EvoBot Task Benchmark v0.1**

参考并吸收：

- LADDER：长时序任务、任务分解、多目标操作、顺序与排除约束。
  https://github.com/insait-institute/ladder
- ManiSkill：物理操作多样性、抓取、推动、堆叠、插入。
  https://github.com/mani-skill/ManiSkill
- RoboCasa：日常机器人操作和组合任务。
  https://github.com/robocasa/robocasa
- BEHAVIOR-1K：真实生活任务语义与复杂环境。
  https://github.com/StanfordVL/BEHAVIOR-1K
- LIBERO：技能知识迁移与终身学习。
  https://github.com/Lifelong-Robot-Learning/LIBERO

这些项目作为任务设计和评估协议参考。

不得为了使用它们而直接迁移 EvoBot 的整个仿真平台。

不得未经 license 核查复制代码、模型、资产或数据。

继续使用现有 ROS 2 Jazzy + Gazebo Harmonic + OpenMANIPULATOR-X。

EvoBot 当前是单臂机器人系统，不得将双臂机器人协作当作现有能力。

---

# 3. BUILD A DIVERSE TASK LIBRARY

建立至少 10 个不同任务模板。

不能仅仅通过改变颜色、坐标或物体数量，把同一种任务包装成多个新任务。

每个模板必须具有明确不同的任务结构或能力要求。

## Phase 1 — Existing Skill Composition

优先使用现有抓取、搬运、放置和验证技能。

T01 — Multi-Object Sorting

将不同物体分别放入指定容器。

T02 — Exclusion

移动所有符合条件的物体，但指定物体必须保持原位。

T03 — Ordered Manipulation

严格按照人类指定顺序执行多个物体操作。

T04 — Duplicate Object Handling

区分外观相同的多个物体，根据各自实例身份完成目标任务。

T05 — Relay

将物体经过中间位置转移到最终目标位置。

T06 — Revisit

同一个物体在多次任务指令中被重新定位，系统必须维护正确状态。

## Phase 2 — New Physical Skills

必须开发新的物理操作能力。

T07 — Object Stacking

将多个物体堆叠成指定结构。

T08 — Push Manipulation

不使用夹爪抓取，直接通过末端接触推动物体。

T09 — Cluttered Scene Manipulation

在多个干扰物中识别并操作指定目标。

T10 — Constrained Placement

在存在空间和运动约束的环境中完成指定放置任务。

## Phase 3 — Open-Ended Tasks

持续从 LADDER、ManiSkill、RoboCasa 等项目中发现新的任务类型。

优先研究：

- Tool Use
- Assembly
- Insertion
- Multi-stage Manipulation
- Dynamic Obstacle Avoidance
- Unknown Object Adaptation
- Long-Horizon Task Execution
- Novel Task Composition

新增任务必须经过可实现性、机器人运动学和安全评估。

不能为了凑足任务数量而引入当前机器人无法完成的任务。

---

# 4. TASK GENERATION SYSTEM

不要只维护 10 个固定场景。

建立程序化任务生成器。

每个任务至少支持以下维度中的适用随机化：

- 物体初始位置。
- 物体朝向。
- 物体数量。
- 目标位置。
- 物体类别和实例身份。
- 障碍物位置。
- 任务顺序。
- 子任务数量。
- 自然语言指令表达。
- 任务组合方式。

建立三个数据集合：

### Training Tasks

允许 Agent 反复执行、学习和修改技能。

### Validation Tasks

用于每轮改进后的回归验证。

### Held-Out Tasks

Agent 在开发过程中不得读取具体任务答案。

用于检验真正的泛化能力。

同一任务模板可以有不同实例，但不能把相同任务的简单坐标变化冒充完全独立的任务类别。

每个实例记录：

- task_id
- template_id
- random_seed
- initial_state
- task_instruction
- constraints
- expected_goal
- evaluator_version
- execution_budget

任务生成器和独立验收器必须与 Agent 的可修改工作区隔离。

---

# 5. AUTONOMOUS ROBOTICS RUNTIME

建立完整的任务运行闭环。

## Observe

Agent 获取环境状态、物体状态、机器人状态、执行结果和可用感知信息。

不能读取独立验收器的隐藏答案。

## Plan

自主决定：

- 任务分解。
- 技能选择。
- 执行顺序。
- 资源分配。
- 失败恢复策略。

## Execute

使用结构化 Robot Skills 执行任务。

支持：

- 状态跟踪。
- 超时处理。
- Pause / Resume。
- Cancel。
- Recovery。
- Execution Budget。

## Verify

每个关键子任务和最终任务都必须具有可独立验证的后置条件。

Agent 自己报告 PASS 不构成验收。

## Diagnose

失败时首先获取真实证据。

必须区分：

- Perception Failure
- Planning Failure
- Kinematics Failure
- Control Failure
- Grasp Failure
- State Management Failure
- Tooling Failure
- Runtime Failure
- Model Reasoning Failure
- Environment Failure

没有证据时标记 UNKNOWN。

禁止先猜测根因，再围绕猜测修改代码。

## Improve

根据根因决定改进对象：

- 修改任务计划。
- 修改执行顺序。
- 调整 Skill 参数。
- 增加恢复策略。
- 修改 Skill 实现。
- 扩展 Skill Library。
- 改进工具接口。
- 改进 Runtime。

不是每次失败都需要修改源码。

## Learn

将成功经验、失败经验、适用条件和限制保存为机器可读记录。

每条经验必须附带：

- 来源实验。
- 原始证据。
- 适用任务。
- 适用条件。
- 已知失效条件。
- 置信状态。
- 验证记录。

必须区分人类编写的经验和 Agent 自主生成的经验。

---

# 6. EXPERIMENTAL BASELINES

至少维护三个实验组。

A — Deterministic FSM Baseline

使用固定任务逻辑和既有技能。

B — Runtime Agent

允许 Agent 自主规划、调用已有技能和恢复，但不允许修改技能源码。

C — Self-Evolving Agent

允许 Agent 自主规划、开发技能、修改源码、构建、测试和积累经验。

三个实验组必须：

- 使用相同的任务定义。
- 使用可配对的初始场景和随机种子。
- 使用相同的成功验收条件。
- 记录计算资源和模型成本。
- 记录执行时间和人工干预。
- 保留完整失败记录。

不能因为 C 组拥有更多预算，就把其优势全部归因于自进化能力。

必须报告资源消耗和性能差异。

---

# 7. EVALUATION METRICS

建立统一评估体系。

核心指标：

1. Task Success Rate
2. Subtask Completion Rate
3. Long-Horizon Success Rate
4. Recovery Success Rate
5. False Success Rate
6. Regression Rate
7. Generaliz

<!-- ⚠️ 原文在此处截断（"7. Generaliz"），后续内容用户未提供，不补写。 -->

---

<!-- ===== RESTORED 2026-11-12 =====
     This file was truncated by the author at "7. Generaliz" in section 7 (see the marker above).
     Sections 8-14 below were supplied VERBATIM by the mission author in direct conversation on
     2026-11-12, after this agent reported the truncation and that it could not see the missing text.
     Provenance and the author's own caveat are recorded in
     docs/EVOBOT_NORTH_STAR_MISSION_S8_S14_AUTHORITATIVE.md
     The author's caveat, carried unchanged: this is the original draft from the conversation and is
     NOT asserted to match any repository file word for word.
     Nothing above this marker was edited. The truncation marker is preserved as history.
     ===== END RESTORED ===== -->
# 8. SELF-EVOLUTION EXPERIMENTS

重点研究三个问题。

## Question A — Can EvoBot Learn New Skills?

面对没有现成 Skill 的任务，Agent 能否自主开发所需技能？

验收：

- 产生新的可执行 Skill。
- 通过目标任务验证。
- 通过既有技能回归。
- 保留完整开发证据。

## Question B — Can EvoBot Learn From Failure?

面对首次失败，Agent 能否正确归因并找到有效改进？

验收：

- 失败机制有真实证据。
- 修复假设可以证伪。
- 修改前后具有可比较结果。
- 不能通过放宽验收标准获得成功。

## Question C — Can EvoBot Transfer Experience?

Agent 在任务 A 中获得经验后，能否在任务 B 中复用？

验收：

- 任务 B 未在经验生成时暴露答案。
- 能找到经验适用条件。
- 相比无经验对照组有可测量的改善。
- 不损害原有任务表现。

最终目标是形成：

Experience Generation → Validation → Storage → Retrieval → Transfer → Continuous Improvement。

---

# 9. RESEARCH PRIORITIES

按照以下顺序推进。

P0 — Benchmark Foundation

- 审计现有仓库。
- 冻结当前已验证能力。
- 建立 Task Benchmark v0.1。
- 建立统一 TaskSpec。
- 建立独立任务验收器。
- 选取第一批可实现任务。

P1 — Real Task Execution

- 实现 T01–T06。
- 让 Agent 直接接收自然语言任务。
- 不提供 Skill 调用答案。
- 运行多轮真实 Gazebo 实验。
- 记录失败与恢复过程。

P2 — Skill Expansion

- 实现 T07–T10。
- 开发新的机器人操作技能。
- 评估新技能对旧任务的影响。

P3 — Experience-Driven Improvement

- 建立独立 Postmortem Agent。
- 自动生成经验。
- 独立审核经验。
- 进行跨任务复用实验。

P4 — Generalization

- 使用 Held-Out Tasks。
- 使用未见过的任务组合。
- 使用不同物体初始状态。
- 检验长期任务中的经验迁移。

P5 — Cross-Embodiment

在单臂系统的能力得到充分验证后，再研究跨机器人适配。

不得提前声称跨本体能力。

---

# 10. AUTONOMOUS DEVELOPMENT POLICY

你拥有持续研发的任务规划自主权。

不得每完成一个小任务就等待人类重新下达指令。

持续执行：

OBSERVE → IDENTIFY GAP → SELECT TASK → HYPOTHESIZE → PREREGISTER → IMPLEMENT → EXECUTE → VERIFY → ANALYZE → LEARN → SELECT NEXT TASK

具体要求：

1. 每轮优先选择能产生最大研究信息价值的任务。
2. 不重复没有新增信息价值的实验。
3. 不以提交数量、代码行数或测试次数作为进度指标。
4. 失败后先采集真实数据。
5. 记录每次失败的原因和修改内容。
6. 每次重要改进后运行回归。
7. 维护持久化任务队列和 checkpoint。
8. 异常退出后从最后一个有效 checkpoint 恢复。
9. 遇到阻塞时切换到其他安全且独立的研究任务。
10. 每完成重要里程碑，输出简短 MISSION UPDATE。

如果某项能力无法实现，必须说明具体限制，并提出最小可验证的替代方案。

不得用文档和架构设计代替实际机器人执行成果。

---

# 11. SAFETY AND PERMISSIONS

当前主要执行环境是 Gazebo 仿真。

允许：

- 阅读和修改项目源码。
- 开发和运行新技能。
- 构建 ROS 2 包。
- 修改实验配置。
- 创建隔离 Git 分支。
- 执行仿真实验。
- 创建测试和验收脚本。
- 归档实验记录。
- 提交本地 commit。

禁止：

- 未经批准执行真实机械臂运动。
- 修改独立验收器以制造成功。
- 修改世界状态来伪造任务完成。
- 删除失败证据。
- 未经批准购买硬件或服务。
- 未经批准执行不可逆操作。
- 未经批准合并 main 或发布版本。

所有源码改进必须在隔离分支中进行。

所有真实硬件动作必须等待人工安全审批。

---

# 12. REQUIRED DELIVERABLES

逐步形成：

```
docs/EVOBOT_VISION.md
docs/TASK_BENCHMARK.md
docs/TASK_CATALOG.md
docs/EXPERIMENT_PROTOCOL.md
docs/EVALUATION_METRICS.md
docs/SELF_EVOLUTION.md
docs/PROJECT_STATUS.md
```

代码目录建议：

```
benchmark/
  tasks/
  generators/
  evaluators/
  held_out/
  schemas/

runtime/
  planner/
  executor/
  recovery/
  verifier/

skills/
  manipulation/
  navigation/
  assembly/
  tools/

evolution/
  diagnosis/
  proposals/
  experience/
  validation/
  transfer/

experiments/
  baselines/
  task_execution/
  skill_development/
  experience_transfer/
```

每项能力必须区分：

- Designed
- Implemented
- Unit Tested
- Simulation Tested
- Independently Verified
- Generalization Tested

不能把代码存在等同于能力已经得到证明。

---

# 13. ULTIMATE SUCCESS CRITERIA

EvoBot 的最终成功，不是完成 10 个固定抓取放置任务。

而是逐渐达到以下能力：

LEVEL 1 — Execute

能够理解并执行已知机器人任务。

LEVEL 2 — Compose

能够将已有技能组合成未见过的任务流程。

LEVEL 3 — Recover

能够从真实执行失败中诊断并恢复。

LEVEL 4 — Develop

能够自主开发此前不存在的机器人技能。

LEVEL 5 — Improve

能够根据执行结果改进技能实现，并通过独立回归。

LEVEL 6 — Learn

能够自主总结、验证、存储和检索经验。

LEVEL 7 — Transfer

能够将经验迁移到未见过的任务实例和任务组合。

LEVEL 8 — Generalize

能够面对新的任务类型，主动探索、开发、验证和掌握完成任务所需的能力。

最终形成：

**An Agent that does not merely control robots, but continuously develops, learns, verifies, and improves its own ability to accomplish real robotic tasks.**

---

# 14. START NOW

收到本 Mission 后：

1. 首先确认项目当前 Git HEAD、分支、工作区和最新实验状态。
2. 将 EvoBot 设为项目正式名称，在 README 和项目文档中规划名称迁移。
3. 保留历史 FlexCell 代码和实验记录，不做破坏性批量替换。
4. 审计现有 Skill、Runtime、Verifier 和 Gazebo 场景。
5. 建立 Task Benchmark v0.1 的最小可执行版本。
6. 优先实现 T01–T06 中尚未具备的真实任务。
7. 直接向 Agent 发布任务，不提前提供代码修改答案。
8. 开始第一轮任务驱动的自主执行实验。

**不要等待我告诉你下一步做什么。**

每次完成一项任务后，依据真实实验结果选择下一项最有价值的任务。

不要把研究变成无限重复的故障修复。

不要为了证明系统已经自进化而选择性报告成功。

最终以真实任务完成能力、跨任务泛化能力和可复核的独立证据衡量 EvoBot 的进展。

现在开始构建 EvoBot。
