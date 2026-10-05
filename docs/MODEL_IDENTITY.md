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

角色：typed 分类快路径，`decision_policy=jev` 或 hybrid 的快臂。后端可插拔
（`jev_backends.py`：`local` = Qwen 生成式 / `clef` = Clef 决策模型）。

**当前部署（桌面机，2026-10-05）**——绑定字段以此为准，变更须同步本表与校准文件：

| 项        | 值                                                                                  |
| --------- | ----------------------------------------------------------------------------------- |
| 后端      | `clef`（`ClefBackend`，typed `/v1/systemone`）                                       |
| 端点      | `http://172.17.144.1:11435/v1/systemone`（llama.cpp b11389 Vulkan，Windows 侧 GPU）  |
| 模型名    | `clef-flash-q8_0`（ggml-org/Clef-Flash-GGUF Q8_0）                                   |
| 权重 sha256 | `8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`                 |
| 校准文件  | `~/.config/flexcell/jev_calibration_clef_q8.json`（含自身 sha，路由门逐字段校验）    |
| prompt 摘要算法 | 哈希 `jev_backends.py` 全源文件字节（2026-10-05 起；旧算法为 ast.dump，跨 Python 版本不稳定且不覆盖 Clef 模板） |
| 校准标签  | `FSM_ACTION_AGREEMENT`（**不是物理成功率**；scope 限 S1 录制输入路由）                |

Ollama Windows 构建对 Clef 全后端 500（ollama#18769），故走上游 llama-server。
Qwen 旧快臂（4/30，LB 0.053）仅存于 `118_local_models.py` 流程；`118 start fast`
检测到 mainline_jev.sh 指向其他快臂时只写 `mainline_qwen.sh`，不再静默覆盖。

## 决策来源记账规则

episode 记录 `policy_trace`，区分真实模型提案与 FSM 回退：

- `source=llm` + `fallback=false` → 真实模型决策
- `source=fsm` + `fallback=true` → 回退，**不得计入模型决策数**
- `escalated=true` → 由 Hybrid 从快路径升级到慢路径

已观测计数（不跨运行指纹合并）：`confirmed_release_s1` fsm 5 / llm 35；
`accepted_goal_s3_s4` 的 S3 fsm 1 / llm 9、S4 fsm 1 / llm 3。
