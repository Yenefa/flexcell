# 版本与分支管理

本文件是当前工作约定。模块目录见 [REPOSITORY_MODULES.md](REPOSITORY_MODULES.md)，
机器可读的版本索引见 [version_baselines.json](../config/version_baselines.json)。
整理任务：[issue #240](https://github.com/Yenefa/flexcell/issues/240)。

## 四种身份分别记录

| 身份 | 当前引用 | 含义 |
|---|---|---|
| 仓库默认分支 | `main` | GitHub 默认入口；不能由此推断某项物理能力已通过验收 |
| Mission 研发线 | `autonomous/flexcell-remediation` | Mission 声明的研发分支；不等于本次已执行版本 |
| T08 执行源码 | `22f873bae82ce61270a63397fbecdd3a119a115e` | CI 43274720654 实际执行的固定源码 |
| T08 证据 checkpoint | `83ffafe117208dc82d2e02320e3cd7204ec8b97c` | 同一候选的报告、原始 ZIP 和离线复核；正式基线未提升 |

当前整理分支 `refactor/module-boundaries-20261113` 从证据 checkpoint 建立，
使用独立工作树。原 `develop/t08-runtime-recovery-20261112` 保留。
两例任务各一次通过，只能记录为限定范围验证；不能命名为正式发布、整体稳定版或未见集通过。

本次核对的 `main` 为 `ebe27f07881200ab0fc74dfaa5490208023bf9d9`，是
`83ffafe1` 的祖先，两者间有 333 个提交。因此本次整理的审查范围是相对 `83ffafe1`
的整理提交；后续向默认分支集成时，应按目标分支核对版本索引并选择相应提交，
不能把整条实验研发历史当成一次目录整理合入。

## 分支与提交范围

- 一个工作分支围绕一个模块和一个问题：`feat/<模块>-<任务>`、`fix/<模块>-<问题>`、
  `refactor/<模块>-<边界>`、`chore/<工具>-<维护>`。
- 同一能力的多次实验在该工作分支上按 commit 和 run ID 记录，避免每轮实验都新建长期分支。
- 控制行为、构建配置、证据归档和文档分别提交，便于独立审查和回退。
- 各模块完成自己的检查后，再准备集成。源码整理通过不代替机器人任务验收。
- 新的实验从明确的完整 SHA 开始；分支名只表示开发位置，不作为已验证版本标识。
- 原始记录、失败和 source/evidence 的对应关系一直保留。历史分支暂不自动删除，历史提交不重写。

## 版本记录最小字段

每个能力 checkpoint 至少记录：执行源码 SHA、证据 SHA、run ID、配置/镜像、任务范围、
独立判定、回归状态和是否正式提升。包里的 `0.1.0` 是软件包版本，不能代替这些信息。

只有 API/软件兼容性需要变化时才按模块维护包版本。GitHub Release、正式基线提升和
主线合并遵循各自现有流程；创建整理分支不会触发这些状态变化。

## 第一阶段与后续拆分

第一阶段处理版本索引、包发现边界、模块职责与生成数据的位置，保持已执行源码和原始证据。
后续可按 Runtime、机器人技能、仿真适配、独立验收分别开小分支拆分实现；
每次保留兼容入口并运行对应检查，涉及机器人行为时需要新的物理验收。


源码提取分支在 `version_baselines.json` 的 `source_refactors` 单独登记。
当前推进结果模块分支 `refactor/runtime-push-results-20261113` 基于 `0c3cf175`，
通过离线等价与 ROS 回归；原物理 checkpoint 的执行源码和证据 SHA 保持原值。

按三职责域解耦的分支 `refactor/skill-layer-boundaries-20261113` 基于 `fc12431f`，
跟踪 [issue #242](https://github.com/Yenefa/flexcell/issues/242)。它接续前两阶段，
独立提取物理模型包并限制开发与执行的依赖方向，范围见
[SKILL_ARCHITECTURE.md](SKILL_ARCHITECTURE.md)。后续集成需包含新能力包、执行包依赖、
兼容入口和构建配置，不能只取路径调整的一部分。独立诊断分支的提交仍需另外审查。
