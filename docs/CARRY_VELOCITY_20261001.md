# Carry 速度约束接入主线（E-015，2026-10-01）

主线已部署 `velocity_servo_v1`：Gazebo 每个物理步同时约束箱子的位姿和速度，
释放后移除约束，500 ms 心跳租约到期也会释放。PICK 改为收到 carry engage
确认后才抬臂，部署入口检查 PLACE 自己能否发现 release 服务。
最终部署的单物体真实 Gazebo / MoveIt / ROS 闭环成功，位置误差 **2.86 mm**。
此前两个双物体批次有失败，均已归档；**本轮不是已通过的统计基线**。

## 实现与边界

- 新包 `flexcell_gazebo` 提供世界插件 `flexcell::CarryDynamics`。只允许
  `target_box_a/b`，每步设置 `WorldPoseCmd`、零线速度和角速度；不关闭重力。
  release 删除命令组件，并在本步 PostUpdate 后应答。物理释放实测为自由下落。
- 原生 engage/pin 携带 UUID 会话，pin 只能更新当前所有者；退役会话不能复活，
  旧会话 release 不能释放新会话。Python worker 停止并确认物理释放后才发布 off。
  worker 失联时由原生 500 ms 单调时钟租约兜底。
- 新 `EngageCarry.srv` 让 PICK 确认启动；丢应答可用同一请求 ID 重读，
  服务器复用当前会话，不重新启动。退役 ID 会被拒绝。两次查询仍没有确认就
  返回抓取失败，**不启动 lift**。默认 `teleport` 保留旧口径，主线配置选新后端。
- 新 `/flexcell/place_ready` 从 PLACE 的实际客户端检查 carry release 发现情况。
  `108_wait_policy.py` 将此内部依赖纳入部署门禁，检查失败不能打印 DEPLOYED。
  这证明启动时依赖可用；不保证运行中所有 DDS 应答都会到达。
- `health` 中曾阻塞的 `ros2 control` CLI 被有截止时间的
  `ListControllers` 真实服务查询替换。新健康检查也要求 engage 服务存在。
- 主线 Cyclone 配置使用 MaxMessageSize=1400B、FragmentSize=1200B，
  针对 E-014 已观察的本机网络路径风险。没有证据证明此前 controller CLI
  超时由 DDS 分片引起，也没有把 Fast DDS 探针结论当作 Cyclone 的内部根因。

