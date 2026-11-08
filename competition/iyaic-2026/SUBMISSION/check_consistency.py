#!/usr/bin/env python3
"""校验 EVIDENCE 台账与答辩逐字稿的关键数字一致，避免口径漂移。"""
import os, re, sys
HERE=os.path.dirname(os.path.abspath(__file__))
EV=open(os.path.join(HERE,"evidence","EVIDENCE.md"),encoding="utf-8").read()
SC=open(os.path.join(HERE,"答辩逐字稿.md"),encoding="utf-8").read()
EXPECTED=["0.514","10.85","5.48","4.35","9.32","14.5","442","146","FUNCTIONAL_WINDOW_PASS","OUTCOME_SUCCEEDED"]
SC_EXPECTED=["0.514","10.85","146","442"]
ok=True
miss_ev=[t for t in EXPECTED if t not in EV]
miss_sc=[t for t in SC_EXPECTED if t not in SC]
if miss_ev: ok=False; print("EVIDENCE missing:", miss_ev)
if miss_sc: ok=False; print("SCRIPT missing:", miss_sc)
# 单位口径：毫米统一写 mm，禁止误写 cm 于落点
if re.search(r"落点[^\n]{0,20}cm", EV): ok=False; print("unit: 落点用了 cm")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)