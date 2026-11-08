#!/usr/bin/env python3
"""以 METRICS.json 为单一数据源，校验证据台账/逐字稿/PPT 的数字一致。"""
import json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
def read(p):
    try: return open(os.path.join(HERE,p),encoding="utf-8").read()
    except OSError: return ""
def pptx_text():
    try:
        from pptx import Presentation
        prs=Presentation(os.path.join(HERE,"创意组_AgenticFlex_展示PPT.pptx"))
        return "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    except Exception:
        return ""
M=json.load(open(os.path.join(HERE,"METRICS.json"),encoding="utf-8"))
EV=read("evidence/EVIDENCE.md"); SC=read("答辩逐字稿.md"); PPT=pptx_text()
cw=M["core_window"]
tokens=[cw["status"], cw["window_id"][:8], cw["runtime_fingerprint"][:8]]
tokens+= [f"{r['err_mm']:.2f}" for r in cw["runs"] if r["err_mm"] is not None]
tokens+= [f"{M['smoke']['normal_a_err_mm']:.3f}", f"{M['smoke']['camera_err_mm']:.2f}",
          str(M["frames"]["total"]), str(M["frames"]["backfilled"])]
ok=True
for t in tokens:
    if t not in EV: ok=False; print("EVIDENCE missing:", t)
# 逐字稿必须含核心窗口数字 + 相机/帧
for t in ["7.47","2.78","10.22","0.514","10.85","442","146"]:
    if t not in SC: ok=False; print("SCRIPT missing:", t)
# PPT 必须含当前指纹与窗口号片段
for t in [cw["runtime_fingerprint"][:8], cw["window_id"][:8]]:
    if t not in PPT: ok=False; print("PPT missing:", t)
print("METRICS tokens checked:", len(tokens))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)