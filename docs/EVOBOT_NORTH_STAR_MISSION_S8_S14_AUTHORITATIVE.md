# EVOBOT — NORTH STAR MISSION, §8–§14 (verbatim, supplied by the author 2026-11-12)

**Provenance**: supplied verbatim by the mission author in direct conversation on 2026-11-12, after this agent
reported that the repository copy was truncated at §8 and that it could not see the missing text.
**Author's caveat, carried verbatim**: *"这是对话中的原始草案，不代表它已经逐字匹配仓库文件。"* — this is the
original draft from the conversation and is **not** asserted to match the repository file word for word.

**Handling**: this is now the authoritative source of §8–§14. The repository copy is left unchanged; consistency
is recorded separately in `MISSION_S8_S14_DIFF_20261112.md`.

---

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
