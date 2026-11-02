# Native 审计对象生命周期修复与本机证据

[PR #85](https://github.com/Yenefa/flexcell/pull/85)（`fix/native-audit-lifetime`）堆叠在 #81。修复的是已确认的跨轮审计对象滞留，
历史 CI `native stream stale` 的具体暂停来源仍为 UNKNOWN。

## 问题与修复

worker 每轮解析完整 physics/contact 历史用于独立审计，却把 `p_rows/c_rows`
保留在同一函数作用域，下一轮实时监控仍持有这些大对象图。本机基线的第二轮
settle 阶段测到 gen2 GC 暂停 362.705794 ms，包裹它的 `collect()` 耗时
385.436406 ms，已接近严格的 500 ms 新鲜度门限。

将原来的完整行读取、重 tick 拒绝、contact observation 校验与 `verify_cycle`
原样放入 `audit_cycle()` 作用域，只返回原有的小型汇总。下轮建立 Follower 前，
原始 JSON 图即因引用释放而消失；原始文件与最终 `verify_run` 完整保留。
异常现在还保存单调时刻、原始堆栈及只读 reader tables/文件位置快照。
快照不调用 collect，快照自身出错也不会覆盖原始失败。

没有改变读取/候选选择、GC 全局设置、500 ms、最早合格候选、2 ms 连续步、
20 ms 绑定间隔、10 s 附着、2 mm/1° 跟随、所有权拒绝或 no replacements。

## 测试与实际运行

黑箱 worker 弱引用反例在修复前显示后续各轮仍持有审计对象：
`[0,2,2,2,2]`；修复后为 `[0,0,0,0,0]`，没有强制调用 GC。
首次测试替身漏处理无 session 的 set_pose，原 IndexError 日志单独保留；
修正替身后才得到上述有效红灯。15 项 native 测试全过。

全套 Python 测试 707 passed，两个既有 C++ 测试程序共 4 cases passed；
静态扫描 40 文件、0 问题。Python 有 3 条既有 inference-budget fork 警告，
完整原文保留，未把它们隐藏为无警告运行。

每个版本只跑一次五循环，A/A/B/B/A，无替换：

| 项目 | 基线 19caa01 | 修复 3328693 |
| --- | --- | --- |
| 实际窗口结论 | FIVE_NATIVE_CYCLES_PASS | FIVE_NATIVE_CYCLES_PASS |
| 完整 physics/contact 步数（每流） | 83,339 | 83,354 |
| 2 ms 原始缺步/重步 | 0 | 0 |
| 最长实时 collect | 385.436406 ms | 104.428982 ms |
| 实时 wait 内记录到的最长 GC | 362.705794 ms | 98.861284 ms |
| 完整窗口墙钟 | 204 s | 208 s |
| 事后健康检查 | 19 + reset + 19 | 19 + reset + 19 |

完整 raw gate 重算每轮：附着至少 10 s、绑定 4–8 ms、被动支撑约 0.49 N、
21 点/40 ms 自由落体 -9.8 m/s²、所有权与接触门均通过。两窗口使用同一份
已核验的 Python/launch/native 安装字节，实际映射库逐一匹配；只有脚本审计
生命周期变化。诊断 wrapper 除冻结源码路径外相同，原文件及 SHA 均保留。
本机旧 WSL 工作树在本轮前后补丁 SHA 一致，仿真/记录进程残留为零。

这是一对诊断窗口的测量，没有总耗时改善声明、延迟保证、成功率估计或 CI 根治声明。
诊断 wrapper 自身保留有限历史采样表，测量也包含这一开销。

## 历史 CI 与来源元数据瑕疵

原失败 run 41116653853 / c2583ae 的 ZIP 完整保留。两流各 30,716 个连续步，
最大生产时间间隔 105.222464 ms，跨流最大 skew 3.525946 ms；第 3 轮物理释放
位于 11.953258 ms 的 release RPC 区间内。原错误为 787.690270 ms stale，
没有失败时堆栈/reader tick，因此无法确定原消费者停顿的具体来源。
独立虚拟时钟实验复现了“顺序读取 + 消费者暂停”机制，也确认恰好 500 ms
仍拒绝、旧已合格候选不能跳过。该实验不等于历史故障复现。

修复窗口的 Windows 版本号旁车文件误用了 CRLF，bash 环境值保留末尾 CR。
第一次严格离线回放因此失败。原 identity、旁车文件和 ZIP 都未改写，
输出继续标记 `INVALID_TRAILING_CR`。`source-binding.json` 另行绑定 Git tar 的
PAX 提交号 3328693、100,864,000 字节归档 SHA，以及实际记录的全部 209 个
source-file SHA；209 个均与 Git blobs 和原 tar 字节一致。校验器仅接受这份
明确记载的异常值及精确 CR/CRLF 字节，不做通用 strip。未来冻结旁车文件应
显式使用 `write_bytes((revision+'\n').encode('ascii'))`。

## 可复算交付与边界

[完整验收胶囊](../setup/acceptance/native_audit_20261031/) 包含 114 成员 ZIP：
两个完整本机窗口、原 CI ZIP、全部诊断/身份/health/reset/rosbag/测试及执行脚本。
压缩包 24,031,905 字节，SHA-256：

`eed67b533957848cdc64dda090a4911a66344e81d7a7655269da6edc45591446`

逐成员源字节与 ZIP 解压字节均核验。默认回放只用标准库和仓库纯模块：

```bash
python3 setup/acceptance/native_audit_20261031/verify.py
```

当时 Windows 与 Linux 解释器均对 Windows 工作树字节回放通过，输出
`NATIVE_AUDIT_LIFETIME_REPLAY_PASS`，但未覆盖独立 Git LF 检出。2026-11-01 已确认
此处的可移植来源绑定缺口并修复，详见[更正与两端 Git LF 验证](NATIVE_PORTABLE_BINDING_20261101.md)。
历史 STOPPED、来源元数据瑕疵和 D3 NO_GO 全部保留，原回放 JSON 不改写。

D3 仍 NO_GO，默认承载后端不变，n≥50 冻结。静止臂 native 循环不证明运动臂、
接触抓取或 #59 的真 legacy 技能 × teleport/joint 矩阵。后者仍是高难度待办。
报告器输入合同、D3 当前台账、归档回放接线继续分别交给 junior #82/#83/#84。

PR 首个交付 head 9a923e7 的 [simulation](https://github.com/Yenefa/flexcell/actions/runs/41202950948)
及 [offline](https://github.com/Yenefa/flexcell/actions/runs/41202950949) 检查未开始执行。
相关 job 为 0 steps，两个 check 的原始 annotation 都明确指出账户付款失败或
消费上限限制。具体是哪一个账户条件无法确定；这不是代码测试失败，也不是 CI PASS。
