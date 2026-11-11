# ROS 2 接口前置校验

**状态：`PROPOSED`**（测试通过 ≠ 有价值；尚未有回访数据）

---

## 什么时候触发

- 要写一个调用 ROS 2 action / message 的新脚本
- 脚本在「消息字段不存在」或「类型不符」上报错
- 一次仿真启动后才发现接口错误 → **已经是本该拦截的失败**

## 什么时候**不能**用

- 消息定义本身在变（先构建，再校验）
- 需要真实数据才能判断的问题（话题有没有数据、服务是否响应）→ 这是集成测试，不是接口校验

**本 Skill 只回答「这个 goal 构造得对不对」，不回答「机器人做没做到」。**

---

## 为什么需要它

本会话有 **6 次**因为猜字段名/类型而失败，每次都要启动一次 Gazebo（约 5 分钟）才发现：

| #   | 我猜的                          | 真实                         | 报错                                     |
| --- | ------------------------------- | ---------------------------- | ---------------------------------------- |
| 1   | `result.success`                | 无此字段                     | `AttributeError`                         |
| 2   | `direction_cosine`              | `direction_cos`              | `AttributeError`                         |
| 3   | `sample_gz_pose(node, name)`    | `sample_gz_pose(model_name)` | `TypeError: float + str`                 |
| 4   | `ObjectPosition.name`           | `ObjectPosition.object_name` | `AttributeError`                         |
| 5   | `stage.place_pose = Point(...)` | `PoseStamped`                | `AttributeError`                         |
| 6   | 未设 `header.frame_id`          | 必须 `'world'`               | `ValueError: stages require world frame` |

**6 次全是静态可判定的。没有一次需要仿真器。**

---

## 必做步骤

```bash
# 1. 打印真实字段名（不靠记忆）
python3 scripts/preflight.py --describe

# 2. 构造一个完整 goal 并断言
python3 scripts/preflight.py
```

**必须打印出真实字段清单再写代码**，而不是写了再改。

## 验证方法

```bash
python3 -m pytest tests/ -q
```

期望：全绿。**并且负向测试必须在变异下变红**（见 `tests/`）。

## 失败时如何安全退出

```
exit 1 + 打印缺失字段 —— 不要「先跑了再说」
```

把本脚本放在批处理脚本**启动仿真之前**，接口不对就退出，不浪费一次世界构建。

---

## 适用范围

| 覆盖                                | 不覆盖         |
| ----------------------------------- | -------------- |
| `RunComposite` goal 构造            | 执行是否成功   |
| `PushObject` result 字段名          | 推到没有       |
| `CompositeStage` / `ObjectPosition` | 位姿是否可达   |
| `PoseStamped` 的 frame 与朝向约束   | 话题是否有数据 |

---

## 回访指标（本 Skill 目前是 PROPOSED 的原因）

| 指标                         | 怎么查                                                       | 当前值     |
| ---------------------------- | ------------------------------------------------------------ | ---------- |
| 接口类失败是否还发生         | 新运行日志里有没有 `AttributeError` / `requires world frame` | **未回访** |
| Agent 是否真的先跑 preflight | 运行记录里脚本是否被调用                                     | **未回访** |
| 是否引入新失败               | preflight 自身误判                                           | **未回访** |

**三项目前都没有数据，所以状态是 `PROPOSED`，不是 `VERIFIED`。**

---

## 证据来源

`references/failure-cases.md` —— 6 次事件的具体命令、报错与修复。

另有可独立运行的实现：`benchmark/tools/check_ros_interfaces.py`
（已被 Baseline B 批处理作为前置门调用）。
