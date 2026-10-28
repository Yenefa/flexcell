# 垂直轨迹观测器

PR #67 的 setup/114_carry_watch.py 分析最长抬升段中的静止保持窗口。它报告垂直
偏移、周期和平均单周期峰峰值，不是抓持或部署准入门禁。

```bash
python3 setup/114_carry_watch.py --poses setup/acceptance/local_run_20261027/poses4.jsonl.gz --json /tmp/watch.json
```

| 标签 | 观测含义 |
| --- | --- |
| SAWTOOTH | 周期接近指定 pin 周期且摆幅超过阈值；与机制一致，不能单独证明原因 |
| CONSTANT_OFFSET | 本保持段垂直偏移变化小；未验证 x/y、旋转或接触 |
| NO_CARRY | 未观察到满足条件的连续抬升段，不是完整抓取失败诊断 |
| INDETERMINATE | 无足够保持段或轨迹不符合上述形状，不强行判断没有抓住 |

默认周期 0.100±0.030 s、平均单周期摆幅阈值 30 mm、稳定偏移变化阈值 5 mm。
这些是形状判据；箱体半高不能证明振荡原因。阈值未针对其他场景标定。

输入必须有有限且严格递增的真实时间戳和目标位姿。坏 JSON、非有限数值、缺整个
timestamp/目标，以及超过半个目标周期的采样缺口均拒绝；不补造 50 Hz 时钟。
proto3 合法省略的零值按零处理。只分析最长主段，不能声称逐次 trial 全部检查。
短 PICK-only 录制应显式给出 --rest 0.0175，全程中位数可能不是静止高度。

三份历史文件的所选保持段均报告 SAWTOOTH：

| 文件 | 平均周期 | 平均单周期峰峰 |
| --- | --- | --- |
| poses.jsonl.gz | 约 0.1003 s | 约 69.9 mm |
| poses4.jsonl.gz | 约 0.1005 s | 约 70.6 mm |
| demo_poses.jsonl.gz | 约 0.1009 s | 约 67.6 mm |

退出 0 只表示完成分析，输入不可用退出 2。工具不能替代 action result、referee 或
同步 SE(3) 检查。--follow 尚未进行在线资格验证。这个 legacy Gazebo Pose_V 适配器
与新 PhysicsTrace schema 不同，不能混入后者，也不能据此声称 ROS 无法提供观测。
