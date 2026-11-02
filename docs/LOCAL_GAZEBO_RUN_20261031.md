# 本机 Gazebo 运行 · 2026-10-31

**VERIFIED：这轮实际启动了本机 WSL/Gazebo、MoveIt、MTC 和控制器，执行了动作。**
源码固定为 PR #75 的 `c2583aec1e507386f5733285fe5399003709b4d0`。
这是无界面的本机仿真；不是 CI 回放，也不是硬件实机运行。

## 执行与结果

先按仓库已有 `infra/core-window.json` 运行 velocity_servo/MTC 五用例窗口，
随后按 `infra/joint-contact-attached-center.json` 运行一次 Joint/MTC 诊断。
两个窗口分别执行一次，没有补跑或替换任务，没有修改生产求解器。

| 用例 | 实际结果 | 原始物理记录重算的落点误差 |
| --- | --- | --- |
| A 箱单任务 | PICK / PLACE / VERIFY 成功 | 0.0896 mm |
| B 箱单任务 | PICK / PLACE / VERIFY 成功 | 0.0743 mm |
| 双物体任务 | A、B 均成功 | A 0.2164 mm；B 0.1639 mm |
| 一次预设抓取失败 | 一次预算内恢复后成功 | 0.1390 mm |
| 持续预设抓取失败 | 按预期返回 ERR_RECOVERY_EXHAUSTED | 不适用 |

基线窗口结果 `FUNCTIONAL_WINDOW_PASS`、退出码 0，墙钟 **389 秒**。
四个成功用例共完成五次物体放置，五个用例均完成复位及 19 项健康检查，
终态 IDLE / carry=false。这些误差是本轮速度伺服仿真观测，不是硬件精度或成功率估计。

Joint 单任务结果 `ROBOT_FAILURE`，窗口按门禁 `STOPPED`、退出码 1，墙钟 **64 秒**。
PICK 成功，箱体实测上升 **119.767 mm**；PLACE 在 hover 规划阶段报
`GOAL_STATE_INVALID`，`mtc_stages=[]`、`released=false`。
没有派发 PLACE 轨迹，没有主动 PLACE 释放，没有替换/扩充这个失败窗口。
本机重现了 CI 同样的失败阶段；完整唯一因果归因仍是 **UNKNOWN**。

## 原始证据复核

直接用运行器记录的 task_start/task_end 单调时钟区间选取物理观测，
对五次成功放置重算末端物体落点，未用技能的误差自报值代替原始坐标。
最后物理样本距任务结束为 1.37–18.65 ms。基线末态健康均通过。

Joint 运行保留 **25,325 条 2 ms 原始物理步记录，整段 0 断帧**。
任务时间窗内有 **9,554 条连续附着记录、19.106 sim s**。
启动阶段另有两个附着帧，任务结束后另有 316 个附着帧，均原样保留并分段记录。
首次审计程序把启动帧和任务帧拼成一次附着而误报时间间隔；旧程序与纠正说明
保留，纠正后的审计同时要求全原始序列连续和任务区间连续，未删除记录、未降低阈值。
运行前实际加载的原生库和规划器身份已由现有运行器核对。

共保留 229 个原始文件，交付压缩包 242 个文件，含 rosbag、控制器/技能日志、
物理/接触记录、原始失败、源码身份、冻结运行器及审计程序。

完整交付包 SHA-256：
`717a5ee6884abaeb01f4bd2c7065fef3784cfadd035038296a9c44bc6452c929`

本地原始目录：`/home/ros/agentic_workcell_ws/artifacts/local-pr75-20261031`。
执行准备记录：`code-clone/artifacts/local-sim-pr75-20261031/`。
审计及交付收据：`setup/acceptance/local_gazebo_20261031/`。
本轮运行结束后，仿真、技能、录包进程均检查为零残留。

## 环境与边界

四个上游均按 `infra/upstream.lock.repos` 从 Git 提交对象导出 LF 源码，
在 `build/pr75-locked-sources` 隔离构建，未覆盖原上游工作树。
六个依赖包构建完成；运行包来自 `install/pr75-locked-upstream`，
四个第一方包来自 `install/pr75`，导入/安装源码身份核对通过。
前两次准备被跨系统 CRLF 差异检查挡住，均发生于仿真派发前；
此后两个实际仿真窗口各只执行了一次。

本轮没有运行 native 五循环、独立取消/停稳矩阵或相机数据窗口，不能宣称复现全部 CI。
Joint 问题没有修复，PR 没有合并或推送。D3 **NO_GO**、模型 n≥50 冻结等边界不变。
后续仍需实现并数值验证实际 TCP 点求解 adapter，并捕获完整 planning scene/request
后再声明新的 Joint 资格窗口。
