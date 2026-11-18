# 真实接触抓取探针：探索分析报告（不产生 PASS/FAIL）

- run: results/stress-v3
- 协议: stress-v3 (protocol.json sha256 e7644f9bb02c71dac202c4a8c4444138d4fe2cdf4e208e896c7ba9515f8137f7)
- 模式: 探索（--stage/--exploratory）：只出指标与表格，不参与 verdict，不得写入 acceptance 结论
- 物理引擎（协议声明；运行期加载身份见各 trial meta.json）: gz-sim 8 dartsim
- 判据来源: protocol.json；本报告不改动任何阈值，ref 固定在 close 最后 50 ms。

## 预注册判据

| 判据 | 值 |
| --- | --- |
| 单 trial 平移漂移 | < 2.000 mm |
| 单 trial 旋转漂移 | < 5.000 ° |
| drop（基座系 z 下降） | > 20.000 mm |
| drop（ref 归一化偏差） | > 30.000 mm |
| lift 双侧 pad 接触下限 | 未预注册（仅报告） |
| lift 阶段 box 对地接触上限 | 未预注册（仅报告） |
| 总体判据 | 10/10 全部通过 |

> 探索模式不改变上述判据；它只用于核对物理趋势（摩擦、载荷、几何），任何探索结果都不得写入 acceptance 结论。

## 运行与完整性

| 项目 | 值 |
| --- | --- |
| stage / mode | stress / exploratory |
| trial 数 | 10（预注册要求 10） |
| 对象 | box_a×10、box_b×0 |
| 采样 | 每 trial 1701-1701 帧，中位步长 0.001000 s |
| 时间戳 | 全部严格递增（分析器拒绝乱序/重复 iter） |
| 对象身份校验 | exploratory_override+protocol_and_meta |

## 每 trial 指标

| trial | 对象 | 采样 | drift_t/mm | drift_r/° | drop | lift 双侧接触 | hold 对地 | 对地消失 t/s | 指令力 close max/mean N | 指令力 lift max/mean N | 实测接触力 lift 峰值 N | 观测滑移 | 对地证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stress-load-0.05kg | box_a | 1701 | 0.001 | 0.000 | 否 | 100% | 0% | 0.71 | 7.493 / 2.060 | 7.500 / 7.499 | 2.04 | 否 | lost_after_lift |
| stress-load-0.50kg | box_a | 1701 | 0.001 | 0.000 | 否 | 100% | 0% | 0.73 | 7.493 / 2.060 | 7.500 / 7.499 | 2.12 | 否 | lost_after_lift |
| stress-load-1.00kg | box_a | 1701 | 0.001 | 0.000 | 否 | 100% | 0% | 0.74 | 7.493 / 2.060 | 7.500 / 7.499 | 2.69 | 否 | lost_after_lift |
| stress-load-1.20kg | box_a | 1701 | 8.852 | 0.000 | 否 | 100% | 0% | 0.74 | 7.493 / 2.060 | 7.500 / 7.499 | 2.73 | 是 | lost_after_lift |
| stress-load-1.50kg | box_a | 1701 | 150.061 | 0.000 | 是 | 34% | 100% | — | 7.493 / 2.060 | 7.499 / 2.675 | 2.71 | 是 | still_touching_at_end |
| stress-load-2.00kg | box_a | 1701 | 150.059 | 0.000 | 是 | 33% | 100% | — | 7.493 / 2.060 | 7.499 / 2.555 | 2.70 | 是 | still_touching_at_end |
| stress-load-5.00kg | box_a | 1701 | 150.059 | 0.000 | 是 | 29% | 100% | — | 7.493 / 2.060 | 7.498 / 2.240 | 2.67 | 是 | still_touching_at_end |
| stress-mu-0.20-mass-500g | box_a | 1701 | 150.059 | 0.000 | 是 | 33% | 100% | — | 7.493 / 2.060 | 7.499 / 2.585 | 2.03 | 是 | still_touching_at_end |
| stress-fast-lift-1ms | box_a | 1701 | 0.001 | 0.000 | 否 | 100% | 0% | 0.70 | 7.493 / 2.060 | 7.498 / 7.497 | 2.05 | 否 | lost_after_lift |
| stress-thin-20mm | box_a | 1701 | 150.059 | 0.000 | 是 | 0% | 100% | — | 0.030 / 0.015 | 0.030 / 0.001 | 0.00 | 是 | still_touching_at_end |

力列说明：指令力取自 steps.jsonl 的 cmd.*（PreUpdate 缓存，是 pad 法向力的上界）；实测接触力取自 contacts.*_pad_force（求解器接触点 wrench 的单点峰值）。二者不等价：一个 pad 上可能有多个接触点，单点峰值小于该 pad 承担的总法向力，因此不能用实测单点峰值直接当 mu*N 的 N。

## 每 trial 一行摘要

