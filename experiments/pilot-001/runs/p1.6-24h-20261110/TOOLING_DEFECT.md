# 工具层缺陷记录（2026-11-10，本轮最重要发现）

## 现象
Level B（源码级修复）在 Flash 3 次、v4-pro 1 次全部失败：Agent 只读不写，
并在 6 轮内反复 `list_dir`/`read_file`/`run_checks`。

## 根因（已修复）
1. **工具描述缺失**：`agent_fc._schemas()` 生成 function schema 时写死 `"description": name`，
   模型收到的工具说明就是工具名本身（如 `read_file`），从未获得"这是什么/怎么用"。
2. **读取截断**：工具结果统一截断到 4000 字符，而 `task_fsm_server.py` 有 1217 行、缺陷在 53KB 处，
   模型即使读到该文件也看不到缺陷行。
3. 缺少**定位工具**：没有按内容搜索的能力，只能靠 `list_dir` 逐层猜路径。

## 修复
- `DESCRIPTIONS` 字典 + `_schemas()` 使用真实描述；
- `read_file(start, count)` 分页 + 工具结果上限提升到 20000 字符（read_file/search_code）；
- 新增 `search_code(pattern, path)` 工具（返回 path:line，限定工作区内）；
- 修复后 `search_code` 可一次定位 3 处 `zone_of[decision.target]` 候选，分页读取可显示 1015 行缺陷。

## 影响与后续
- 这解释了此前 W5 系列"行动缺口"（8/8 失败零写操作）的一部分：工具可用性不足，
  不只是模型"不想写"；
- 需在额度恢复后重跑 Level B，以区分"模型能力"与"工具可用性"；
- 该修复不触碰验收器/阈值/世界。
