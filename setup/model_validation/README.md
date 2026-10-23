# 现有 Clef 服务的只读回归

此入口面向 RX 6800 上已部署的 llama.cpp Vulkan / Clef-Flash Q8 服务。它用当前 checkout 的 `ClefBackend` 和 `JevPolicy` 发送固定的 20 个真实记录输入，仅测试模型接口。Python 标准库即可运行，不要求 ROS 或 PyTorch。

完整转发提示词见 [AGENT_TASK.md](AGENT_TASK.md)。默认 Windows 本机命令：

```text
python setup/model_validation/run_clef_replay.py --weights "F:\flexcell-models\Clef-Flash-Q8_0.gguf" --out "setup/model_validation/reports/clef_<UTC时间>.json"
```

把 `<UTC时间>` 换成实际值。`--endpoint` 默认 `http://127.0.0.1:11435/v1/systemone`，`--model` 默认 `clef-flash-q8_0`，单请求超时默认 10 秒，可在 0–30 秒内显式指定。已有输出拒绝覆盖。权重不符或固定输入校验失败时不调用服务；推理失败时停批并保存已完成的结果。

`clef-inputs.json` 固定三个 Q8 先导 episode 的原始 SHA，取 21 个非 bootstrap 输入中的前 20 个，不把这些相关步骤当作 20 个独立任务。原始文件没有结尾换行，校验按原字节，不补换行、不重排 JSON。

每个模型响应必须形成真实 Jev 提案、正的 measured tokens、合法动作与有效概率分布。FSM 回退即使恰好与历史动作一致也不能通过。报告保留每次响应 JSON、输入身份、动作、耗时和部分失败；一致数只作描述。p50/p95 是本轮 20 次客户端调用耗时，不是物理控制周期。

`MODEL_API_PASS` 与 GPU 执行证据分开：脚本可验证本地 GGUF 文件，但 HTTP 模型别名和客户端声明的 SHA 不能证明服务端实际加载了该文件；服务进程的模型路径和当前实例的 Vulkan/offload 日志须由执行 Agent 一起回传。没有这些证据时，相关身份保持未确认。

本工具不改生产校准，不调用付费慢模型，不启动仿真、不派发动作，也不证明 Hybrid 路由资格或闭环成功。原 `119_policy_eval.py replay` 面向旧的 Linux 本地慢模型 ownership profile，不适合直接套用此 Windows Clef 服务，因此增加独立入口。

云端验证采用模拟 loopback HTTP 服务，不接真实模型：

```text
python -m unittest discover -s setup/model_validation -p 'test_clef_replay.py' -v
```

这些检查覆盖完整客户端路径、拒收 OOV/FSM 回退、缺少 tokens、畸形响应、权重漂移和旧报告保护。模拟 HTTP 通过不能计作 GPU 测试结果。
