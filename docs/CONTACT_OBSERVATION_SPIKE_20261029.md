# 原生接触观测：固定声明

此声明、world、插件、门禁和运行脚本先于执行提交。沿用 #71 的 NO_GO 决定。
本窗口是**一次独立传感器链路 spike，0 次机器人逻辑任务**；没有机械臂、夹持、
相机、模型、训练或硬件。不替代 #56 的 attach/contact 用例，也不签 #57 的 GO。

## 复用上游及观测语义

使用 Gazebo Harmonic 官方 Contact 系统和 contact sensor，请求由 Physics 填充的
`components::ContactSensorData`。一方 `ContactTrace` 只在 PostUpdate 读取该组件、
实际 link 位姿和 collision ID，逐物理步保存原始 protobuf JSON；不创建组件、不
计算接触力、不改 pose、速度、碰撞或绑定约束，也不再发明抓持后端。

核对的上游版本是当前安装的 gz-sim 8.15.0，固定参考提交
[`446a443`](https://github.com/gazebosim/gz-sim/tree/446a44335a45b704b4d36dabcc5508ee34eeb3d8)。
官方 [Contact.cc](https://github.com/gazebosim/gz-sim/blob/446a44335a45b704b4d36dabcc5508ee34eeb3d8/src/systems/contact/Contact.cc)
说明 `Only publish if there are contacts`。因此 topic 沉默不能证明没有接触。
[Physics.cc](https://github.com/gazebosim/gz-sim/blob/446a44335a45b704b4d36dabcc5508ee34eeb3d8/src/systems/physics/Physics.cc)
在无接触时清空组件；接触附加数据是否存在取决于 physics engine。我们记录每个
物理步的组件快照，包括空集合和缺组件；稳态时组件不发生 change 不等于传感器断流。

四种状态严格区分：

| 原始观测 | 状态 | 力值 |
| --- | --- | --- |
| 无组件/无观测 | UNKNOWN | null |
| 有组件，未报告接触 | NO_REPORTED_CONTACTS | null |
| 报告接触但无完整力消息 | CONTACTS_FORCE_UNKNOWN | null |
| 每个接触点有有限的双边 force 消息 | CONTACTS_WITH_FORCE | 实测向量之和的模 |

Protobuf JSON 可省略标量零值，所以**存在的 force 消息**内部省略的轴表示零；
整个 force 消息不存在时不能补零。NaN/Infinity 原样保留为 protobuf JSON 字符串，
门禁在全窗口任何位置发现非有限数据都拒收。torque 未提供不推断为测到零扭矩。
原始 body_1/body_2 方向保留，当前只验总力的模，不声明已标定目标物体的有符号力。

## 一次固定 world 的三个控制

[`infra/contact-probe.json`](../infra/contact-probe.json) 固定同一个 2 ms DART world：

- A：50 g、35 mm 箱子起始位于水平地面，配置 contact sensor。预先固定分析
  `[1.0, 2.0]` 仿真秒内的 501 步，至少 476 步报告完整 force，总力模均值应在
  `0.392–0.588 N`，即 `m*g=0.49 N` 的 ±20%。其余未报告接触步仍保留且不补零。
- B：同尺寸静态箱子悬空，配置 contact sensor。0.2 秒后组件必须存在、接触集合为空。
- C：同尺寸地面箱子不配置 sensor。0.2 秒后实际 body/collision 必须存在，但组件
  应缺失并明确 UNKNOWN，不能把目标名字写错后的缺对象误充“缺传感器”正例。

完整运行 1,200 步，严格保留每个 2 ms 帧、各模型位姿、collision 绑定和原始 protobuf。
首个 PostUpdate 时间允许 Gazebo 的 0 或首个 2 ms 时刻；后续必须逐 2 ms 连续，
monotonic 时间严格递增，不能剪裁异常帧。加载器实际映射的 observer/Physics/Contact/
DART 库路径与哈希保存，observer 必须等于当次 install 身份记录。

world SHA256 固定为
`c3325093739d0156690251cae9811d96c247c1f28ef6fcff1529a4eebec1b81c`。
只允许一次此声明窗口。源码/安装/库身份未知、启动失败、缺帧、力数据缺失或门禁
失败时停止，保留全部输出，不切换引擎、不更换阈值或补成功样本。

## 执行和边界

```sh
python3 scripts/contact_probe.py --out /artifacts/contact-probe-UNIQUE
```

源代码与构建产物先核对，声明和结果独立落盘。单独进程组、随机 transport partition，
有界等待与仅自己进程的清理；不使用按进程名全局 kill。CI 以同一声明运行原生探针，
包括失败的原始日志都上传。任何后续诊断窗口必须另行固定声明、关联原失败，不能
修改历史结果。

即便通过，只能说明本固定场景的 contact/force 数据链路可用。没有执行无接触
预定位参考、绑定时十秒 contact trace、五轮整机 attach、整机自由落体、S2 同轮
故障注入或 legacy 矩阵。D3 继续 **NO_GO**，默认运行后端、旧数据与模型冻结不变。
