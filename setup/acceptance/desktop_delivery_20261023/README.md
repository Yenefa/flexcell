# 桌面机交付证据与 Jev 错误原因修复

本目录保存用户上传的原始交付 ZIP、独立审计及修正版导出 schema。原始 ZIP 字节未改动，SHA-256 为 `9aaee5fa2b24388c2523ebcb434a175bf4d2fbf72213987c0157df62b0eed30a`。ZIP 内的 4 个补丁和 bundle 保存了公共机上未推送的原始提交。

## 代码审查与修复

源分支 `fix/pick-lift-release` 基于 `a9b6a62`：`c15187d` 保留 FSM PLACE 错误码；`110ae98` 在非取消的 LIFT 失败后请求释放 carry；`011bb09` 收紧 S7 采样范围；`ed0cf0a` 只归档交付证据。第四个提交不是第四项运行时修复。

云端恢复并验证了 bundle、原始提交和相关源码对象。通过连接器发布时提交元数据会改变；导入提交保留 `Original-Commit` 标识，树内容与原提交核对，原始身份仍可从 ZIP 内 bundle 恢复。源代码版本和本次归档提交分别记录，不把旧实验改写成新代码测得。

新修复在公共执行层 ABORT 分支追加最近一次失败技能的 canonical 错误码和 legacy 数字。它读取执行器已有的 `previous_skill_result`，保留模型解释和 trace，覆盖纯 Jev / LLM 等策略；不会从模型文本猜测错误，也不把更早、已经恢复的失败归因给后续中止。任务层 `ERR_SKILL_FAILED=50` / `ERR_RECOVERY_EXHAUSTED=51`、动作、恢复预算和历史输入保持原语义。

Pick 修复复用既有释放方法，不重构 carry。该方法发送释放请求，没有确认物体已回到桌面；新代码将结果文字改为 `carry release requested`。已有取消分支仍保留 carry。本轮不把释放请求当作物理停止/落桌确认，也不把磁吸仿真当作接触抓取。

## 可复算的结果

- 27 个 manifest 条目 hash/长度全部一致，12 份原始批次共 176 行，与导出表的结果、策略、阶段、指纹、模型决策数等字段逐条一致。
- 114 条任务成功、60 条预期失败、2 条 S7 异常；“174 条符合预期”不是任务成功率。
- smoke 81 条、baseline 95 条。三个运行时指纹分别 50、71、55 条，统计按指纹、策略、场景和阶段分别保留。
- 修复后 FSM 的 S7 baseline 为 10/10；同一指纹的 S7 smoke 有 6 条，其中 1 条是旧范围 seed=20260931 的失败复现，另 5 条成功。旧范围反例不删除，不能仅凭指纹就把采样范围不同的记录并池。
- Jev 的 S4 10 条缺少 detail 中的技能类型码，不能据其终止失败就宣布类型化错误验收通过。报告的 320 次模型决策是运行器摘要计数，尚不能替代逐决策来源、tokens 和权重身份审计。

## 数据缺口与 schema 修正

原 `dataset/schema.json` 把 `batch_id` 声明为 integer/null，实际 176 行都是字符串。原 schema 校验得到 176 个错误；[schema.corrected.json](schema.corrected.json) 只修正该字段类型，176 行校验无错误。原数据与原 schema 留在 ZIP 内，不覆盖。导出器 `130_export_dataset.py` 未随包提供，不能声称已修改其源码。

30 条 S4 的导出 `run_id` 为空。其余 146 个非空 ID 无重复，原始批次共保留 176 个不同的 episode 路径；这不是 29 条重复实验。原生 episode 文件却未归档，因此本包无法重做 FSM 输入回放或模型 trace/tokens 核验。记录中的 FSM replay PASS 仅按历史声明保存，模型 replay 仍为 NOT_RUN。不能宣布完整 M3 或解除 n≥50 冻结。

两份 README 未纳入原 manifest，其中 dataset README 仍自称 fsm-only，和 55 条 Jev 行不一致。审计指出这些问题，不改写原始文件。

## 复核与后续

安装开发检查依赖 `jsonschema` 后，在仓库根目录运行：

```bash
python3 setup/audit_desktop_delivery.py \
  setup/acceptance/desktop_delivery_20261023/original-delivery.zip \
  --out /tmp/desktop-delivery-audit-new.json \
  --corrected-schema /tmp/desktop-delivery-schema-new.json
```

输出路径须不存在。退出码 2 表示包内容核对完成、证据仍不完整；CI 明确核对这一状态，不把它包装为验收 PASS。细项见 [audit.json](audit.json)。

云端无需 ROS 的 147 项回归已通过；新测试还覆盖 Jev S4 的结果/episode 类型码，以及 S5 维持 51。ROS 集成由该 PR 的 Jazzy CI 执行，实际 Gazebo 补测待电脑 Agent 回传。已准备 [最小补测任务](NEXT_TEST.md)，不重跑原来的 176 条。
