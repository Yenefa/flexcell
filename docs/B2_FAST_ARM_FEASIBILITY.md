# B2 fast 臂可行性（2026-11-09）

> B2 的降级试点已证明：缺 fast 端点时 Hybrid 会安全回退 FSM（`DEGRADED_HYBRID`），
> 但这**不能**回答分层路由的价值问题。本文逐条列出"要跑真正的 B2，还缺什么"。

## 1. 前置条件清单

| # | 条件 | 现状 |
| --- | --- | --- |
| A | OpenAI 兼容端点，返回 `{"choice", "confidence"}` JSON | ✅ 支持（`/chat/completions` + `response_format=json_object`） |
| B | 远端端点鉴权 | ✅ 本次新增：`FLEXCELL_JEV_API_KEY` → `Authorization: Bearer`，未设置则不加头（本地服务不受影响）；key 不落盘、不记录 |
| C | 远端超时 | ⚠️ 默认 `FLEXCELL_JEV_TIMEOUT_S=2s`，远端需显式调大（例如 30s） |
| D | **校准产物**（`FLEXCELL_JEV_CALIBRATION`） | ❌ **缺**。`JevPolicy.route_eligible()` 要求校准 bins 存在且 `n>=5`、`wilson_lower>=threshold`；否则 `HybridRouter` 直接 bypass fast |
| E | 身份一致（`FLEXCELL_JEV_MODEL` + `FLEXCELL_JEV_MODEL_SHA256`） | ❌ 缺，需与 D 同时生成 |

## 2. 结论
- A/B/C 已具备；**D/E 是唯一硬阻塞**；
- 校准**不能用编造数据**：必须来自真实标注（每条 decision 的 reported confidence 与真实 outcome）；
- 因此 B2 保持 **INFRA_BLOCKED**，直到完成一次真实校准采集。

## 3. 建议路径（下一阶段）
1. 选 fast 端点：优先本地小模型（无网络依赖、无费用）；若不可用，用当前云端 API 的廉价模型充当 fast（需接受费用与延迟）；
2. 采集 N=60 条真实 decision（同一任务族、同一模型），每条记录 `reported_confidence` 与最终 outcome；
3. 用 `flexcell_skills.confidence_calibration` 生成校准产物，并写 `FLEXCELL_JEV_MODEL` / `MODEL_SHA256`；
4. 冻结 B2b 协议（同 B2，但补 fast 命中率、paid 调用数、决策延迟），跑 3+3 次；
5. 若 fast 端点仍不可得：保持 INFRA_BLOCKED，不得用降级试点替代分层结论。

## 4. 成本估算（若用云端廉价模型）
- 每条 decision prompt 约 1.1–1.4k tokens；60 条约 70–85k tokens；
- 校准本身只用于建立置信度映射，不产生机器人运行；
- 校准完成后，B2b 每次运行约 4–6 条 decision。

## 5. 本次代码改动
- `jev_backends.LocalReproductionBackend._auth_headers()`：可选 Bearer 头（`FLEXCELL_JEV_API_KEY`）；
- `ClefBackend` 复用同一 header 生成；
- 新增回归测试：设置 key 时有 header、未设置时无 header；
- 本地服务行为不变（未设置 key 时与之前完全一致）。
