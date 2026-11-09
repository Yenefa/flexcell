# C12 — MTC 是否具备 FSM 缺失的能力？（负结果）

协议：[`docs/C12_PREREGISTRATION.md`](../../../docs/C12_PREREGISTRATION.md)。

| 场景 | FSM | MTC |
| --- | --- | --- |
| A 基线 dual_object | 2/2 PASS（28.0/28.4 s） | 2/2 PASS（33.0/32.6 s） |
| B 目标区重叠（zone_2 移到 zone_1 旁） | **0/2** `ERR_SAFETY_REJECTED` | **0/2** `ERR_SAFETY_REJECTED` |
| C 跨对象绕行（regrasp + 近距 place） | 2/2 PASS（12.8/12.9 s） | 2/2 PASS（14.8/14.7 s） |

## 判读（按预注册）
- **未出现**"FSM 失败 / MTC 成功"的能力差异 → 记为**负结果**；
- 场景 B 由**安全门**在规划前拒绝（两臂相同），因此它检验的是安全约束而非规划能力；
- 场景 C 未构成绕行冲突，两臂都通过；
- 结论：在既有场景族内，**没有证据表明 MTC 具备 FSM 缺失的能力**；
- 不扩大普通样本代替机制检验。
