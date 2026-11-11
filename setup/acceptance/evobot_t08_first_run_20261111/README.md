# T08 Push：首次仿真运行的执行脚本（尚未运行）

**状态：脚本已就绪并通过语法检查，仿真通道被 A-v2 批次占用，尚未执行。**

## 为什么用 overlay 而不改在用工作区

push 代码在 `wt-comp/src`，而运行中的栈是从 `/home/ros/flexcell-p14` 构建的。
直接改在用工作区会**在测量中途改变 Baseline A/B 的栈**——这正是本项目反复要撤销的那类
悄悄的环境改动。

做法：把**当前**源码复制到 `/tmp`，只把 push 相关的文件覆盖上去，只构建受影响的两个包。
**在用的 install 一个字节都不写。**

## 判据

- 成功与否由 `evaluate.py` v0.3.0 对**测得位移**判定，不是技能自报
- 技能可以自称 SUCCEEDED 而物体没动 —— 那是失败，验收器会说
- 第一次运行最多 `Simulation Tested`（n=1）。**只过 1 个实例必须标 SINGLE-INSTANCE SUCCESS**

## 运行前提

1. A-v2 批次与 Baseline B 执行都已结束（同一时刻只允许一个高负载仿真）
2. `contact_height_m` 必须显式声明（默认 NaN 会被服务器拒绝——这是刻意的）

## 用法

```bash
bash evobot_t08_push_first_run.sh [输出目录] [任务spec] [contact_z]
# contact_z 用 0.030：Step 0 实测中唯一真正产生接触的高度
```

## 当前阻塞

仿真通道。A-v2 批次 55/72 进行中，跑完自动接 Baseline B 执行。
