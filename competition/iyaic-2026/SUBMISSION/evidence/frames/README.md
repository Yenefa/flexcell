# 演示帧（真实仿真相机，640×480）

来源：本机 WSL 原生 Gazebo 的一次相机 smoke（run `dbbe6dc49915`）。画面为柔性工作单元相机视角：
机械臂 + 彩色目标箱 + 目标/放置区。

- `frame_first.png` / `frame_mid.png` / `frame_last.png`：抓取—放置过程帧。
- `frame_backfilled.png`：rosbag 对账回填的代表帧（实时丢帧时从 bag 补齐）。

> 这些是真实渲染帧，可直接用于 PPT/答辩；非合成、非示意图。

> 视频版：[../demo_sim.mp4](../demo_sim.mp4)（29.6 s，由本组相机帧以 10 fps 合成）。
