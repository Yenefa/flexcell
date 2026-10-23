# GPU 证据与当前交接任务

2026-10-23，根据用户转交的家用 Agent 回执和仓库只读核对更新。云端没有读取家用 F 盘、回收站或 shell 历史；这些本机信息来自回执，不冒充云端独立检查。

## 已有证据

- 提交 [`d627f9e`](https://github.com/Yenefa/flexcell/commit/d627f9e9f803e0af2843a58ada80d649268ddede) 的 [school-mode 文档](SCHOOL_MODE_20261005.md) 明确记载家用 RX 6800、`F:\flexcell-models\`、llama.cpp b11389 Vulkan、Q8 GGUF 与 11435 服务。
- [模型身份](MODEL_IDENTITY.md) 和 [Q8 先导](Q8_PILOT_20261005.md) 记录权重、真实 typed 请求、tokens、校准与历史运行身份。
- 用户转交的本机调查发现 `start-gpu-server.bat`、`llama-server.log` 和 WSLg/d3d12 渲染记录。这支持家用机器此前参与 GPU 工作；其中启动参数表示配置意图，具体实例的 GPU 卸载仍应看实际日志。

Vulkan GGUF 推理、WSLg 渲染和 PyTorch 张量计算是不同执行路径。已有前两者的记录，不自动证明 SmolVLA / PyTorch GPU 已运行。目前收到的是历史调查回执，没有收到本次 SmolVLA 的 GPU 推理结果。

## 不能由缺失材料推出的结论

- `49f7723` 是新增交接脚本的代码提交，不是 GPU 结果。它未包含结果只能说明该提交未归档结果；报告目录本就被忽略，不能据此证明本机从未运行过。
- pip cache、shell history 或回收站中未找到记录，不能证明此前从未安装或执行过软件；可能涉及其他环境、用户、清理或记录缺失。
- 当前材料不能证明另一台 RTX 4060 笔记本已经成功运行了相同 PyTorch / SmolVLA 测试。
- 没有核验对应 GPU、操作系统与版本的支持矩阵前，不把 Linux 双系统描述成 RX 6800 的已确认官方 PyTorch 支持路径。

## 当前决定

本轮不变更驱动、系统或服务部署。撤回“PR #39 必须拿到 RX 6800 的 SmolVLA PASS”这一交付限制；用户要求的是可执行的 GPU 测试交接，不应被未经验证的软件后端假设阻塞。

当前家用 Agent 执行 [CLEF-RECORDED-001](../setup/model_validation/AGENT_TASK.md)，复用现有 Vulkan 服务，发送已归档真实输入并保存响应、tokens、时延与当前实例的 GPU 日志。它是任务层快模型接口回归，与低层机器人 VLA 的能力分别记录。

SmolVLA 保留已有 CPU 检查与 [可移植推理脚本](../setup/learned_policy_validation/README.md)。其 GPU 路径在已有兼容 PyTorch 后端的执行机上另行验证；当前家用软件后端阻塞不通过改系统强行解决。Vulkan/DirectML 移植仍需单独实现与验证，不能直接换个设备名当作支持。