新 world 与原 world 的差别是插入此插件，箱体几何、质量、物理步长和技能
验收阈值保持原值。它仍是**磁性仿真 carry**：不模拟夹持力、摩擦和真实接触抓取。
这是新的物理实现，不能把旧 teleport 数据当作同一实验条件。
组件用法参照 [Gazebo 原生 VelocityControl 实现](https://raw.githubusercontent.com/gazebosim/gz-sim/gz-sim8_8.15.0/src/systems/velocity_control/VelocityControl.cc)，
DDS 配置含义参照 [Cyclone 官方配置说明](https://cyclonedds.io/docs/cyclonedds/latest/config/config_file_reference.html)。

## 已执行的闭环及失败

| 阶段 | 实际结果 | 含义 |
|---|---|---|
| 隔离原生插件生命周期 | PASS | 持有、显式释放、租约到期、旧会话拒绝均在真实 Gazebo 中执行 |
| 首次单物体 | SUCCEEDED，18.459 s，12.70 mm | 原生约束已能支撑实际 PICK / PLACE / VERIFY |
| 新物理首次 S1×5 | 4/5，runner RC=1 | 尚未加入 engage 确认；存在控制、模型和规划失败 |
| engage 确认后 S1×2 | 1/2，runner RC=1 | 一次双物体成功；一次 PLACE 内部发现失败 |
| 加内部依赖门禁后单物体 | SUCCEEDED，19.012 s，2.86 mm | 最终部署已完成真实 PICK / PLACE / VERIFY |

首批 S1 五回合逐项如下，不能只读总成功率：

1. A/B 均首次抓取并完成。
2. A/B 均首次抓取并完成。
3. B 首次 rise=0，未记录 carry 启动；B 重试 rise=89.46 mm 后完成。
   原始 topic 启动没有确认，是确定的设计缺口；没有证明消息具体丢在 DDS 哪层。
4. 模型在成功 OBSERVE B 后直接提议 PLACE B，被 `not_carried` 安全门拒绝。
   当次观察还包含 A 的旧 carry 状态；这是后续状态新鲜度和策略语义的调查入口。
5. B lift 规划失败 `ERR_NO_COLLISION_FREE_PLAN`。模型重观察后选择 PLACE，
   最终独立 VERIFY 通过；这证明任务完成，**不证明该次 PICK 通过**。

首批与首次单物体共有 11 次 PICK 记录：9 次测得正向 lift（89.46–104.71 mm），
1 次 rise=0，1 次 lift 规划失败、没有 rise。旧的负向 rise 没在这些成功抓取中出现，
但这个小样本不能证明可靠性改善的统计幅度。

第二批 S1 首回合 PICK 成功，PLACE 等 5 s 后报告
`carry release service unavailable; object remains attached`，随后任务终止；
第二回合完整成功。内部依赖门禁是针对这次具体失败的主线修复。
最终单物体不含 B 分支，因此最终部署的双物体整体可靠性仍未验收。

隔离物理探针持有高度最低 0.199755 m，显式释放后降到 0.009450 m，
租约到期后降到 0.009325 m。最初四次探针超时也保留在证据中：Python
Pose_V 订阅与同步 Gazebo request 同进程时出现干扰；把 pose recorder
分离为独立进程后完成。没有声称已定位其 Python/GIL 内部调用栈。

## 协议、模型、指纹与预算

全部机器人任务使用 protocol v2、官方 `deepseek-flash`、`LLMPolicy 2.3`。
本轮物理接入保持 `thinking=disabled/max_tokens=512`，便于隔离物理变化。
E-014 的三个 `thinking/max` 机制评审是单独诊断调用；不能称本轮实时策略为 max。
初始化无 world 的 OBSERVE 仍走明确记录的 FSM fallback：两次单物体分别
3 次真实模型决策 + 1 次 fallback，首批 S1 为 35 + 6，第二批为 12 + 2。
decision latency 来自实际 `policy.decide` 前后计时，不使用历史假 0.0。
首批 41 项计时为 0.036–5655.576 ms，第二批 14 项为 0.041–1299.564 ms；
小值对应 FSM fallback，不等于模型调用延迟。

| 阶段 | Runtime fingerprint |
|---|---|
| 首次单物体 | `8dd87d757ca88226491e5af32fea5c561430ded5921d673160004f4da0f0aac0` |
| 首批 S1×5 | `4381dad6aa575478551630ee51c90bfacf83675614375fba30d402ad71420690` |
| engage 确认后 S1×2 | `aa073fa2bb43640ac77866ce9224df34183173f56742820d6594a6946f6ba91f` |
| 最终依赖门禁部署 | `005eadb8dca9d3e691761297c5ca58f264b0fd88b88429593cfdf23a33434491` |

不同指纹不合并。E-011 protocol v1 继续仅作存档，E-013/E-014 冻结证据不改。
指纹加入原生源码、已安装插件、已安装 Python、接口定义、world、DDS 配置和
启动门禁源码；最终 carry/pick/place 源文件与已安装模块 SHA 均一致。

同一持久预算账本累计 **152 个请求记录，保守计费上界 ¥0.987406 / ¥5**：
151 项已按 usage 的峰时未命中价上界结算，1 项历史未知调用仍保留预算占用，
没有当作免费调用。凭证在私有 mode-600 文件，未进入源码、部署指纹或证据。

## 验收和下一步

已实际构建原生插件、接口和技能 overlay；8 项 carry 生命周期/确认契约测试通过，
包含首次应答丢失时同 ID 重读、退役请求保护、未确认释放不得发布 off。
这是控制契约测试；机器人行为证据来自上面的真实 Gazebo 闭环。
编译日志保留了本机时钟偏差警告。未重跑全套 colcon test，也未核验 rosdep 闭包。

最终 reset **RC=0 / ok=true**；scene 实际查询已清空、箱体 canonical、arm home。
原始 reset 同时报 `scene_apply_ok=false`，没有隐藏；最终状态由独立重读确认。
最后 health 19 项、hard_fail 空、IDLE；原生 status 为 engaged=false。
历史 reset RC=139 的根因仍未证明解决。GetResult 重读的适用边界继续按 E-014；
未宣称定位历史 Cyclone 首次应答丢失、gate_flood 的底层触发源或 MTC。

下一主线优先处理**观察到的 carry 新鲜度与目标关联语义**，再做同指纹各 cell
的五次冒烟。模型 replay 仍 NOT_RUN；现有 episode 证明真实在线决策记录，
不表示重放已通过。新物理 n≥50/100 执行方案另存
[`m3_velocity_batch_plan.json`](../setup/m3_velocity_batch_plan.json)，状态为冻结，
没有启动 400 回合，也不能拿混合指纹的 4/5 或 1/2 解锁基线。

证据在 [`carry_velocity_20261001`](../setup/acceptance/carry_velocity_20261001/manifest.json)：
包含全部失败尝试、各阶段 episode/deployment、关联执行器日志、最终源码快照、
原生插件及 SHA 清单。当前源码快照对应最终部署；早期阶段由各自部署摘要标识。

## 工作区交接

```text
Repo: /mnt/c/dev/flexcell
Remote: https://github.com/Yenefa/flexcell.git
Branch: main
HEAD: 5878c05
Changed: flexcell_gazebo; EngageCarry.srv/CMake; carry_server.py; pick_server.py;
         place_server.py; flexcell_admin.py; 98/102/104/108/116 scripts;
         velocity world; Cyclone config; carry tests; evidence/docs/batch plan
Tests actually run: native/interface/skills colcon builds PASS; carry pytest 8 PASS;
                    Gazebo lifecycle PASS; two single tasks PASS;
                    S1x5 FAIL (4/5); S1x2 FAIL (1/2); final single PASS;
                    final reset/health/native off PASS; static checks in manifest
Not run / limitations: full suite; final-fingerprint dual-object batch;
                       n>=50; model replay; rosdep closure; MTC;
                       historical Cyclone result-loss/reset139/gate_flood root causes
Workspace status: main ahead 2, tracked and untracked changes remain;
                  prior changes preserved; no commit or push in this turn
```
