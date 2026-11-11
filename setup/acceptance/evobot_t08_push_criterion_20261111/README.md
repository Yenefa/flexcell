# T08 Push 判据：新增 push 子句并证明它能红（2026-11-11）

## 为什么必须新增判据，而不是复用现有子句

实测事实（`evobot_t08_push_step0_20261111`）：把方块推了 **23.02 mm**，
方向余弦 0.9965，侧向 1.92 mm，Δz 0，`carry.engaged` 全程 False。

而在**加这个子句之前**，验收器对「推了 60 mm」和「方块完全没动」**同样判 FAIL** ——
因为 goal 词表里根本没有位移概念。**不可评分的能力等于不存在。**

## 判据设计：两个半边都必须有

      for name, want in sorted((goal.get("push") or {}).items()):
          moved = hypot(dx, dy)          # 水平位移
          dz    = abs(end[2] - start[2]) # 垂直位移
          cos   = 方向余弦（对指定方向）
          ok = (min_m <= moved <= max_m) and dz <= max_dz and zone_ok
          if cos is not None: ok = ok and cos >= min_cos

| 半边 | 单独存在时的问题 |
| --- | --- |
| 只查位移 | **搬运也能满足**（抓起走 60 mm 再放下） |
| 只查未抬起 | **什么都不做也能满足** |

所以位移与垂直位移**必须同时**检查。这不是保守，是让「推」区别于「搬」。

## 向后兼容（已实测）

加子句后重新评分一个**冻结的** T01 实例：

      instance: T01-train-seed1000
      passed= True clauses= 2 failed= []

**判定与加子句前完全一致**，因为该 spec 不声明 `push`，循环体不执行。
所有已冻结的 T01–T06 结果因此仍然有效。

版本从 `0.2.0` 升到 `0.3.0`——改了验收器就必须升版本，这是冻结纪律。

## 参数默认值与其来源

| 参数 | 默认 | 依据 |
| --- | --- | --- |
| `min_displacement_m` | 0.030 | T08 Step 0 预注册判据（跑之前写死的） |
| `max_displacement_m` | 0.150 | 防止把物体推出桌面还判成功 |
| `max_vertical_m` | 0.020 | 与 `REST_HEIGHT_TOLERANCE_M` 同量级；推不许变成抬 |
| `min_direction_cosine` | 0.9 | 实测达成 0.9965，留余量 |

**这些默认值不来自「让结果好看」，来自跑之前就写下的预注册文件。**
实测 23.02 mm **没有达到** 30 mm 门槛，所以 Step 0 判 NOT_FEASIBLE —— 门槛没有被事后放宽。

## 这个子句还不能证明什么

- 它**没有**让 T08 通过。实测 23.02 mm < 30 mm，用新子句评同样是 FAIL。
- 它只解决「无法评分」的问题，不解决「推不到 30 mm」的问题。后者要靠技能改进。
- 子句本身**未被独立复核**，等级：Implemented + Unit Tested。
