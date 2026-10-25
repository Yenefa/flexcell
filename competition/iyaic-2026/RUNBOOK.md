# 家用快模型连接与比赛交付检查

历史服务：`http://100.87.190.44:11435`，`/health`、`/v1/models`、typed `/v1/systemone`。
历史模型为 `clef-flash-q8_0`，权重与校准身份见 [MODEL_IDENTITY](../../docs/MODEL_IDENTITY.md)。
历史记录不是当前机器在线状态或服务端权重证明。

## 工具链分工与交接（不是队员分工）

本项目为单人独立完成，「分工」指的是人与工具的交接，不涉及第二名学生：
云端负责写代码、运行具备依赖的离线检查、准备给电脑 Agent 的提示词。
用户手动转发给电脑 Agent，后者在指定电脑执行 ROS/Gazebo/GPU 任务并返回完整产物。
公用电脑无需为此登录 GitHub；可通过带 commit、SHA-256 和版本说明的包交接。
新任务先查已有回执，已完成的固定五项回归不重复执行。

## 2026-10-24 已完成的家用 GPU 回归

[原始证据及独立审计](../../setup/acceptance/home_gpu_abort_20261024/README.md)：
ROS/Gazebo 在执行机，Clef Q8 推理通过 Tailscale/SSH 转发至家用 RX 6800，
Vulkan 日志确认 33/33 层卸载。固定批次为 S4:2、S5:2、S1:1，四次预期失败和一次任务成功；
共 20 次真实 Jev 决策，权重和校准身份已核对。它是功能回归，不是 baseline 资格窗口。

服务参数有 8192/16384 context 元数据差异，原始响应正文未完整留存，模型重放仍为 NOT_RUN。
家用服务和执行机 ROS/Gazebo 已在回执中停止；不把历史通过当作当前在线状态。
比赛机器、现场网络、冷启与离线交付仍需单独固定和验收。

## 2026-10-17 云连接历史快照

2026-10-17本云环境的policy snapshot为 `vpn_configured=false`；经继承HTTP代理访问health返回503。
[真实请求回执](evidence/home-fast-connectivity.json)。没有得到服务响应，没有发推理、SSH或机器人请求。
这不证明家用电脑离线，也不是上述后续回归失败的记录。当前手动转发流程不依赖云端直连。

**2026-10-24 根因更正**：那次 503 和 502 的来源已在同一台机器上定位到系统代理，而不是端点不可达。
`ProxyEnable=1`、`ProxyServer=127.0.0.1:7890`，bypass 列表含 `127.*` 与 RFC1918 段，
但**不含 `100.64.0.0/10`**；`urllib.request.getproxies()` 在 Windows 读注册表，因此把
`100.87.190.44:11435` 交给本地代理，代理对该 overlay 私网地址回 502。三组对照只改地址与代理覆盖：
`100.87.190.44` 无 `no_proxy` → 502 / 7 652 ms / FSM 回退；加 `no_proxy=100.87.190.44` → 20/20 PASS；
`127.0.0.1` 无 `no_proxy` → 20/20 PASS。`curl` 不读注册表，所以同一时刻同一 URL 是通的。
证据与对照表见 [`setup/acceptance/clef_recorded_001_20261024/tailscale_endpoint/`](../../../setup/acceptance/clef_recorded_001_20261024/tailscale_endpoint/README.md)。
仍未证明的是跨机可达——三次请求都发自托管服务的机器。

运行规范要求使用环境自带sidecar VPN与代理，不在executor另装Tailscale或改路由绕过配置。
HTTP请求保留继承代理和TLS校验；SSH/raw TCP另外需要匹配grant及应用身份，不把HTTP权限当SSH权限。
不要在聊天或Git中提交Tailscale/API凭据。

## 后续有新任务时的检查顺序

1. 先由执行该任务的电脑 Agent 核对指定 commit、已有服务与回执，再按已定协议做有界健康检查。
2. 需要新的推理验证时使用既有ClefBackend；合成最小typed问题标为推理探针，不计机器人或benchmark样本。
3. 请求/响应模型串、实际权重摘要、prompt摘要、校准文件摘要分别核对；API未提供的权重证明标UNKNOWN。
4. 家用快模型离线时暂停模型相关任务；不能用其他模型或FSM回退冒充快臂。
5. 机器人实验另需执行机ROS/Gazebo、已批准协议和同指纹验收；返回全部失败、原始日志、版本及哈希。

## 现场交付

优先比赛机器本地或现场局域网推理，先验证显存/共享内存、时延和冷启，不假设笔记本能容纳现有Q8。
未达标时使用明确标注的FSM实时演示与真实Hybrid录像/证据回放，不赶工换模型后继承旧校准。

比赛manifest仍未冻结，至少需要：commit/tag、上游提交、world摘要、carry后端、运行指纹、protocol、
模型/权重/prompt/校准摘要、机器网络模式、启动说明、视频/回放摘要、固定演练窗口及判据。
凭据、权重、编译产物和私有留出集留在机器，不进比赛目录。
持久预算保持原账本；不得重置预算或自动解冻n≥50。
