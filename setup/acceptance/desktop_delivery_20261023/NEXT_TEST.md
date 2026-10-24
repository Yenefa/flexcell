# 桌面 Agent：只补 Jev 错误原因回归

复用 5060 Ti 16GB 那台机器当前已跑通的 ROS Jazzy / Gazebo / Clef 配置。原 176 条不重跑，不改模型、校准、预算或扰动范围。

## 获取修复

公共电脑无需登录 GitHub。使用云端提供的补丁 ZIP，校验其中清单，保留原 `fix/pick-lift-release` 分支；从 `ed0cf0a3203f5a9c040656a57f881dc48668f832` 新建测试分支后，`git am` 包内 `0001-*.patch`。也可在已有只读凭据的环境取 PR 的 `fix/desktop-abort-evidence` 分支，按云端给出的固定 SHA 测试。

应用补丁后的提交 SHA 可能不同于 GitHub 导入分支，须如实记录本机 HEAD、补丁 SHA 和新运行指纹，不把历史结果写成新代码结果。工作区如有额外运行时修改，先保留并回传 diff。

## 执行范围：5 条功能回归

沿用本机已验证的构建、WSL 保活、模型 profile 与 `102_mainline_runtime.sh cold` 启动流程。新源码必须重新构建并冷启动形成新指纹；旧部署不能代测新代码。之后用当前源树的运行器执行：

```bash
python3 setup/94_scenario_runner.py --stage smoke --policy jev --batch S4:2 S5:2 S1:1
```

这只是功能回归，不用于 baseline 资格或统计结论。固定本轮 5 条，失败全保留，不追加选择性补采。

判据：

- S4 两条按预期失败，顶层仍为 50；detail 和原生 episode 的 final_state.detail 都有 `previous_skill=PLACE cause=ERR_IK_UNREACHABLE` 或 `ERR_MOTION_FAILED`，应与对应失败技能的实际 canonical 类型一致。
- S5 两条仍是 `ERR_RECOVERY_EXHAUSTED=51`；保留真实最后技能原因，不改变重试次数和恢复预算。
- S1 一条仍成功，没有新增恢复。bootstrap 之外的模型提案应是实际 `source=jev`、非 FSM 回退，并有原始 usage/tokens，不能只看 policy 参数。

同时补齐归档：按旧 ZIP 原始批次中 `episode` 字段查找并复制对应的 176 份原生 episode，逐个记录 SHA-256 与原路径映射；缺失就标 MISSING，不重新生成或覆盖历史文件。新回归的原生 episode 也单独归档，两个版本不并池。

回传本机完整 HEAD、构建/启动日志、新指纹、这 5 条 batch JSONL 和原生 episodes，以及旧文件回收清单。遇到构建、启动或模型错误直接保留日志，不重装环境或改系统。
