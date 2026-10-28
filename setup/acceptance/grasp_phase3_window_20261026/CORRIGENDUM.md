# Phase-3 解释勘误与 v2 整合

原始修正来自 PR #68；2026-10-28 与已合入 #65 的校验器整合。
原始日志及 v1 逐字不变；v2 采用 #65 实现，不引入同名的第二套 authority。

事实仍为：十次 PICK、九次成功、一次 error 23；639 次查询、零报告 missing；
639 次 pin、638 次确认。唯一拒绝发生在成功 A1。失败 B5-2 为 45/45 确认、
零 missing，rise +0.023416 m。ACK 不能证明 TF 新鲜或物理持续绑定。

撤回两条解释：

1. 短升程减最大观测 lag 得到的 +17.4 mm 是样本算术，不是物理下界。
   端点不是同步测量；历史记录没有臂升程，不能迁移该算术。
2. 54 条负 rise 失败与本窗失败属于不同机制的断言没有依据。92 条历史自然
   error-23 失败支持区间约 [−0.0102781,+0.0298355] m，54 条负值；本窗失败
   位于其中，另有 7 条历史失败不低于它。区间重叠同样不能证明机制相同。

对抗自测的准确表述：仅保留负值会改变 v1 已断言的 54/92 负值计数，v1 也会拒绝。
能够使旧 v1 通过而 v2 拒绝的变异，是保留旧统计量、同时隐藏重叠正值上尾。
不得把两种变异混写。

```bash
python3 setup/acceptance/grasp_phase3_window_20261026/verify_phase3_window.py
python3 setup/acceptance/grasp_phase3_window_20261026/verify_phase3_window_v2.py
python3 setup/acceptance/grasp_phase3_window_20261026/selftest_verify_phase3_window_v2.py
```

v1 退出 0 只表示旧断言被满足，不是旧因果解释获证实。v2 正控制加九项变异共十项。
后续轨迹须独立记录配置和时间口径，不能倒填此十次窗口缺失的同步信息。
故障机制继续为 UNKNOWN。
