#!/usr/bin/env python3
"""终检：当前口径文档不得残留旧构建数字；必备要素齐全；PPT 文本同步。"""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
DOCS=["项目创意计划书.md","PPT大纲.md","答辩逐字稿.md","答辩问答30题.md","电梯陈述60秒.md",
      "README.md","RELEASE_NOTES.md","现场操作卡.md","一键提交.md","提交清单.md","邮件提交正文.md"]
STALE=["0.514","10.85","442","146","5.48","4.35","9.32"]
REQ=["7.47","5.25","557","39","iyaicmsczh@163.com","2026-11-13","dd456b9b","8b1c18af"]
def read(p):
    try: return open(os.path.join(HERE,p),encoding="utf-8").read()
    except OSError: return ""
def pptx_text():
    try:
        from pptx import Presentation
        prs=Presentation(os.path.join(HERE,"创意组_AgenticFlex_展示PPT.pptx"))
        return "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    except Exception: return ""
bad=[]
for d in DOCS:
    t=read(d); hit=[x for x in STALE if x in t]
    if hit: bad.append((d,hit))
ppt=pptx_text(); ph=[x for x in STALE if x in ppt]
if ph: bad.append(("PPT",ph))
corpus="\n".join(read(d) for d in DOCS)+"\n"+ppt
miss=[x for x in REQ if x not in corpus]
print("STALE hits:", bad or "none")
print("REQUIRED missing:", miss or "none")
ok = not bad and not miss
print("AUDIT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)