# P1.4 stage 2 — T-G1 deepseek-chat 记录（不稳定）

- 4 轮内多次调用 `run_execution`，读 telemetry/verdict，并写了 `plan.json`；
- 数值选择不稳定（0.30 / 0.35），最终失败；
- 其中一次 `0.30` 实际 PASS，但被 **HashGuard 空 protected 列表 bug** 误判（已修复并加测试）；
- 判定：LLM 工具使用可用、**参数推理不可靠**；W1 不升级。
