# SMOLVLA-GPU-001：现有 RX 6800 上的增量推理测试

你是家里电脑上的执行 Agent。用户确认已有跑通的 RX 6800 环境，本轮直接复用现有解释器、GPU 后端和模型缓存。云端负责写代码，本机负责执行下面的测试并回传结果。

仓库：`Yenefa/flexcell`，分支：`research/smolvla-gpu-handoff`。固定到用户提供的完整提交 SHA；保留现有工作区修改。先读适用的 `AGENTS.md`（若有）。

## 本轮只需要的测试

PR #39 的云端 CPU 推理、资源校验和 ROS 离线 CI 已通过。本机只补当前固定检查点的完整 GPU 推理，不重复环境盘点、矩阵运算专项测试、安装/部署流程或云端已通过的测试。

先查看本机已有结果：若同一推理脚本、同一资产清单/检查点、FP32、batch=1、10 次采样、3 次预热加 20 次测量已有完整 RX 6800 报告，直接回传该报告及其原提交 SHA，不重跑。若只差部分结果，只补缺项。文档提交变化本身不要求重跑；判断脚本与资产清单内容是否相同。

没有符合条件的结果时：

1. 复用现有模型缓存，脚本会核验固定的 20 个文件。缓存目录不在本目录时传入 `--assets-dir <已有缓存根目录>`。只在缺少清单中的资源时运行 `prepare_artifacts.py` 补齐，已有 hash 正确的文件不会重下。模型为 `anuaju/smolvla_openmanipulator`，revision `660b5d90e0c62b9eec6a996c8ef0122eaa623550`，子目录 `checkpoints/008000/pretrained_model`，使用其配套 5 维处理器。
2. 使用已有 GPU 解释器，直接执行以下完整推理。将报告路径的 `<commit>_<UTC时间>` 替换为实际值，保留旧报告；需要复用其他位置的缓存时追加 `--assets-dir`。

   ```text
   python setup/learned_policy_validation/run_policy_smoke.py --device gpu --expected-gpu rx6800 --warmup 3 --repeat 20 --report setup/learned_policy_validation/reports/gpu_<commit>_<UTC时间>.json
   ```

3. 保存 stdout/stderr 与退出码。检查每次输出均为 `[1,50,5]` 且数值有限；报告应包含实际 GPU 后端、模型/输入设备、20 次测量耗时、p50/p95 和显存峰值。脚本中的设备校验属于本次推理的运行断言，不需要额外执行 `--probe-only`。

不要为使测试通过而重装驱动、重启、替换现有模型服务、改采样步数/精度或切到 CPU。若执行失败，直接回传完整错误及出错命令，交由云端修复。本轮不训练、不运行 Gazebo、不发送机器人动作。

## 回传格式

```text
任务：SMOLVLA-GPU-001
结果：PASS / BLOCKED_ENV / FAIL
证据：本轮新测 / 复用已有报告
代码提交：<完整 SHA>；本地改动：<无 / diff>
实际命令、解释器路径与退出码：
完整报告：<粘贴 JSON 或附文件>
运行日志：<关键输出；失败时完整堆栈>
```

硬件/后端/依赖版本已在 JSON 中记录，无需另做环境清单。若复用旧报告，保留原时间与原提交身份，不改写成新测结果。一次记录观测的推理报告不作为闭环抓取成功率。
