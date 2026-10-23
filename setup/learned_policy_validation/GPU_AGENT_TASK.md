# SMOLVLA-GPU-001：家用 RX 6800 环境与推理验证

你是家里电脑上的执行 Agent。云端 Agent 已负责实现代码，你负责本机 GPU 验证并回传可核验结果。当前显卡是 **AMD Radeon RX 6800**；不要沿用 NVIDIA 4060 Ti 的安装命令。用户通过手机转交任务，不要要求他回家操作，也不需要配置云端 Tailscale。

## 代码与任务范围

仓库：`Yenefa/flexcell`，分支：`research/smolvla-gpu-handoff`。以用户随提示词提供的完整提交 SHA 为准，核对 `git rev-parse HEAD`。若未附 SHA，拉取该分支后先记录实际 SHA。使用独立 worktree/副本保留原工作区。先读仓库适用的 `AGENTS.md`（若有）和 `setup/learned_policy_validation/README.md`。

任务是判断现有 RX 6800 环境能否执行固定 SmolVLA 的离线 GPU 推理。先检查操作系统与现有 GPU 软件，再选择可用解释器；不要先假定 Windows、WSL 或 Linux。保留现有驱动、ROS 环境和模型服务，不重装系统、不重启、不安装 NVIDIA CUDA、不强行覆盖依赖。不把 GPU 驱动或系统层的迁移作为本轮测试的前提。

## 执行顺序

1. 收集实际系统、显卡名称和显存、AMD 驱动、现有 Python 环境，以及 ROCm/HIP、Vulkan 和现有模型服务的可用情况。Windows 可读 `Get-CimInstance Win32_VideoController`；Linux 可读 `lspci`，存在时使用 `rocminfo` / `amd-smi` / `vulkaninfo --summary`。不要因命令不存在就判定显卡不存在，不输出完整环境变量或凭据。
2. 优先找电脑上已有的 GPU PyTorch 环境。在选定解释器下执行：

   ```text
   python setup/learned_policy_validation/run_policy_smoke.py --device gpu --expected-gpu rx6800 --probe-only --report setup/learned_policy_validation/reports/gpu_probe.json
   ```

   ROCm 的 PyTorch 也使用 `torch.cuda` 接口，`torch.version.hip` 才用于区分 AMD 后端。本探测包含实际 GPU 矩阵运算。若没有合适解释器/可运行的 AMD PyTorch，或探测为 `BLOCKED_ENV`，保存输出与原因后结束本轮，不下载 1.20 GB 模型，不换成 CPU 宣布通过。存在 Vulkan/llama.cpp 服务只作为环境信息，不能计作 SmolVLA 已支持 Vulkan。
3. 仅在实际 AMD GPU 内核探测成功后，准备独立 Python 环境。复用已验证 GPU torch/torchvision 的版本和来源，不破坏原环境。安装锁定的其余依赖，再执行 `python -m pip check`。LeRobot 所需范围为 `torch>=2.7,<2.12`、`torchvision>=0.22,<0.27`，注意配对；如果现有 GPU 构建不满足，回传依赖阻塞，不擅自换用 CPU wheel。记录所有版本调整。安装后重新运行探测确认没有失去 GPU。
4. 使用以下命令下载并校验固定资源，约 1.20 GB。文件 hash 不符时停止，不手改归一化统计或换检查点：

   ```text
   python -m pip install -r setup/learned_policy_validation/requirements-policy-lock.txt
   python -m pip check
   python setup/learned_policy_validation/prepare_artifacts.py
   ```

5. 下载完成后，按实际 shell 设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`TOKENIZERS_PARALLELISM=false`。运行 FP32、batch=1、保留 10 个采样步骤的基线，3 次预热加 20 次测量：

   ```text
   python setup/learned_policy_validation/run_policy_smoke.py --device gpu --expected-gpu rx6800 --warmup 3 --repeat 20 --report setup/learned_policy_validation/reports/gpu_report.json
   ```

   将 stdout/stderr 保存在 `reports/gpu_run.log`，记录退出码。出现显存不足、缺少 GPU 内核、版本/API 错误时，保留完整堆栈；不要减少采样步数、量化、换模型或静默改用 CPU。

## 通过条件与回传

环境通过与完整推理通过分开报告。完整通过要求实际 RX 6800 上严格加载固定权重，模型/输入/原始输出确实在 GPU，所有预热和 20 次测量的动作形状均为 `[1,50,5]` 且数值有限。报告应含实际 AMD 后端、显存峰值、样本数和 p50/p95。此任务不训练、不启动 Gazebo、不下发机器人动作，不能据此声称闭环抓取成功。

直接回复以下内容，方便用户整体转交云端 Agent：

```text
任务编号：SMOLVLA-GPU-001
代码提交：<完整 SHA>；本地改动：<无 / diff>
结果：GPU_INFERENCE_PASS / BLOCKED_ENV / FAIL
系统、RX 6800 实测名称/显存、驱动：
解释器路径、PyTorch/HIP/CUDA/LeRobot/Transformers 版本：
实际运行命令与退出码：
环境探测：<粘贴完整 gpu_probe.json>
完整推理：<粘贴完整 gpu_report.json；未执行则写原因>
运行日志：<失败时完整堆栈，成功时关键输出>
依赖：<pip freeze，或以附件提供>
Vulkan/现有模型服务：<只报检测到的事实，不含 token>
阻塞原因与建议的最小下一步：
```

可以附 `reports/` 压缩包与依赖清单，不附模型权重、私人文件或账号凭据。若本轮阻塞，明确是当前 PyTorch 后端/版本兼容性问题还是硬件识别问题，把事实交给云端继续适配。
