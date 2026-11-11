# 失败案例：ROS 2 接口猜测（6 次）

全部发生在 2026-11-12 同一会话，全部靠启动 Gazebo 才发现，全部可静态拦截。

---

## 案例 1 —— `PushObject.Result.success`

```python
result.success          # 我写的
# AttributeError: 'PushObject_Result' object has no attribute 'success'
```

**修法**：遍历 `PushObject.Result.get_fields_and_field_types()` 通用导出，不逐字段猜。

## 案例 2 —— `direction_cosine` vs `direction_cos`

```python
result.direction_cosine  # 我写的
# AttributeError: ... no attribute 'direction_cosine'
```

真实字段：`direction_cos`。短一个 `ine`。

## 案例 3 —— `sample_gz_pose` 的第一个参数

```python
pose, err = common.sample_gz_pose(node, o['name'])   # 我写的
# TypeError: unsupported operand type(s) for +: 'float' and 'str'
```

真实签名：`sample_gz_pose(model_name, timeout_s=6.0, world='empty', max_age_s=1.0)`。

**第一个参数是模型名，不是 node。** 报错信息完全看不出这一点——它是在函数内部
`time.monotonic() + timeout_s` 那里炸的。

## 案例 4 —— `ObjectPosition.name`

```python
op.name = o['name']      # 我写的
# AttributeError: 'ObjectPosition' object has no attribute 'name'
```

消息定义：

```
string object_name
geometry_msgs/Point position
```

## 案例 5 —— `CompositeStage.place_pose` 是 Point

```python
s.place_pose = Point(x=..., y=..., z=...)   # 我写的
# AttributeError
```

真实定义：`geometry_msgs/PoseStamped place_pose`。

## 案例 6 —— `header.frame_id` 未设

```
# 我构造了 PoseStamped 并设了 pose.position 与 orientation.w
# 漏了 header.frame_id
ValueError: stages require world frame and identity orientation
```

`task_fsm_server.py:609` 的判据是**精确比较**：

```python
if (pose.header.frame_id != 'world' or
        [q.x, q.y, q.z, q.w] != [0., 0., 0., 1.]):
    raise ValueError('stages require world frame and identity orientation')
```

`[q.x, q.y, q.z, q.w] != [0., 0., 0., 1.]` 是列表精确比较，
所以 `orientation.w = 1.0` 必须和 `x=y=z=0` 同时成立，且不能用近似值。

---

## 共同点

| 特征                       | 次数 |
| -------------------------- | ---- |
| 启动 Gazebo 后才发现       | 6/6  |
| 静态可判定                 | 6/6  |
| 报错信息不足以指出真实字段 | 4/6  |
| 靠读源码才修好             | 6/6  |

**结论：这类错误的正确处置不是「下次小心」，而是「先打印真实定义再写代码」。**
