# P1.4 stage 2 — T-G1 with function-calling agent (BLOCKED)

- `pilot/agent_fc.py`：OpenAI tools 协议（read/write/run/telemetry/verification）。
- 首次 FC 运行（deepseek-flash）：3 轮，**未调用 run_execution、未写 plan.json**；读 `plan.json`/telemetry/verification，甚至去读不存在的 `README.md`。
- 尝试强制 `tool_choice={"type":"function",...}` → **HTTP 400**（DeepSeek 不支持强制函数选择）；该次运行在写入 result 前崩溃，仅保留 events。
- 判定：**BLOCKED（模型工具使用行为）**；基础设施保留，任务不再重试。
