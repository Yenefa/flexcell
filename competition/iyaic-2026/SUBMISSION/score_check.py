#!/usr/bin/env python3
"""按创意组 6 项评分权重，检查计划书/PPT/逐字稿是否都有对应支撑。"""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
def read(p):
    try: return open(os.path.join(HERE,p),encoding="utf-8").read()
    except OSError: return ""
def pptx_text():
    try:
        from pptx import Presentation
    except Exception:
        return ("", 0)
    f=os.path.join(HERE,"创意组_AgenticFlex_展示PPT.pptx")
    if not os.path.isfile(f): return ("",0)
    prs=Presentation(f); out=[]
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame: out.append(sh.text_frame.text)
    return ("\n".join(out), len(prs.slides))
PLAN=read("项目创意计划书.md"); OUT=read("PPT大纲.md"); SC=read("答辩逐字稿.md")
PPT,NSLIDE=pptx_text()
CORPUS=PLAN+"\n"+OUT+"\n"+SC+"\n"+PPT
ITEMS=[
 ("项目创新性",25,["创新点","创新性","原创"]),
 ("技术可行性",20,["技术路线","架构","MoveIt","ROS"]),
 ("实用性",15,["应用前景","场景","市场"]),
 ("项目完成度",15,["完成","指标","已验证","实测"]),
 ("团队协作与贡献",20,["团队","分工","贡献"]),
 ("答辩与展示效果",5,["答辩","PPT","展示"]),
]
ok=True; print("PPT slides:", NSLIDE)
for name,w,kws in ITEMS:
    miss=[k for k in kws if k not in CORPUS]
    if miss: ok=False; print(f"[WEAK] {name} ({w}%) missing {miss}")
    else: print(f"[ OK ] {name} ({w}%)")
print("TOTAL WEIGHT:", sum(w for _,w,_ in ITEMS))
print("PASS" if ok and NSLIDE>=12 else "FAIL")
sys.exit(0 if ok and NSLIDE>=12 else 1)
