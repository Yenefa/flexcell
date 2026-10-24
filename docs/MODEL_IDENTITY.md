# 模型标识与推理来源

## 线上模型（当前 fleet）

| 项       | 值                                                                                |
| -------- | --------------------------------------------------------------------------------- |
| 服务     | DeepSeek 官方 API，`https://api.deepseek.com/chat/completions`                    |
| 请求模型 | **`deepseek-flash`**（当前配置及本轮响应中的字符串；权重版本 UNKNOWN）            |
| 角色     | 慢路径 / 任务级推理（ADR-002 接缝）                                               |
| 思考模式 | thinking disabled                                                                 |
| 输出模式 | `json_object`，上限 512 output tokens                                             |
| 生产超时 | 30 s（端点 readiness 探测另用 60 s，不混用）                                      |
| 凭据位置 | `/home/ros/.config/flexcell/deepseek_api_key`，mode 600，不入仓库                 |
| 预算账本 | `/home/ros/.config/flexcell/deepseek_budget_20261001.json`，跨进程持久，上限 5 元 |

### 名称记录说明

2026-10-05 Q8 先导的真实慢路径记录中，`model` 与 `response_model` 均为
`deepseek-flash`。此前本页把它解释为 `deepseek-v4.1-flash` 并声称绑定确定权重，
缺少服务商权重版本或摘要证据，现撤回。实际权重版本与跨时间权重稳定性为 **UNKNOWN**；
固定请求串不能替代服务端权重身份。

### 已验证事实

- 本轮慢路径记录的请求模型与响应模型字符串一致；这不证明权重未漂移。
- 账本固定按输入 2 元/百万 tokens、输出 8 元/百万 tokens 记费用上界。
  这是仓库当前计价常量，不是本轮联网核实的官方现价。
  账本始终用这组较高价格、不扣缓存优惠，因此展示值是**费用上界**。
  历史 2026-10-01 的 95 次结算合计 **0.330258 元 / 5 元**
  （实测 prompt 143221 / completion 5477 tokens），不代表本机当前账本总额。

### 已知边界

- 固定请求串、固定权重、同输入同输出是三个不同结论；后二者当前均未验证。
- 本轮在线先导的 `model replay` 为 **NOT_RUN**。仓库 `119_policy_eval.py`
  已有本地冻结模型的离线工具；它不构成官方服务权重身份或本轮在线重放的证据。
- 早期实验曾使用本地小模型（Qwen2.5-1.5B / Qwen2.5-3B），那批结果与线上官方模型
  **不是同一模型**，不可合并比较。相关记录保留在
  `setup/acceptance/m3_deepseek_20261001/endpoint_attempt.json`。

## 快路径（Jev）

角色：typed 分类快路径，`decision_policy=jev` 或 hybrid 的快臂。后端可插拔
（`jev_backends.py`：`local` = Qwen 生成式 / `clef` = Clef 决策模型）。

**当前部署（桌面机，2026-10-05）**——绑定字段以此为准，变更须同步本表与校准文件：

| 项              | 值                                                                                                              |
| --------------- | --------------------------------------------------------------------------------------------------------------- |
| 后端            | `clef`（`ClefBackend`，typed `/v1/systemone`）                                                                  |
| 端点            | `http://172.17.144.1:11435/v1/systemone`（llama.cpp b11389 Vulkan，Windows 侧 GPU）                             |
| 模型名          | `clef-flash-q8_0`（ggml-org/Clef-Flash-GGUF Q8_0）                                                              |
| 权重 sha256     | `8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`                                              |
| 校准文件        | `~/.config/flexcell/jev_calibration_clef_q8_20261005.json`（运行时计算文件 sha，逐决策核对）                    |
| prompt 摘要算法 | 哈希 `jev_backends.py` 全源文件字节（2026-10-05 起；旧算法为 ast.dump，跨 Python 版本不稳定且不覆盖 Clef 模板） |
| 校准标签        | `FSM_ACTION_AGREEMENT`（**不是物理成功率**；scope 限 S1 录制输入路由）                                          |

2026-10-05 新一轮真实加载：后端字节摘要 `b37e71cd…5f4e85b8`，校准文件摘要
`0af588a8…8ec3fa7`。原始字节与完整摘要见 [Q8 先导记录](Q8_PILOT_20261005.md)。
服务端 `/v1/models` 实测 `n_ctx=16384`。历史 `102` 部署文件的
`server_context_tokens=8192` 是静态默认值，不能当成 Clef 服务实测上下文；
封存记录保持原值，2026-10-24 家用五条功能回归的差异仍按其归档说明解释。

新版 `102` 生成 `manifest_version=2`：`server_context_tokens` 改为
`{"fast": <正整数或 null>, "slow": <正整数或 null>}`，分别记录当前策略使用的
服务端 `/models` 响应 `data[].meta.n_ctx`。每臂最多一次 2 秒超时的只读 GET，
不发送推理请求；FSM 不查询模型，配置密钥文件的服务及 TypeSafe SDK 不读取凭据，
其上下文留空。缺失、歧义、非法值或不可达均保留 `null` 及明确状态，不回填 8192、
训练上限或请求输出 token 上限，也不因此改变策略/回退/动作。

`server_metadata` 保留响应模型 ID 和选择依据；仅一个模型但请求别名不匹配时，
明确标 `sole_advertised_model`，不能据此验证请求模型或权重身份。
原始响应保存为同目录 `fast_models.json` / `slow_models.json`，SHA 与查询时间记录于
`backend_metadata_observations`。运行指纹包含稳定的上下文与选择状态、部署脚本及采集器
源码摘要；查询时间、完整响应 SHA 等易变回执在指纹之外。部署时的观测不能保证服务
之后不被替换，权重与逐决策来源仍须单独核验。

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
