# 固定推动重复与普通任务回归

执行源码：`66b53f51c73ea3d02ab4147ceabf2580a0ee9fb3`。物理能力分支从共同源码 checkpoint `3e81f956` 出发，机器人执行源码保持一致。本轮完成固定重复实验和普通任务 smoke，不是新的自主技能开发实验。

[实际 Gazebo 运行](https://github.com/Yenefa/flexcell/actions/runs/43421358107)；原作业结论为 failure，原因是汇总器结果路径错误。原始 ZIP、原始 results.json 和红色 CI 状态全部保留。修复提交 `364f7543` 只改结果发现与离线检查；没有为了获得绿色状态重跑物理任务。

| 固定项 | 实际结果 | 返回后净推动 |
|---|---|---|
| RED_1 | Runtime 成功；独立9/9 | 60.924 mm |
| RED_2 | Runtime 成功；独立9/9 | 60.945 mm |
| RED_3 | Runtime 成功；独立9/9 | 60.935 mm |
| BLUE_1 | Runtime 成功；独立9/9 | 60.924 mm |
| BLUE_2 | Runtime 成功；独立9/9 | 60.926 mm |
| REG_NORMAL | 原运行器 PASS | — |
| REG_DUAL | 原运行器 PASS | — |

红目标3次、蓝目标2次，每次独立启动，全部完成两次30mm推进，使用24/40个执行目标；Runtime耗时131.85–134.23s，预算600s。10次真实返回状态全部被消费，记录年龄17.0–107.2ms。没有替换失败或调用模型。

普通 normal 与 dual_object 使用现有完整默认图、FSM 与 velocity_servo 后端；任务分别14.6s、29.857s。物体末端误差分别9.83mm，以及3.61/10.55mm。两项属于 FUNCTIONAL_SMOKE_ONLY，不替代所有场景、取消、恢复、预算和故障回归。旧夹爪释放波动本批未复现，不宣称其根因已修。

## 原始记录与汇总修复

`sim_smoke.py` 在 --out 下创建唯一 run-* 子目录。原汇总器读取 REG_NORMAL/result.json、REG_DUAL/result.json 得到空值，将两个实际 PASS 写成 task_completed=false 并令CI退出2。真实任务日志、原运行器结果与原始数据均在ZIP中。`corrected_results.json` 单独记录离线更正，未覆盖原结果。修复后的读取要求唯一子目录并匹配声明任务，缺失、重复或错误任务不能被挑选为通过。

## 离线独立复核

[archive.json](archive.json) 记录原始37,633,702字节ZIP的SHA256。675个manifest文件、完整覆盖、9个冻结文件和push核心、全部生产源码哈希匹配。由物理/接触/关节原始流重建5个bundle，重新运行未改的独立验收器，复现5次9/9。10次返回状态消费契约亦通过。结果见 [offline_verification.json](offline_verification.json)。

```bash
python3 setup/acceptance/physical_repetition_20261113/verify_archive.py \
  setup/acceptance/physical_repetition_20261113/physical-capabilities-43421358107.zip \
  /tmp/physical-window-replay-UNIQUE
```

使用该证据checkpoint的源码和新输出目录，不启动仿真。5项汇总器回归通过；篡改ZIP的反例在提取前以非零退出码拒绝。独立离线CI只复核原记录，不产生新机器人运行。

## 适用范围与下一关口

本窗口是在两个已暴露开发任务上的小样本重复验证：35mm方块、已登记接触几何与固定负x方向。不能合并旧图像/旧源码运行估计成功率，不能宣称任意物体、方向或未见任务泛化。正式基线不提升，默认仍为legacy。下一物理关口是冻结实现后声明新的初始位置与接触条件，在新的隔离任务上验证适用范围；扩展时继续保留普通任务回归。
