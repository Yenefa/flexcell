# 工作树与独立开发环境

本轮架构分支为 `refactor/modular-workspace-20261115`，从物理能力 checkpoint
`81eed33c5c536e31ea4806fc4d3363f724b96300` 建立。它已包含上一轮模块拆分和物理成果，
不从较旧的架构工作树重新覆盖物理开发。当前路径如下：

| 路径 | 职责 | 分支 |
|---|---|---|
| `/workspace/flexcell` | 原仓库入口、公共 Git 数据 | `work` |
| `/workspace/worktrees/architecture` | 本轮模块与工作区整理 | `refactor/modular-workspace-20261115` |
| `/workspace/worktrees/physical` | 保留已验证的物理开发 checkpoint | `develop/physical-capabilities-20261113` |
| `/workspace/worktrees/architecture-checkpoint` | 上轮架构 checkpoint | `refactor/skill-layer-boundaries-20261113` |
| `/workspace/worktrees/evidence-t08` | 原 T08 Runtime 证据 checkpoint | `develop/t08-runtime-recovery-20261112` |

三个旧 `/workspace/work/flexcell-*` 路径保留为指向新位置的兼容链接。
工作树移动使用 `git worktree move`，原分支、HEAD 与已登记 Git 元数据保持关联。
`/workspace/work/` 中其余目录仍是历史实验运行和重建资料，不作为实时源码或根构建输入。
后续新的本地运行输出放在各工作树忽略的 `artifacts/<run-id>/`。

其他机器将 `worktrees/` 放在自己的仓库父目录下即可；以上绝对路径是本会话的位置，
不是库、Runtime 或 CI 的运行要求。可移植角色声明在
[development_branches.json](../config/development_branches.json)。

## 随时核对实际状态

```bash
python3 scripts/worktree_inventory.py
git worktree list
```

清单分别显示实际工作树、脏状态、本地分支 HEAD 和最近已获取的 origin HEAD。
它只读，不 fetch、不 checkout、不删除、不 reset，也不根据分支存在推断正在运行 Agent。
因此远端字段可能落后于服务器；先明确执行 `git fetch origin` 再观察远端变化。
保留的 checkpoint 可通过 checkout 到其他目录复核，不能自动解释成正式基线。

## 每个工作树独占环境与构建输出

```bash
python3 -m venv .venv
.venv/bin/python -m pip install ./src/flexcell/flexcell_capabilities pytest jsonschema pyyaml
.venv/bin/python -I -c 'import flexcell_capabilities; print(flexcell_capabilities.__file__)'
```

不要复用另一个工作树的 editable installation、`PYTHONPATH`、`build/` 或 `install/`。
本轮实际遇到旧虚拟环境加载早期能力包的情况；新环境独立安装后恢复正确版本。
每次源码修改后重新安装普通 wheel，或只在当前工作树自己的环境中使用 editable 安装。

ROS 工作树分别在自己的根目录构建并 source 自己的 `install/setup.bash`；五个第一方包
仍由 `src/flexcell/` 发现，不把其他工作树嵌入这个目录。全量历史 benchmark 检查中有
会重生成报告的测试，只在临时检出中运行；工作中的物理树不作为测试输出目录。

创建新功能树时，从需要的明确 SHA 出发，而不是无条件追随某个较旧的预留分支。
完成后审查源码、接口依赖和验证，再将相关提交集成到架构分支；`main` 不自动合入。
