#!/usr/bin/env python3
"""提交就绪判定：文件齐全 + 三项自检 + 占位符检查。"""
import json, os, re, subprocess, sys
HERE=os.path.dirname(os.path.abspath(__file__))
REQ=["项目创意计划书.md","创意组_AgenticFlex_展示PPT.pptx","答辩逐字稿.md",
     "演示脚本.md","现场操作卡.md","提交清单.md","邮件提交正文.md","RELEASE_NOTES.md",
     "METRICS.json","evidence/EVIDENCE.md","evidence/demo_sim.mp4"]
miss=[f for f in REQ if not os.path.isfile(os.path.join(HERE,f))]
plan=open(os.path.join(HERE,"项目创意计划书.md"),encoding="utf-8").read()
ph=re.findall(r"<[^>\s]{1,20}>", plan)
def run(s):
    return subprocess.run([sys.executable,os.path.join(HERE,s)],cwd=HERE,
                          capture_output=True,text=True,encoding="utf-8",errors="replace")
c1=run("check_consistency.py"); c2=run("score_check.py")
print("files missing:", miss or "none")
print("plan placeholders:", len(ph), (sorted(set(ph))[:6] if ph else ""))
print("consistency:", "PASS" if c1.returncode==0 else "FAIL")
print("score:", "PASS" if c2.returncode==0 else "FAIL")
ready = (not miss) and c1.returncode==0 and c2.returncode==0 and not ph
print("READY_TO_SUBMIT" if ready else "NOT_READY (fill placeholders / fix checks)")
sys.exit(0 if ready else 1)