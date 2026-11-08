# PILOT-001 · P1.0 测量基础设施

> **P1.0 只验证测量链路**：不产生"机器人验证有效"的研究证据。

```bash
python3 run_pilot.py --out /tmp/pilot001     # 五个夹具自检
python3 -m pytest tests -q                   # 单元/夹具测试
```

组件：`manifest`（冻结+摘要）/ `hash_guard`（受保护文件）/ `recorder`（事件 JSONL）/
`toolbox`（按臂工具权限）/ `judge`（独立验收，不看 agent 自述）/ `evidence`（完整性）/
`metrics`（预注册指标）/ `runner`（一次运行）。
