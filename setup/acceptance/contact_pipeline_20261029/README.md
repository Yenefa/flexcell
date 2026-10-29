# 原生 contact/force 链路探针

声明先于运行提交：`3d9e9b49229bc6f4edf4327c44f9fcb876ad8b63`，见
[固定声明](../../../docs/CONTACT_OBSERVATION_SPIKE_20261029.md)。本地仅执行一次，
无替换；kind 为 `CONTACT_SENSOR_PIPELINE_SPIKE_ONLY`，逻辑机器人任务数 **0**。
运行指纹：`2516110b1b6addb0ce7f6f248cb264dac84499516b7abbeec864de8034342eec`。

结果为 **CONTACT_PIPELINE_PASS**，不属于 D3 默认准入：

| 控制 | 完整 1,200 步的原始观测 | 力的解释 |
| --- | --- | --- |
| A，地面 50 g 箱子，有 contact sensor | 1,200 CONTACTS_WITH_FORCE | 稳定 501/501 步力数据完整，向量和的模均值 0.4900000000667622 N |
| B，悬空静态箱子，有 contact sensor | 1,200 NO_REPORTED_CONTACTS | null，不能改写为实测 0 N |
| C，实际存在的地面箱子，无 sensor | 1,200 UNKNOWN | null，不能改写为实测 0 N |

从 0.002 到 2.400 仿真秒，1,200×2 ms 帧完整、monotonic 时间递增、控制 collision
身份独立且稳定。全段所有已提供的 pose、force、normal、depth 数值有限，原始双边
force 互为反向；已提供的 force 消息均保留，没有把未知消息填成 0。正控制的固定
1–2 秒稳定区间均值落在预声明 0.392–0.588 N 内。

实际进程映射记录确认 observer、gz-sim Physics/Contact 8.15.0、DART 7.8.0 的库路径
及哈希。observer 实际加载 SHA256
`aa2f6f6fe29f3e0633de55cd23660472a17db4f8aef67b5124fd409cd4aea4a2`
与该次 install 身份一致。simulator 和 owned process 均正常退出 0。

`probe_3d9e9b4/` 保留原始声明、world、完整日志、identity、进程身份、实际加载库和
结果。2,376,988 字节原始逐步 protobuf JSON 只做无损 gzip 压缩，解压后 SHA256
`d6506d244120a233425cd3dfa08ecd48bd7a0c309f038942fe84945a93b718bc`。
文件摘要在 `inputs.json`；原未压缩记录仍在交付工作区运行目录。

```sh
python3 setup/acceptance/contact_pipeline_20261029/verify.py
```

校验不启动仿真，会重算全部物理时序、三类控制和力模，不只核对结果文字。
CI 同时运行该归档复核和同声明原生探针；各自结果分开保留，不合并成可靠性样本。

边界：力的目标物体有符号方向尚未独立标定；body wrench 的 torque 未提供时仍是
未测量。这是静态载荷/悬空/缺传感器控制，没有机械臂、绑定、抓持、自由落体或
S2 实际故障注入。不能将本结果与另一窗口的附着位姿拼接，声称“绑定期间接触力
已验证”。旧 #71 A/B、两份 STOPPED、Phase-3 和数据集原样保留，D3 继续 **NO_GO**。