- **stress-load-0.05kg** (box_a): —；drift 0.001 mm / 0.000°；对地接触消失 t=0.71（证据 lost_after_lift）；lift 双侧接触 100%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.04 N；观测滑移 否
- **stress-load-0.50kg** (box_a): —；drift 0.001 mm / 0.000°；对地接触消失 t=0.73（证据 lost_after_lift）；lift 双侧接触 100%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.12 N；观测滑移 否
- **stress-load-1.00kg** (box_a): —；drift 0.001 mm / 0.000°；对地接触消失 t=0.74（证据 lost_after_lift）；lift 双侧接触 100%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.69 N；观测滑移 否
- **stress-load-1.20kg** (box_a): —；drift 8.852 mm / 0.000°；对地接触消失 t=0.74（证据 lost_after_lift）；lift 双侧接触 100%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.73 N；观测滑移 是
- **stress-load-1.50kg** (box_a): —；drift 150.061 mm / 0.000°；对地接触消失 t=—（证据 still_touching_at_end）；lift 双侧接触 34%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.71 N；观测滑移 是
- **stress-load-2.00kg** (box_a): —；drift 150.059 mm / 0.000°；对地接触消失 t=—（证据 still_touching_at_end）；lift 双侧接触 33%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.70 N；观测滑移 是
- **stress-load-5.00kg** (box_a): —；drift 150.059 mm / 0.000°；对地接触消失 t=—（证据 still_touching_at_end）；lift 双侧接触 29%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.67 N；观测滑移 是
- **stress-mu-0.20-mass-500g** (box_a): —；drift 150.059 mm / 0.000°；对地接触消失 t=—（证据 still_touching_at_end）；lift 双侧接触 33%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.03 N；观测滑移 是
- **stress-fast-lift-1ms** (box_a): —；drift 0.001 mm / 0.000°；对地接触消失 t=0.70（证据 lost_after_lift）；lift 双侧接触 100%；指令力 close 峰值 7.49 N；实测接触力 lift 峰值 2.05 N；观测滑移 否
- **stress-thin-20mm** (box_a): —；drift 150.059 mm / 0.000°；对地接触消失 t=—（证据 still_touching_at_end）；lift 双侧接触 0%；指令力 close 峰值 0.03 N；实测接触力 lift 峰值 0.00 N；观测滑移 是

## 总体结论

**探索模式：不产生 PASS/FAIL。** 本 run 只有逐 trial 指标与摩擦/载荷对照，不参与 acceptance 判据，也不能用于声称可行性。

## 摩擦锥核对（friction_cone_check）

容量 = mu ×（左右指令指力之和）；载荷 = m × (g + a)，a 由预注册抬升曲线取最大值，本 run 取 3.60 m/s²（protocol rig.lift_height_m / phases_s.lift (smoothstep, 6h/T^2)）。

| trial | 质量 kg | mu | 单侧指令指力 N | 单侧实测峰值 N | 容量 muN N | 载荷 N | 预测滑移 | 观测滑移 | 一致 | 预测滑移质量 kg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stress-load-0.05kg | 0.05 | 1.00 | 7.50 | 2.04 | 15.00 | 0.67 | 否 | 否 | 是 | 1.12 |
| stress-load-0.50kg | 0.50 | 1.00 | 7.50 | 2.12 | 15.00 | 6.70 | 否 | 否 | 是 | 1.12 |
| stress-load-1.00kg | 1.00 | 1.00 | 7.50 | 2.69 | 15.00 | 13.40 | 否 | 否 | 是 | 1.12 |
| stress-load-1.20kg | 1.20 | 1.00 | 7.50 | 2.73 | 15.00 | 16.08 | 是 | 是 | 是 | 1.12 |
| stress-load-1.50kg | 1.50 | 1.00 | 7.50 | 2.71 | 15.00 | 20.10 | 是 | 是 | 是 | 1.12 |
| stress-load-2.00kg | 2.00 | 1.00 | 7.50 | 2.70 | 15.00 | 26.80 | 是 | 是 | 是 | 1.12 |
| stress-load-5.00kg | 5.00 | 1.00 | 7.50 | 2.67 | 15.00 | 67.00 | 是 | 是 | 是 | 1.12 |
| stress-mu-0.20-mass-500g | 0.50 | 0.20 | 7.50 | 2.03 | 3.00 | 6.70 | 是 | 是 | 是 | 0.22 |
| stress-fast-lift-1ms | 0.05 | 1.00 | 7.50 | 2.05 | 15.00 | 0.67 | 否 | 否 | 是 | 1.12 |
| stress-thin-20mm | 0.03 | 1.00 | 0.03 | 0.00 | 0.06 | 0.40 | 是 | 是 | 是 | 0.00 |

**结论**：符合 — 符合：10/10 trial 的观测滑移与库仑预测一致（容量 = mu x 两侧指令指力）。mu=1.0 时观测翻转区间为 1.00-0.03 kg，预注册预测 1.12 kg 不在该区间内。 注：若用日志中的单点接触峰值代替指令指力，只有 8/10 trial 一致——该峰值是单点力而不是总法向力，不能直接作为 mu*N 的 N。

预注册预测：滑移质量 1.12 kg（protocol.controls.load_ladder_prediction）。

观测翻转区间：1.00 kg 仍托住，0.03 kg 已滑移。

## 本结果不能证明什么

1. 仅两种尺寸/质量组合（35 mm-50 g、50 mm-120 g）与单一摩擦系数，未扫描尺寸-质量-摩擦参数空间；对其它几何、质量或摩擦组合的抓取能力没有任何证据。
2. 无视觉、无位姿误差、无传感器噪声注入：物体与基座位姿是仿真真值，夹持位姿完全由预注册几何决定；不能证明存在感知误差、标定偏差或物体位姿不确定性时的可行性。
3. 单一物理引擎（DART）与单一 1 ms 步长：接触刚度、摩擦锥离散化和穿透恢复都与步长、求解器耦合，结论不能迁移到其它引擎、其它步长或实时控制频率，也不能外推到真实硬件。

> 本报告只在 protocol.json 的预注册判据内给出 PASS/FAIL。PASS 表示该固定场景、固定参数下全部 trial 的基座系相对漂移低于阈值且未判为掉落；它不表示抓取成功率、不表示可部署性、不表示真实接触优于磁吸替代，也不表示物体在更重、更滑或更小的夹持余量下仍能被持住。
