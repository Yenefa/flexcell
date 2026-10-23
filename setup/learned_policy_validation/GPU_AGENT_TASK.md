# SmolVLA GPU 研究任务：当前家用机暂不执行

当前家用执行机已验证的历史路径是 RX 6800 / llama.cpp Vulkan / Clef GGUF。收到的调查回执没有提供 SmolVLA / PyTorch GPU 推理结果。因此撤回此前默认让家用机直接执行本任务的交接。

**家用 Agent 当前执行 [CLEF-RECORDED-001](../model_validation/AGENT_TASK.md)**，复用既有服务。无需为此安装 ROCm、重装驱动或改双系统。

本目录的 SmolVLA 脚本保留为独立研究工具。只有另行明确已有兼容 GPU PyTorch 的执行环境后，才下发该任务；不把 RX 6800 的 PASS 作为 PR 的必需结果，也不把其他 GPU 的报告标成 RX 6800。

后续执行时固定仓库提交，使用原检查点及 SHA 清单，复用缓存。在已有可执行 PyTorch GPU 后端的解释器下运行：

```text
python setup/learned_policy_validation/run_policy_smoke.py --device gpu --warmup 3 --repeat 20 --report setup/learned_policy_validation/reports/smolvla_<commit>_<UTC时间>.json
```

按实际值替换文件名占位符，缓存位于其他目录时追加 `--assets-dir`。如需固定特定卡型，再显式使用 `--expected-gpu`，不默认指定 rx6800。

输出要求 `[1,50,5]` 且全部有限，报告完整模型的设备、20 次测量时延及显存；保留原 FP32、batch=1、10 个采样步骤。回传实际提交、命令、JSON 和错误日志。已有相同脚本/资产/参数的报告直接复用，保留其原时间和硬件身份。

该脚本没有 Vulkan 或 DirectML 实现；当前 CPU 检查不作为 GPU 或闭环成功。缺少结果文件也不能证明本机从未执行过。详见 [README.md](README.md) 与 [证据说明](../../docs/GPU_EVIDENCE_AND_NEXT_TEST.md)。
