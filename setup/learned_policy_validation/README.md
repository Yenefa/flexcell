# SmolVLA 离线推理交接

当前目标机器是家用 AMD RX 6800。此目录验证固定 SmolVLA 策略在实际 PyTorch GPU 后端上的推理。它读取公开数据中的一帧观测，保留 FP32、batch=1 和原始 10 次采样设置，输出 `[1, 50, 5]` 动作张量。它不启动 ROS、Gazebo 或机器人。

**RX 6800 能运行 Vulkan 大模型，不代表能运行 PyTorch/ROCm 的 SmolVLA。** 本脚本实现 PyTorch CUDA/ROCm 路径；ROCm 也使用 `torch.cuda` / `cuda:0` API，报告用 `torch.version.hip` 区分真实后端。Vulkan 和 DirectML 尚未接入本脚本。RX 6800 在实际操作系统、驱动和 PyTorch 构建上的兼容性须先探测，不能只看显存容量或设备枚举结果。

## 已有环境：直接执行增量测试

用户确认家用 RX 6800 已有跑通的环境。日常按 [GPU_AGENT_TASK.md](GPU_AGENT_TASK.md) 复用现有 GPU 解释器和缓存，只补当前缺失的完整推理报告。已有相同脚本、资产和测试参数的报告可直接回传，不重跑。

```text
python setup/learned_policy_validation/run_policy_smoke.py --device gpu --expected-gpu rx6800 --warmup 3 --repeat 20 --report setup/learned_policy_validation/reports/gpu_<commit>_<UTC时间>.json
```

将报告文件名中的占位符替换为实际值，保留旧报告。缓存位于其他目录时追加 `--assets-dir <目录>`。只在缺少固定资源时使用 `prepare_artifacts.py` 补齐；该脚本会跳过 hash 正确的已有文件。若执行报错，回传日志交由云端修复，不为本轮测试重做系统或服务部署。

## 按需诊断与新环境参考

`--probe-only` 仅用于环境变化或针对性诊断，不是日常任务的前置步骤。它会记录 PyTorch/HIP/CUDA 版本、实际设备与显存，并执行一次 GPU 矩阵运算。没有 PyTorch、GPU 不可用、卡型不符或内核不可执行时，返回 `BLOCKED_ENV` 和退出码 2，不自动改用 CPU；`ENV_READY` 尚不代表完整模型通过。

依赖参考文件为 `requirements-policy-lock.txt`，有意不固定 torch/torchvision；须先有已在该 RX 6800 上验证可执行的匹配 GPU 构建。LeRobot 0.6.1 要求 `torch>=2.7,<2.12`、`torchvision>=0.22,<0.27`，还须满足版本配对。本仓库未验证 RX 6800 驱动/ROCm 的安装方案，不把 NVIDIA CUDA 或 CPU wheel 当作 AMD GPU 依赖。

资源清单固定 20 个公开文件的 revision 和 SHA-256，总下载量约 1.20 GB。包括完整策略和处理器、基础 VLM 的配置/tokenizer、公开样例视频和状态表；不下载额外基础模型权重。下载与运行产生的文件已在本目录忽略规则内。

必须使用 `anuaju/smolvla_openmanipulator` 的 revision `660b5d90e0c62b9eec6a996c8ef0122eaa623550` 下 `checkpoints/008000/pretrained_model` 子目录。该 revision 根目录的处理器统计是 4 维，与 5 维策略配置不一致；本清单使用子目录配套的 5 维处理器，不修改权重或统计。

## 报告口径

报告记录严格权重加载、模型和输入的实际设备、形状、有限值检查、3 次预热与 20 次测量、p50/p95 耗时及 PyTorch 记录的显存峰值。耗时包括预处理、推理、后处理至 CPU 输出，并在 GPU 计时边界同步；不包括加载、视频解码和有限值检查。显存数字是 PyTorch 分配/保留的峰值，不是整张显卡全部进程的用量。

通过条件是实际 RX 6800 后端执行完整模型，输出 `[1,50,5]` 且所有预热/测量结果有限。单条记录观测重复推理不能说明抓取成功率、动作适配正确或闭环控制可用。

云端仅能运行 CPU 检查，例如：

```text
python setup/learned_policy_validation/run_policy_smoke.py --device cpu --warmup 0 --repeat 1 --report setup/learned_policy_validation/reports/cpu_report.json
```

`prepare_artifacts.py` 和推理脚本均支持 `--assets-dir <目录>`，用于复用已校验的缓存；资产仍按本清单重新核验。完整转发任务见 [GPU_AGENT_TASK.md](GPU_AGENT_TASK.md)，协作约定见 [AGENT_WORKFLOW.md](../../docs/AGENT_WORKFLOW.md)。
