# WSL 权威 world 路径纠正

2026-10-07，physics profile 的 FLEXCELL_WORLD 从 Windows 克隆改为
`/home/ros/agentic_workcell_ws/worlds/flexcell_velocity_servo`。
两处 world 文件逐字节相同，原 profile 在私有配置目录完整备份；仅一行路径改变，
物理后端、场景内容、模型、校准、DDS 与代理设置未变。profile 原文及备份不进仓。

冷启成功，拥有的 Gazebo 进程实际加载 WSL world；指纹仍为
`5909f3720f821b112313dfbd8cd38231da0204214dd8f97544f93de716962fca`。
随后只读就绪检查通过，369 份已有 episode 文件集合和字节不变，新增原生 episode 为 0。
冷启/只读命令均 rc=0，world sha 不变。

[报告](report.json)和 validation/ 保留路径差异、拥有的进程组、部署、日志及只读检查。
该纠正不扩展样本或证明网络/抓取稳定性；n≥50 与 qualification 保持冻结。
`python3 scripts/verify_frozen.py` 只读检查本回执。
