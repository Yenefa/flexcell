# LIBERO 判据分类：B2 结论能推广到哪（2026-11-11）

**这份文件的作用是限制声称范围，不是展示工作。** 它列出 B2 的结论在哪些任务上成立、在哪些上不成立。

## 一、In 与 On 不是同一套判据（Lead 已逐层核实源码）

源码路径：`/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO/libero/libero/envs/`

      predicates/base_predicates.py:57-64
        class In:  return arg2.check_contact(arg1) and arg2.check_contain(arg1)
        class On:  return arg2.check_ontop(arg1)

      object_states/base_object_states.py:36-64
        SiteObjectState.check_contact(...) -> return True   # 注释原文：no dynamics for site objects
        SiteObjectState.check_ontop(...)   -> under(...) and env.check_contact(parent_object, other)
                                              （仅当 parent 存在）

**推论：** `In` 的接触项恒为真，**退化成纯几何 box 测试**；`On` 在 parent 存在时**额外要求真接触**。

## 二、不是所有 region 都有接触项

`problems/libero_tabletop_manipulation.py::_load_sites_in_arena`：

      if "main_table" in object_region_name:
          target_zone = TargetZone(name=..., zone_size=..., zone_centroid_xy=...)   # 不传 parent_name
      else:
          object_sites_dict[name] = SiteObject(parent_name=body.name, ...)

| 实例 | region | 类型 | parent | 接触项 |
| --- | --- | --- | --- | --- |
| libero_goal/1 | `flat_stove_1_cook_region` | SiteObject | `flat_stove_1` | **有** |
| libero_goal/5 | `main_table_stove_front_region` | **TargetZone** | **None** | **没有** |

**所以 goal/1 与 goal/5 不能用同一个假设解释。** /5 恒 False 不可能由接触引起。

## 三、check_contact 不等于「放稳了」

`check_contact` 只判断一对 geom 是否**出现在** `sim.data.contact` 里。
MuJoCo 的接触列表**包含 margin 内的近接触（dist > 0）**，且不看穿透深度。

**因此：**
- `check_contact = True` 只能写成「判据接受了」，**不能**写成「物体压在父物体上」或「放稳了」
- 任何引用 `check_contact` 的结论，**必须同时给出 `min_dist_m` 与 `penetrating`**，否则会被误读

## 四、谓词分布（读 bddl 的 `(:goal)` 统计，非估计）

| 套件 | In（纯几何） | On | 其它 |
| --- | --- | --- | --- |
| libero_object | **10/10** | 0 | 0 |
| libero_spatial | 0 | **10/10** | 0 |
| libero_goal | 1 | 7 | Open 1 / Turnon 1 |

## 五、允许与禁止的声称

| 声称 | 允许？ | 理由 |
| --- | --- | --- |
| B2-1c 在 `libero_object/1` 上端到端成立 | **允许** | 实测，且该实例是 In 类 |
| 该结论推广到全部 10 个 libero_object | **允许，但需说明是同类判据** | In 类无接触项 |
| 「几何修好了所以 goal/spatial 也解决了」 | **禁止** | On 类要求真接触，几何只是必要条件 |
| 「B2-1c 对全套件有效」 | **禁止** | 只在 In 类端到端验证过 |
| 1a/1b 的归因结论 | **不受影响** | 那 5 个配对实例全是 In 类 |

## 六、对后续的约束

- 任何在 On 类任务上声称「判据通过」的结果，必须同时给出接触真值分解（`env_check_contact`、`n_pairs`、
  `min_dist_m`、`penetrating`），且**必须区分真穿透与 margin 近接触**。
- 给 `/5` 取父物体接触数是**无意义**的（不存在该要求）。凭空造出判据里没有的要求，
  和漏掉一个要求是同类错误，方向相反。
- 缺失信息的正确做法是记 `parent_name=None` / `has_contact_term=False`，而不是补一个默认值。
