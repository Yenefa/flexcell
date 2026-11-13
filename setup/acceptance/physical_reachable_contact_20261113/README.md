# 可达接触姿态：从运动前拒绝到三段推动

同一 Gazebo 任务、同一物体初始世界、同一验收和预算，原固定 85° 控制器在初始位置 `(0.235, 0.025, 0.0175) m` 登记失败，零运动、零位移；候选连续两次完成三段接触推动及返回，净位移分别为 **91.389 mm、91.408 mm**，均通过完整 **9/9** 独立验收。

| 固定实验槽 | 结果 | 返回后净位移 | 实际姿态顺序 | 动作预算 | Runtime 耗时 |
|---|---|---:|---|---:|---:|
| 原失败 LONG_POS，CI 43448943203 | 运动前拒绝；fixed-pitch target unreachable | 0 mm | 固定 85°，未执行 | 0/40 | 0.634 s |
| ANCHOR，CI 43455056965 | 完整 9/9 PASS | 60.945 mm | 85° → 85° | 24/40 | 216.782/600 s |
| LONG_1，同一失败任务 | 完整 9/9 PASS | 91.389 mm | 79° → 85° → 85° | 36/40 | 327.534/600 s |
| LONG_2，同一失败任务 | 完整 9/9 PASS | 91.408 mm | 79° → 85° → 85° | 36/40 | 325.217/600 s |
| REG_NORMAL | 普通抓取、放置及验证功能 smoke PASS | 不适用 | legacy 后端 | 自身原预算 | 18.740 s task |

原拒绝保留在[位置探针归档](../physical_position_contact_20261113/README.md)。新旧 LONG 的 TaskSpec 与实际 world SHA 完全一致；本归档的重放程序检查该关系。两次 LONG 均为三个 30 mm 有界请求，实际净位移包含小幅接触超调；不据此宣称精密位移控制。

修复位于独立物理能力包的 `register_reachable_finger`：优先 85°，在 85°–73° 之间以 1° 步长搜索；每个候选仍经过原真实手指网格接触、支撑法向、关节、桌面和受保护物体约束，并筛查推进路径。筛查点不是连续碰撞证明；执行器原有的密集轨迹检查仍决定是否派发。执行层通过现有 `plan_observed` 运行纯几何计算，期间继续处理观测。没有可行姿态时拒绝执行。

8 次真实技能返回均满足返回完成、末端就绪及终态已知要求；Runtime 消费时记录的新鲜度为 46.2–139.8 ms。原任务仍选择 85°。九个冻结文件、`contracts/push.py`、旧 TaskSpec、物理环境参数、阈值和默认后端未改。

实施提交：`3c6292f82fd8d70d9beb5da40aa04210294bc45b`。实际执行源：`31a002f6cf4980750207fc7b09def6483ccfb971`。物理 CI [43455056965](https://github.com/Yenefa/flexcell/actions/runs/43455056965) 成功，同一镜像先通过 142 项相关检查；独立模块边界 CI [43455056891](https://github.com/Yenefa/flexcell/actions/runs/43455056891) 成功，其中 ROS 回归 170 项。这两个测试集合有重叠，不累计成物理成功次数。

原始 ZIP、原始 `results.json` 和不可变哈希见 `archive.json`。`offline_verification.json` 为离线重建：覆盖全部 462 个 manifest 文件，重新生成三份轨迹/接触证据，复现全部 9/9，核验 8 次返回以及普通任务结果；不执行仿真。使用本证据提交的源码运行：

```bash
python3 setup/acceptance/physical_reachable_contact_20261113/verify_archive.py \
  setup/acceptance/physical_reachable_contact_20261113/raw-43455056965.zip /tmp/reachable-contact-replay
```

只证明已登记的直立 35 mm 方块、世界 −x 方向下，一个此前不可达起点的工程能力扩展。LONG 已用于诊断，是暴露开发任务；两次重复不证明总体可靠性、盲测泛化或硬件能力。普通 smoke 使用仿真专用搬运后端，且不是完整任务回归。未证明 Runtime 自主开发技能、经验迁移或 L4。Legacy 仍为默认，正式基线 **NOT_PROMOTED**，正式 T08 仍 **CALIBRATION_UNSUPPORTED**；主目标保持 active。
