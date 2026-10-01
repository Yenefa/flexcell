# 模型标识与推理来源

## 线上模型（当前 fleet）

| 项       | 值                                                                                |
| -------- | --------------------------------------------------------------------------------- |
| 服务     | DeepSeek 官方 API，`https://api.deepseek.com/chat/completions`                    |
| 模型名   | **`deepseek-v4.1-flash`**（官方具名模型，指向确定权重）                           |
| 角色     | 慢路径 / 任务级推理（ADR-002 接缝）                                               |
| 思考模式 | thinking disabled                                                                 |
| 输出模式 | `json_object`，上限 512 output tokens                                             |
| 生产超时 | 30 s（端点 readiness 探测另用 60 s，不混用）                                      |
| 凭据位置 | `/home/ros/.config/flexcell/deepseek_api_key`，mode 600，不入仓库                 |
| 预算账本 | `/home/ros/.config/flexcell/deepseek_budget_20261001.json`，跨进程持久，上限 5 元 |

### 名称记录说明

仓库既有记录（`docs/DEEPSEEK_20261001.md` 等）写作 `deepseek-flash`。那是**客户端配置与账本中的请求串**，
官方实际模型名为 `deepseek-v4.1-flash`。两者指向同一模型；引用服务端返回的 model ID 时以
`deepseek-v4.1-flash` 为准。

### 已验证事实

- 95 次官方请求的 `requested model` 与响应 `response model` **全部一致**，无模型漂移。
- 该名称是具名版本，不是 `latest` 别名，因此跨时间可复现：后续批次仍在使用同一组权重。
- 计价按官方人民币价格，输入未命中缓存高峰 2 元/百万 tokens、输出 8 元/百万 tokens。
  账本始终用这组较高价格、不扣缓存优惠，因此展示值是**费用上界**。
  95 次结算合计 **0.330258 元 / 5 元**（实测 prompt 143221 / completion 5477 tokens）。

### 已知边界

- 权重固定**不等于**同输入同输出：采样、批处理浮点非确定性、服务端路由都可能造成偏差。
  "跨时间用同一模型"已成立；"同一输入产生同一决策"尚未验证。
- `model replay` 目前 0/5 NOT_RUN，原因是**尚未实现用冻结输入离线重放模型的环节**，
  不是因为模型会漂移。episode 中已存 `canonical_world`（策略输入的精确字节）。
- 早期实验曾使用本地小模型（Qwen2.5-1.5B / Qwen2.5-3B），那批结果与线上官方模型
  **不是同一模型**，不可合并比较。相关记录保留在
  `setup/acceptance/m3_deepseek_20261001/endpoint_attempt.json`。

## 快路径（Jev）

角色：单 token 分类快路径，`decision_policy=jev`。
模型与端点通过 `FLEXCELL_JEV_ENDPOINT` / `FLEXCELL_JEV_MODEL` 配置。
**当前未配置，线上决策来源统计中不含 jev。** Hybrid 阈值逻辑依赖该路径的置信度，
而置信度语义尚未标定。

## 决策来源记账规则

episode 记录 `policy_trace`，区分真实模型提案与 FSM 回退：

- `source=llm` + `fallback=false` → 真实模型决策
- `source=fsm` + `fallback=true` → 回退，**不得计入模型决策数**
- `escalated=true` → 由 Hybrid 从快路径升级到慢路径

已观测计数（不跨运行指纹合并）：`confirmed_release_s1` fsm 5 / llm 35；
`accepted_goal_s3_s4` 的 S3 fsm 1 / llm 9、S4 fsm 1 / llm 3。
