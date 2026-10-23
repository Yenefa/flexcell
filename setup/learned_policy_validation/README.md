# SmolVLA 离线推理研究工具

当前家用 RX 6800 已有的历史服务是 Clef GGUF / llama.cpp Vulkan。现有回执未提供 SmolVLA / PyTorch GPU 运行报告；本目录暂不作为家用 Agent 的当前任务，也不要求用户安装 ROCm 或更换系统。当前可执行任务见 [Clef 真实输入回归](../model_validation/AGENT_TASK.md)。

## 保留的研究能力

`run_policy_smoke.py` 读取公开数据的一帧观测，严格加载固定 SmolVLA 策略和配套处理器，以 FP32、batch=1、原始 10 次采样输出 `[1,50,5]` 动作张量。云端 CPU 已通过单次与重复推理检查，不代表 GPU 或抓取成功。

GPU 路径采用 PyTorch CUDA/ROCm；ROCm 也使用 `torch.cuda` / `cuda:0` API，报告用 `torch.version.hip` 区分实际后端。Vulkan 和 DirectML 尚未实现。只有已有兼容且可执行的 GPU PyTorch 环境时才使用：

```text
python setup/learned_policy_validation/run_policy_smoke.py --device gpu --warmup 3 --repeat 20 --report setup/learned_policy_validation/reports/smolvla_<commit>_<UTC时间>.json
```

将文件名占位符替换为实际值，保留旧报告。设备型号限制通过可选 `--expected-gpu` 指定，不默认绑定 RX 6800。执行 CPU 检查则使用 `--device cpu --warmup 0 --repeat 1`。无可用 GPU 时明确阻塞，不自动回退 CPU。

`--probe-only` 保留为按需诊断工具，不是当前日常交接要求。依赖参考文件 `requirements-policy-lock.txt` 未固定 torch/torchvision；LeRobot 0.6.1 所需范围是 `torch>=2.7,<2.12`、`torchvision>=0.22,<0.27`，还须满足构建与版本配对。这不是已验证的 RX 6800 安装方案。

## 固定资源与报告

`inference-assets.json` 固定 20 个公开文件的 revision 与 SHA-256，总下载量约 1.20 GB。仅在缺少资源时运行 `prepare_artifacts.py`；已有 hash 正确的文件会被复用。两个脚本均支持 `--assets-dir <目录>`。资源包含完整策略与处理器、基础 VLM 配置/tokenizer、公开样例视频和状态表，不下载额外基础模型权重。

检查点为 `anuaju/smolvla_openmanipulator`，revision `660b5d90e0c62b9eec6a996c8ef0122eaa623550` 下 `checkpoints/008000/pretrained_model`。该 revision 根目录的处理器统计是 4 维，与 5 维策略不一致；清单使用子目录配套的 5 维处理器，不修改权重或统计。

报告记录严格加载、模型和输入的实际设备、形状、有限值、预热与测量、p50/p95 及 PyTorch 分配/保留的显存峰值。计时包括预处理、推理、后处理至 CPU 输出，并在 GPU 边界同步；不包括加载、视频解码和有限值检查。重复单条记录观测不说明闭环性能或抓取成功率。

[后续研究提示词](GPU_AGENT_TASK.md) 与 [协作约定](../../docs/AGENT_WORKFLOW.md) 说明任务状态。下载、缓存和本地报告已被忽略，不会随 Git 提交；因此不能从提交中没有报告推断“从未运行过”。
