# 最终交付核验（示例队伍，证明流水线可交付）

> 用 `team.example.json` 走完整 `make_release.py` 流程；真实队伍替换 team.json 即可。

## 结果
| 项 | 值 |
| --- | --- |
| readiness_check | **READY_TO_SUBMIT**（文件齐全、占位符 0、一致性/评分 PASS） |
| 出包自检 | check_consistency PASS / score_check PASS / audit PASS |
| 文件数 | 16 |
| 包名 | `创意组+河南+示例大学+AgenticFlex+本科生+T000.zip` |
| 大小 | 352644 bytes |
| SHA256 | `AC6034EA8D34E25BC758F249EEA9F1696D9AF431736AB72C10217516258C43C8` |

## 包内清单
- `项目创意计划书.md`
- `创意组_AgenticFlex_展示PPT.pptx`
- `PPT大纲.md`
- `演示脚本.md`
- `答辩逐字稿.md`
- `现场操作卡.md`
- `提交清单.md`
- `README.md`
- `RELEASE_NOTES.md`
- `evidence/demo_sim.mp4`
- `evidence/EVIDENCE.md`
- `evidence/frames/frame_backfilled.png`
- `evidence/frames/frame_first.png`
- `evidence/frames/frame_last.png`
- `evidence/frames/frame_mid.png`
- `evidence/frames/README.md`

## 说明
- 命名完全符合官方规则：`创意组+省份+学校名称+项目名称+学生类别+队伍编号`。
- 真实提交时以 team.json 生成的包为准，并记录其 SHA256 至 `发送回执模板.md`。
- 本核验为流程正确性证明，非提交行为本身。
