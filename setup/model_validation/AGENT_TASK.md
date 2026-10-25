# CLEF-RECORDED-001：现有 Vulkan 服务的真实输入回归

状态（2026-10-25）：[现有回执](../acceptance/clef_recorded_001_20261024/README.md)已完成
20/20 接口测试，云端已加固离线校验并复核原字节。以下保留原执行说明，不要求再次执行；
同一协议、输入和服务已有回执时直接使用。当前剩余的 GPU/权重身份边界见回执说明。

当前执行机是家里的 RX 6800，已有 llama.cpp Vulkan / Clef GGUF 服务。直接复用它。本轮执行下面的测试并回传结果，不安装 PyTorch、ROCm 或新驱动，不改系统，也不寻找此前不存在于交接包中的 SmolVLA 报告。

仓库：`Yenefa/flexcell`；分支：`research/smolvla-gpu-handoff`。固定到用户随提示词提供的完整提交 SHA，保留原工作区修改。读取适用的 `AGENTS.md`（若有）。相同代码、输入、模型和参数已有完整报告时直接回传；新增测试入口没有旧报告则直接执行。

## 执行

1. 使用现有 Python，优先在 Windows 本机执行，以直接访问现有 `127.0.0.1:11435` 服务。脚本仅使用 Python 标准库和本 checkout 的纯策略模块，不需要 ROS 或 PyTorch。
2. 服务已运行就直接使用。若未运行，且端口未被其他服务占用，可用已有 `F:\flexcell-models\start-gpu-server.bat` 启动；不要为测试重启正在运行的服务。确认实际服务进程加载的模型路径是本次传入的 Q8 GGUF。只回传 PID、程序路径、模型路径等必要字段，凭据不要带入报告。
3. 将命令中的 `<UTC时间>` 替换为实际时间，用新输出文件保留旧结果：

   ```text
   python setup/model_validation/run_clef_replay.py --weights "F:\flexcell-models\Clef-Flash-Q8_0.gguf" --out "setup/model_validation/reports/clef_<UTC时间>.json"
   ```

   默认端点是 `http://127.0.0.1:11435/v1/systemone`，模型名为 `clef-flash-q8_0`。若在 WSL 中使用既有 Python，权重路径改成 `/mnt/f/flexcell-models/Clef-Flash-Q8_0.gguf`，并通过 `--endpoint` 指定现有 profile 中可达的 Windows 宿主地址；不要把 NAT 模式 WSL 的 loopback 当作 Windows loopback。保持服务和模型版本不变。
4. 脚本会核对本地 Q8 权重 SHA，以及三个已归档真实 episode 的原始文件 SHA；按清单顺序取前 20 个非 bootstrap 输入，调用项目现有 `ClefBackend` 和 `JevPolicy`，逐次保存结果。遇到失败即停止，保留部分报告，不补采覆盖。保存 stdout/stderr 与退出码。
5. 从当前 `F:\flexcell-models\llama-server.log` 提取 Vulkan 设备名称、实际 offloaded layers / GPU buffer 的相关行，并核对其属于当前服务实例。`-ngl 99` 本身只是卸载请求，不能代替实际设备/卸载日志。日志缺失时明确 GPU 执行证据未确认，不改写成通过。

## 判据与回传

模型接口通过要求 20 次输入都有真实 `source=jev`、`fallback=false`、正的实测 tokens、合法动作与有限且归一化的概率分布，canonical state 字节不变。本地权重必须是文档中的 Q8 SHA：`8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`。

JSON 的 `MODEL_API_PASS` 只表示接口测试通过；GPU 执行和服务端实际权重身份还需要上述进程与日志证据。历史动作一致数仅作描述，不作为通过条件，也不是抓取成功率。保留原生产校准文件，不生成或部署新校准；此任务不解除 Hybrid 路由资格冻结、不调用付费慢模型、不运行 Gazebo 或机器人。

直接回传：

```text
任务：CLEF-RECORDED-001
代码提交：<完整 SHA>；本地修改：<无 / diff>
实际命令、解释器与退出码：
完整 JSON 报告：<附件或粘贴>
服务进程 PID、程序路径、实际模型路径：
当前实例的 Vulkan 设备与实际卸载日志：<原文；缺失则写 UNKNOWN>
stdout/stderr：<失败时完整堆栈>
```

如果执行阻塞，直接交回出错命令和证据。本轮不追加历史调查或系统迁移。

