# MISSION UPDATE — goal round 13 (2026-11-12)

**Branch** autonomous/flexcell-remediation · **Master Goal** docs/EVOBOT_MASTER_GOAL_20261112.md
**North Star** §8–§14 still **BLOCKED_MISSION_TEXT_MISSING** — never invented.

---

## §19.1 本轮：把上一轮审核排在第一位的修复**做了**，而不是继续记录它

第 12 轮审核给了五条排序修复，第一条是：**让播种器机械地验证来源**——约十行。
我查了它动到的文件：`evolution/experience/seed_from_evidence.py` **不在钉定列表里**，
所以这件事**不需要批准**。**那就做，而不是再写一份建议。**

## §19.2 缺陷就是一行代码

播种器的 docstring 写着「证据是从 run 实际记录里复制的，没有一条是回忆」。实现是：

```python
if not source.exists():        # 第 26 行——唯一的检查
    print('SKIP (no archived evidence):', s['source_run'])
    continue

rec['validated'] = True        # 第 31 行——播种器自己写的
```

**它从未打开过那个目录。** 只要**路径存在**，记录就通过；里面有没有那条证据，无人过问。

## §19.3 修了什么

| 函数 | 规则 |
| --- | --- |
| `verify_provenance()` | 证据里的**每一个字符串**都必须出现在 `source_run` 下的**机器可读**文件里 |
| `check_actionability()` | **写入时**拒绝 `HARNESS` / `DOWNSTREAM_CODE` / `UNCLEAR` 的 lesson，复用已有的分类器而不是另写一个更宽松的 |

**按后缀排除散文**（`.md` / `.rst` / `.txt`）：README 是对一次测量的**叙述**，它不是测量。
四条拒绝路径全部 fail-closed——因为原缺陷的本质就是**把沉默读成了成功**。

## §19.4 对四条真实种子跑一遍

```
$ python3 evolution/experience/seed_from_evidence.py --dry-run
REJECT T01-train-seed1000       PROVENANCE: evidence not found in any machine-readable file under source_run: detail
REJECT T05-train-seed1000       PROVENANCE: not found ... : detail
REJECT T05-train-seed1004       PROVENANCE: not found ... : failure
REJECT T03-heldout-seed9000     PROVENANCE: not found ... : detail

accepted: 0   rejected: 4
```

**4/4 被拒，不是审核预期的 3/4。**

审核以为 R3 会幸存（它相信 R3 的证据在真实 run 日志里）。
我在第 12 轮记录过这处分歧：记录写 **domain 213**，而 `runs/s1004-a1/stack.log` 是 **domain 233**。
机械检查核对的是**被引用的确切字符串**，所以 R3 也被拒。
**分歧现在由一个检查裁定，而不是由论证裁定——而且裁定结果不支持更宽容的那种读法。**

这个结果比预期更强，但对项目**不是**更好的消息：
**经验库目前根本无法从自己的种子文件重建。这才是诚实的状态。**

## §19.5 测试 7/7

用例专门挑「朴素检查会通过」的地方：

- 证据**只在 README** 里 → 拒绝（**这就是历史上的那个缺陷**）
- `source_run` 缺失 → 拒绝
- 证据里没有任何可核对的字符串 → 拒绝
- 多字符串中缺一个 → 拒绝

## §19.6 schema 只做保守改动

| 字段 | 之前 | 之后 |
| --- | --- | --- |
| `validated` | 播种器设为 `True` | **播种器不再设置**（留给第二方） |
| `provenance_verified` | 无 | **仅当证据确实在机器可读文件里找到时为 `True`** |
| `evidence_files` | 无 | **证据实际所在的文件** |
| `reviewed_by` / `review_verdict` / `review_ref` | 无 | 存在且为 `None`——**给审核者，不给播种器** |

**我没有改写 `records.jsonl`，也没有重新播种。** 四条旧记录保留 `validated: true`，
因为那现在是「旧播种器跑过」这一**历史事实**；改掉它们等于**销毁这个缺陷的证据**。

## §19.7 回归检查：门第一次真正当门用

改完 `evolution/` 之后，用第 7 轮建好的差分门跑了一次全套：

```
ACCEPTED: structure ok; 109 verifier(s) run; 4 known failure(s) unchanged; 0 new
          [restored 1 archive file(s) the verifier run rewrote]
```

**0 个新失败。** 那道门第一次不是演示，而是真的拦了一次改动。

## §19.8 这修好了什么、没修好什么

| 声明 | 状态 |
| --- | --- |
| 播种器不能再把叙述当成证据 | **已修复，已测试** |
| harness 类 lesson 在写入时就被拒 | **已修复，已测试** |
| `validated` 不再等于「播种器跑过」 | **仅对未来的记录有效** |
| 四条旧记录被修复 | **没有，也不可能**——它们引用的来源里没有那条证据 |
| 经验通道现在**能用** | **不能。** 库里没有可信记录，且无法重新播种 |

**这让 P3 的通道变得诚实，不是变得可用。**
一个拒绝坏记录的空库比一个接受它们的满库是更好的地基，**但它不是经验复用**。
审核五条修复中仍有三条未做：`source_run` 指向 run 而非批次、修缺陷时归档那次失败的 run、审核者持有判决权。

## §19.9 花费与资源

| 项 | 数量 |
| --- | --- |
| LLM 付费调用 | **0** |
| Gazebo 运行 | **0** |
| 孤儿进程 | **0** |
| 钉定文件改动 | **0** |
| `records.jsonl` 改写 | **0** |
| 删除证据 | **0** |
| 回归验证 | **109 个 verifier 全跑，0 新失败** |
