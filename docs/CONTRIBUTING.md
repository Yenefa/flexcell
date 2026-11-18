# Contributing — 第一篇独立 PR

这份指南只讲**怎么把一个改动做成可审阅的 PR**。新机器 bring-up 看
[ONBOARDING.md](ONBOARDING.md)；架构和冻结规则看 [DEVELOPMENT.md](DEVELOPMENT.md) 与
[REPOSITORY_MODULES.md](REPOSITORY_MODULES.md)。

## 0. 先建 Issue，再写代码

仓库的流程是 **Issue → 实现 → 验证 → 文档 → PR**。没有 Issue 的 PR 很容易被要求补范围。

建议的 Issue 模板：

```markdown
## Context
为什么现在需要这个改动？指向具体文件/行为/失败模式。

## Scope
- 改什么
- 不改什么

## Verification
可复现的命令和预期结果。

## Boundaries
是否触碰冻结区、证据或物理行为。
```

标签：`task` + `tooling` / `documentation` / `hardening`；适合新人的再加
`good first issue`。如果任务靠近某个 umbrella issue（例如 #240、#8），先在该 issue
下确认范围，避免重复。

## 1. 选一个小的、独立的任务

好的第一 PR：

- 1–3 个文件，diff 通常小于 250 行；
- 只解决一个问题；
- 有明确的本地验证命令；
- 不改变机器人控制行为、验收阈值或冻结证据。

优先方向：测试、CLI 参数/错误处理、配置校验、只读审计工具、文档。
不要一开始就改 `src/flexcell/flexcell_capabilities`、carry/push 控制路径或
`setup/acceptance/` 里的历史证据；这些需要维护者明确同意。

## 2. 分支和提交

```bash
git checkout main
git pull origin main
git checkout -b test/push-error-mapping
```

当前 team-handoff 阶段的任务可能需要对 `chore/team-handoff-20261116`；以维护者在
Issue 里的指定为准。

提交信息用 `<type>(<scope>): <summary>`，例如：

```text
test(contracts): cover PUSH error mapping
fix(tooling): validate worktree inventory config
docs(contributing): add first-PR guide
```

一个 PR 一个主题；不要混入无关格式化、重命名或大规模重构。

## 3. 本地验证

按改动类型选命令：

```bash
# 仓库工具和脚本测试
python3 -m unittest discover -s scripts/tests -v
python3 scripts/check_repository_layout.py
python3 scripts/check_skill_boundaries.py

# flexcell_skills 的离线契约测试（从仓库根目录）
PYTHONPATH=src/flexcell/flexcell_skills python3 -m unittest discover \
  -s src/flexcell/flexcell_skills/test -p 'test_contracts.py' -v

# physical capability 的离线窗口测试
python3 -m unittest discover \
  -s experiments/physical_capabilities/pick_place_reliability/tests -v
```

如果改动涉及 ROS/Gazebo，再加一条真实窗口验证；离线测试不能替代现场验收。
没有 ROS 环境时，在 PR 里明确写“未跑 ROS/Gazebo”，不要暗示已经跑过。

## 4. 已知的基线红项

以下失败是仓库当前基线，不是你的 PR 引入的：

- `offline-tests`：`experiments/pilot-001` 的 8 个用例（`flexcell_skills` 导入/断言）；
- `sim-smoke`：静态扫描的 3 个既有属性
  （`camera_snapshot.py`、`push_server.py`、`task_fsm_server.py`）。

不要通过放宽测试、删除断言或改阈值来“修绿”。如果 PR 需要全绿才能合并，先和
维护者确认是否接受这些基线红项，或另开 Issue 处理。

## 5. PR 模板

```markdown
Refs #<issue>

## Summary
一句话说明问题和改动。

## Changes
- 文件/行为级别的改动列表

## Testing
运行的命令 + 结果（例如 `9 tests, OK`）；未跑的验证要写明。

## Scope
- 只改了什么
- 明确没有改什么

## Boundaries
- [ ] 没有修改冻结控制/阈值/历史证据
- [ ] 没有把离线结果说成物理能力
- [ ] 没有混入无关格式化
```

## 6. 提交前检查

- [ ] 有对应 Issue，并写了 `Refs #...`
- [ ] 只改目标文件，diff 可逐行审阅
- [ ] 新测试/新校验在本地通过
- [ ] 没有改冻结证据或验收标准
- [ ] PR 描述里写清“未跑什么”
- [ ] 没有为了 PR 数量把同一改动拆成多个重复 PR

维护者需要的是可复现的证据和清楚的边界，不是 PR 数量。
