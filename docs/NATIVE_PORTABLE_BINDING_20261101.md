# Native 原始回放的可移植来源绑定修正

本轮更新 [PR #85](https://github.com/Yenefa/flexcell/pull/85)，处理 #87 和自动审查
指出的 LF 检出失败，未修改原始物理记录、原回执或任何控制门限。

## 已确认的原因与此前验证缺口

在 b042f9b 的真实 Git archive LF 快照上，旧命令直接退出 1：
`gate changed; use the recorded source revision: scripts/contact_gate.py`。
原 receipt 的四个来源 SHA 混合了 LF/LF/CRLF/CRLF 工作树字节；实际运行来源
`source-binding.json` 中的四个 SHA 都是 Git 3328693 的 canonical LF。

此前 Linux 回放读取了 Windows 挂载目录，确实在 Linux 解释器中通过，但输入仍是
同一混合行尾工作树，不能推出干净 LF 检出也通过。本轮明确补足该缺口，保留原结果。
版本号旁车的末尾 CR 是另一个已记录的历史瑕疵，继续输出 INVALID_TRAILING_CR。

## 修复边界

对明确列出的四个 Python gate 文件，仅将 CRLF 对转为 LF，再要求 SHA 与已经封存的
运行源码 map 完全一致。同时要求历史 receipt 的原 SHA 等于这份内容的 LF 或整文件
CRLF 形式，防止把旧观察悄悄丢弃。新输出同时列出 canonical、当前观察和原记录 SHA。

不移除 BOM、孤立 CR、空白或代码字节。四文件集合缺项/多项、历史 SHA 损坏、代码
改动仍拒绝。原 source-binding SHA 在新逻辑前校验。元数据字符串不做通用 strip，
500 ms、最早合格候选、物理门禁和准入裁决均保持。

## 验证与完整补证

35 个字节传输/来源反例覆盖全部 16 种逐文件 LF/CRLF 组合、四种文件内混合、
12 个非行尾篡改及三种历史来源记录损坏。测试调用实际 verify，仅截断昂贵的原始
提取边界。旧代码 25 failed / 10 passed；修复后与原 native 测试合计 50 passed。
全套 Python 742 passed，三条既有 fork 警告保留；40 文件静态扫描零问题。

冻结源码 009b5af；Windows 和 Linux 分别解出同一个 Git LF archive，在 `-I -S -B`
独立模式、无 site-packages 下完整重算两份本机窗口及旧 CI 失败。两端均输出
NATIVE_AUDIT_LIFETIME_REPLAY_PASS，且四个来源观测全部为 LF。原历史 STOPPED、
INVALID_TRAILING_CR 与 D3 NO_GO 均保留；本轮未启动仿真或派发机器人任务。

[补证目录](../setup/acceptance/native_portable_20261101/) 保留完整红/绿日志、Git
快照哈希、两端回放、原失败和执行脚本。原 ZIP SHA 仍为
`eed67b533957848cdc64dda090a4911a66344e81d7a7655269da6edc45591446`；
receipt、source-binding 及最初的 receipt-before-source-binding 均与 b042 字节相同。

## 最新矩阵审查与分工

#86 已提供 legacy 本机矩阵，不能重复把它描述为完全缺失，也不能用本机结果关闭其
CI 执行条件。重算已提交 verify rows，四个格子的最大误差为：

| 技能 / 承载 | teleport | detachable_joint |
| --- | --- | --- |
| MTC | 0.170952 mm | 12.252029 mm |
| legacy | 12.206467 mm | 45.006972 mm |

这些最大值只给出描述性差异：改变 carry 时为 12.081 / 32.801 mm，改变 skill 时为
12.036 / 32.755 mm。两组幅度接近，且最大值可能来自不同落点，不能据此确定
“误差主要来自 skill 而非 carry”的因果结论。精确误差机制仍需高难度诊断。

另用同一批已提交回执构造 CI 的 `/artifacts/.../trial-XX/run-*` 搬运布局，独立复现
报告器十份回执全丢失仍 PASS，容差与全部误差字段为 null。这是 #82 的明确低难度
回归条件，留给该任务修复；不修改其报告器。#84/#87 继续只负责加入已有回放命令，
#83 负责按上述边界更新当前台账。D3 仍 NO_GO。
