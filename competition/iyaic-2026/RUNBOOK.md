# 家用快模型连接与比赛交付检查

历史服务：`http://100.87.190.44:11435`，`/health`、`/v1/models`、typed `/v1/systemone`。
历史模型为 `clef-flash-q8_0`，权重与校准身份见 [MODEL_IDENTITY](../../docs/MODEL_IDENTITY.md)。
历史记录不是当前机器在线状态或服务端权重证明。

## 本次连接状态

2026-10-17本云环境的policy snapshot为 `vpn_configured=false`；经继承HTTP代理访问health返回503。
[真实请求回执](evidence/home-fast-connectivity.json)。没有得到服务响应，没有发推理、SSH或机器人请求。
这不证明家用电脑离线；须在当前任务的环境设置接入同一Tailscale网络，再重复相同授权服务请求。

运行规范要求使用环境自带sidecar VPN与代理，不在executor另装Tailscale或改路由绕过配置。
HTTP请求保留继承代理和TLS校验；SSH/raw TCP另外需要匹配grant及应用身份，不把HTTP权限当SSH权限。
不要在聊天或Git中提交Tailscale/API凭据。

## 接通后的顺序

1. 读当前环境状态/policy，实际有界GET `/health`与`/v1/models`；成功只证明相应HTTP服务。
2. 使用既有ClefBackend发一次合成最小typed问题；标记为推理探针，不是机器人或benchmark样本。
3. 请求/响应模型串、实际权重摘要、prompt摘要、校准文件摘要分别核对；API未提供的权重证明标UNKNOWN。
4. 家用快模型离线时暂停模型相关任务；不能用其他模型或FSM回退冒充快臂。
5. 机器人实验另需本机ROS/Gazebo、已批准协议和同指纹验收；本云环境不具备这些条件。

## 现场交付

优先比赛机器本地或现场局域网推理，先验证显存/共享内存、时延和冷启，不假设笔记本能容纳现有Q8。
未达标时使用明确标注的FSM实时演示与真实Hybrid录像/证据回放，不赶工换模型后继承旧校准。

比赛manifest仍未冻结，至少需要：commit/tag、上游提交、world摘要、carry后端、运行指纹、protocol、
模型/权重/prompt/校准摘要、机器网络模式、启动说明、视频/回放摘要、固定演练窗口及判据。
凭据、权重、编译产物和私有留出集留在机器，不进比赛目录。
持久预算保持原账本；不得重置预算或自动解冻n≥50。
