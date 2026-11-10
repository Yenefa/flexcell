# Baseline C 骨架 — 第一次把「自进化」变成代码

## 本轮做了什么

Baseline C 之前**完全空白**（三臂只有 A′ 和 B）。本轮建成：

| 模块 | 路径 | 作用 |
| --- | --- | --- |
| 经验库 | `evolution/experience/store.py` | 追加写、hash 链、防篡改、防删失败证据 |
| 证据种子 | `evolution/experience/seed_evidence.json` | 4 条**真实归档失败**，非编造 |
| 诊断 | `evolution/diagnosis/classify.py` | 10 类归因；无判别证据时返回 `UNKNOWN` |
| 检索 | `experiments/baselines/baseline_c.py` | 按指令特征检索已验证经验 |
| 回归门 | `evolution/validation/regress.py` | 拒绝受保护路径；跑全部 verifier |

## 三条设计决定（都来自之前的失败）

### 1. 经验由机器生成，不让模型写散文
上一个 track 里，**四种写法都没能让 Agent 事后写出可用的经验**（P2 item ② 未达成）。
所以这里不让模型自述：流水线直接记录**独立验收器测到的事实**，模型只能**检索**。

### 2. 追加写 + hash 链
没有 update、没有 delete。删掉任意一条失败记录、或改写 lesson，
`verify_chain` 都会报错。测试覆盖了这两种篡改。
**失败证据不能被抹掉**，否则经验库只剩成功，无法审计。

### 3. 作用域守卫：经验通道不能用来造假
任何提到 evaluator / tolerance / threshold / verifier 的 lesson **写入时就被拒绝**。
回归门再挡一层：改动路径命中受保护目录直接拒绝，**连回归都不跑**。

## 验证结果

```
经验库：4 条真实归档失败，chain intact (4 records)
检索：命中 1 条（同箱落点经验）
回归门拒绝：benchmark/evaluators/evaluate.py -> accepted=false
回归门放行：planner 改动 -> accepted=true, all 45 verifiers still pass
离线测试：75 passed
```

## 途中修掉的缺陷（测试抓到）

`record_sha256` 是对**不含自身**的记录算的，但 `verify_chain` 把哈希字段也放进
body 参与重算 → 每条记录都被误判为篡改。修正后又误删了 `body` 赋值导致 `NameError`，
第二次才修对。**两次都是我自己写的 hash 逻辑，不是环境问题。**

## 诚实的边界：C 现在到哪一级

| 阶段 | 状态 |
| --- | --- |
| Designed | 完成 |
| Implemented | 完成（骨架） |
| Unit Tested | **完成，75 passed** |
| Simulation Tested | **未开始** |
| Independently Verified | **未开始** |
| Generalization Tested | 未开始 |

**C 还没有在 Gazebo 上跑过任何一个任务。** 因此：
- **不宣称** C 比 B 强；
- **不宣称** Level 5（Improve）或 Level 6（Learn）达成；
- **不宣称** 经验迁移有效。

### 明确没实现的

- 把「已接受的提案」真正应用到源码并重建（需人工批准写作用域）；
- C 与 B 的**同任务配对对照**；
- 检索目前是关键词打分，只命中 1/4 条，**召回率明显不足**。

## 下一步

1. 让 C 在**同一批 held-out 任务**上与 B 配对运行，测经验是否真的带来改进；
2. 改进检索（按失败类别 + 场景特征，而非裸关键词）；
3. 在人工批准后再开放「应用提案」这一步。
