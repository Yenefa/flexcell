# 真实接触抓取探针（grasp contact probe）

独立研发线：用**真实接触+摩擦**（而不是 DetachableJoint / 磁吸）让平行夹爪夹住并抬起刚体箱子，
把「到底能不能夹住、能夹多重、什么时候开始滑」变成可复现的测量，而不是口头判断。

- 分支：`research/grasp-contact-probe-20261119`
- 世界：`worlds/grasp_probe.sdf.tmpl`（渲染后每个 trial 一份 `world.sdf`）
- 插件：`src/GraspContactProbe.cc`（力控伺服 + 逐毫秒位姿/接触记录）
- 运行：`scripts/run_probe.py`
- 分析：`scripts/analyze.py`（由独立分析员实现，只读原始 JSONL）
- 结论：`REPORT.md`；磁吸对照：`MAGNET_BASELINE.md`；对抗性评审：`REVIEW.md`

## 为什么不是「接个库就完事」

几何（夹哪儿）与驱动（怎么闭合）确实接上就有；**能不能在抬起、加速时靠摩擦托住**是第三件事，
它由摩擦锥 `2·μ·N` 与载荷 `m·(g+a)` 的比值决定，不是代码问题。本探针只测这一件事。

## 复现

```bash
# 在 WSL Ubuntu-24.04（ROS Jazzy + gz-sim 8.15）里
source /opt/ros/jazzy/setup.bash
cd research/grasp_contact_probe

python3 scripts/run_probe.py --stage acceptance --out results/acceptance-v2 --rebuild
python3 scripts/run_probe.py --stage stress     --out results/stress-v3
python3 scripts/run_probe.py --stage magnet     --out results/magnet-v1   # 磁吸基线

python3 scripts/analyze.py --run-dir results/acceptance-v3 \
    --json-out results/acceptance-v3/summary.json \
    --md-out   results/acceptance-v3/REPORT.md

# 探索性对照（只出指标与摩擦锥核对，不给 PASS/FAIL）
python3 scripts/analyze.py --run-dir results/stress-v2 --stage stress \
    --json-out results/stress-v2/summary.json \
    --md-out   results/stress-v2/REPORT.md
```

## 世界契约（不要"顺手"改）

| 量 | 值 | 说明 |
| --- | --- | --- |
| 物理步长 | 1 ms | `max_step_size` |
| 张开间隙 | 0.056 m | 两指内表面间距 |
| 闭合指令间隙 | 0.020 m | 用户指定判据；对 35/50 mm 箱即「压进去」 |
| 抬升 | 0.15 m / 0.5 s | smoothstep 速度剖面，峰值 0.3 m/s |
| 保持 | 0.5 s | |
| 指力上限 | 20 N | 力控伺服 `F = clamp(kp·e - kd·v)` |
| 摩擦 | μ = 1.0 | 指垫、箱体、地面一致 |
| trial | box_a 5 次 + box_b 5 次 | 初始位姿抖动 ±1.5 mm / ±2°（预注册） |

**没有任何** `DetachableJoint`、fixed joint、teleport、attach/detach topic。物体只可能被接触力托住。

## 每 trial 产物

```
results/<run>/protocol.json          预注册判据（跑前写死）
results/<run>/<trial>/world.sdf      实际渲染的世界（含 sha256）
results/<run>/<trial>/meta.json      物体规格、抖动、插件/world/日志 sha256、加载的 dartsim 库
results/<run>/<trial>/steps.jsonl   逐毫秒：obj/base/rel 位姿、关节 q/qd/f、接触计数与峰值力
results/<run>/summary.json           分析器输出（指标+判定）
results/<run>/REPORT.md              分析器生成的报告
```

## 已知坑（都踩过，别再踩）

1. **world 插件的 `Configure` 早于实体创建** → 必须惰性解析实体，否则 `model not found` 直接 abort。
2. **`gz::sim::components::Joint` 不存在** → 用 `gz::sim::Model::JointByName`。
3. **`sdf::Element::Get<T>(key, default)` 返回 `std::pair<T,bool>`** → 别直接赋给 T。
4. **关节状态组件不会自己出现** → 物理引擎只刷新已存在的 `JointPosition/JointVelocity`，必须在 Resolve 里显式创建；否则力控伺服读到的永远是 0（开环），抬升会变成 80 N 猛抬。
5. **三个碰撞体都叫 `pad` 会让接触传感器串号** → 每个碰撞体唯一命名，并按 `msgs::Contacts` 的 `collision1/2` 分类伙伴。
6. **`JointForceCmd` 在 PostUpdate 读到的是 0**（物理步已消费/清理）→ 要记录指令力就用 PreUpdate 自己存的值，接触力用接触传感器读数。
