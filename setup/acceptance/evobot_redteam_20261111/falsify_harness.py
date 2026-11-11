#!/usr/bin/env python3
"""Falsification harness: mutate a copy of each acceptance dir and see whether verify.py fails.

Read-only w.r.t. the repo: every mutation happens in ./_falsify/<case>/ copies.
"""
import json, os, shutil, subprocess, sys, textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACC = HERE.parent
WORK = HERE / "_falsify"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)

def cp(src):
    dst = WORK / (src + "__" + str(len(list(WORK.iterdir()))))
    shutil.copytree(ACC / src, dst)
    return dst

def run(d):
    p = subprocess.run([sys.executable, "verify.py"], cwd=str(d), capture_output=True, text=True, timeout=300)
    first = (p.stderr.strip().splitlines() or [""])[-1]
    return p.returncode, first[:150]

def jload(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def jdump(p, o): Path(p).write_text(json.dumps(o, indent=2, ensure_ascii=False), encoding="utf-8")

CASES = []

def case(label, src, mutate, expect):
    CASES.append((label, src, mutate, expect))

# ---------- official ----------
def m_action_dim(d):
    o = jload(d/"run_result.json"); o["action_dim"] = 6; jdump(d/"run_result.json", o)
def m_noop_true(d):
    o = jload(d/"run_result.json"); o["official_success_with_noop_policy"] = True; jdump(d/"run_result.json", o)
def m_init_note(d):
    o = jload(d/"run_result.json"); o["init_note"] = "not used"; jdump(d/"run_result.json", o)
def m_stepped_999(d):
    o = jload(d/"run_result.json"); o["stepped"] = 999; jdump(d/"run_result.json", o)

case("official: action_dim 7->6", "evobot_libero_official_20261111", m_action_dim, "FAIL")
case("official: noop success false->true", "evobot_libero_official_20261111", m_noop_true, "FAIL")
case("official: init_note says init NOT loaded", "evobot_libero_official_20261111", m_init_note, "FAIL")
case("official: stepped 5->999 (fabricated step count)", "evobot_libero_official_20261111", m_stepped_999, "PASS?")

# ---------- adapter ----------
def m_ad_success(d):
    o = jload(d/"result.json"); o["official_success"] = True; jdump(d/"result.json", o)
def m_ad_reach(d):
    o = jload(d/"result.json"); o["reach_probe"]["lowest_eef_z_in_free_space"] = 0.09; jdump(d/"result.json", o)
def m_ad_final(d):
    o = jload(d/"result.json"); o["log"][-1] = "object final [0.02,0.25,0.10] - moved into the basket"; jdump(d/"result.json", o)
def m_ad_phase(d):
    o = jload(d/"result.json"); o["phase_success"] = False; jdump(d/"result.json", o)

case("adapter: official_success false->true", "evobot_libero_adapter_20261111", m_ad_success, "FAIL")
case("adapter: reach probe 0.02->0.09", "evobot_libero_adapter_20261111", m_ad_reach, "FAIL")
case("adapter: log says object MOVED to basket (contradicts claim)", "evobot_libero_adapter_20261111", m_ad_final, "PASS?")
case("adapter: phase_success true->false", "evobot_libero_adapter_20261111", m_ad_phase, "FAIL")

# ---------- solved ----------
def m_sv_success(d):
    o = jload(d/"result.json"); o["official_success"] = False; jdump(d/"result.json", o)
def m_sv_nomove(d):
    o = jload(d/"result.json"); o["log"][-1] = "object final at [-0.12, -0.24, 0.015] ; distance to basket_1_main = 0.51 m"; jdump(d/"result.json", o)
def m_sv_basket_z(d):
    o = jload(d/"result.json"); o["log"][2] = "target basket_1_main at [0.015, 0.252, 0.035]"; jdump(d/"result.json", o)
def m_sv_calib(d):
    o = jload(d/"calibration.json")
    for r in o: r.pop("lift_above_control", None)
    jdump(d/"calibration.json", o)

case("solved: official_success true->false", "evobot_libero_solved_20261111", m_sv_success, "FAIL")
case("solved: object did not move", "evobot_libero_solved_20261111", m_sv_nomove, "FAIL")
case("solved: rewritten log says basket z=0.035 (README's number)", "evobot_libero_solved_20261111", m_sv_basket_z, "PASS?")
case("solved: strip lift_above_control (the 'control arm')", "evobot_libero_solved_20261111", m_sv_calib, "FAIL")

# ---------- transfer ----------
def m_tr_success(d):
    o = jload(d/"t1.json"); o["official_success"] = True; jdump(d/"t1.json", o)
def m_tr_region(d):
    o = jload(d/"t1.json"); o["parsed_region"] = "basket_1"; jdump(d/"t1.json", o)
def m_tr_obj(d):
    o = jload(d/"t1.json"); o["parsed_object"] = "cream_cheese_2"; jdump(d/"t1.json", o)
def m_tr_log(d):
    o = jload(d/"t1.json"); o["log"][2] = "object while carried at [0.02, 0.25, 0.12]"; o["log"][3]="success trace during settle: [True, True]"; jdump(d/"t1.json", o)

case("transfer: failed task t1 flips to success", "evobot_libero_transfer_20261111", m_tr_success, "FAIL")
case("transfer: parsed_region loses _contain_region", "evobot_libero_transfer_20261111", m_tr_region, "FAIL")
case("transfer: parsed_object changed to a different object", "evobot_libero_transfer_20261111", m_tr_obj, "PASS?")
case("transfer: t1 log now says it WAS carried (contradicts 'not grasped')", "evobot_libero_transfer_20261111", m_tr_log, "PASS?")

# ---------- geometry ----------
def m_ge_success(d):
    o = jload(d/"mid_2.json"); o["official_success"] = True; jdump(d/"mid_2.json", o)
def m_ge_top(d):
    for i in range(5):
        p = d/("top_%d.json" % i)
        if p.exists(): p.unlink()
def m_ge_salad(d):
    o = jload(d/"mid_2.json")
    o["log"] = [l.replace("0.107", "0.030") for l in o["log"]]
    jdump(d/"mid_2.json", o)
def m_ge_topfrac(d):
    o = jload(d/"top_0.json"); o["frac"] = 0.70; jdump(d/"top_0.json", o)

case("geometry: mid_2 flips to success", "evobot_libero_geometry_grasp_20261111", m_ge_success, "FAIL")
case("geometry: delete all top_*.json (the 0.85 arm)", "evobot_libero_geometry_grasp_20261111", m_ge_top, "FAIL")
case("geometry: salad log now says it descended to 0.030", "evobot_libero_geometry_grasp_20261111", m_ge_salad, "PASS?")
case("geometry: top_0 claims frac 0.70 (README's third arm)", "evobot_libero_geometry_grasp_20261111", m_ge_topfrac, "PASS?")

# ---------- side grasp ----------
def m_sg_success(d):
    o = jload(d/"side_1.json"); o["official_success"] = False; jdump(d/"side_1.json", o)
def m_sg_logs(d):
    for i in range(5):
        p = d/("side_%d.json" % i)
        o = jload(p); o["log"] = ["no termination note here"]; jdump(p, o)
def m_sg_err(d):
    o = jload(d/"side_1.json"); o["release_xy_error_m"] = 0.5; jdump(d/"side_1.json", o)

case("side: side_1 success true->false", "evobot_libero_side_grasp_20261111", m_sg_success, "FAIL")
case("side: erase 'episode terminated' from every log", "evobot_libero_side_grasp_20261111", m_sg_logs, "PASS?")
case("side: a 'successful' release error -> 0.5 m", "evobot_libero_side_grasp_20261111", m_sg_err, "FAIL")

# ---------- auto approach ----------
def m_au_success(d):
    o = jload(d/"auto_3.json"); o["official_success"] = False; jdump(d/"auto_3.json", o)
def m_au_sidey(d):
    for i in (2,4):
        p = d/("side_y_%d.json" % i)
        if p.exists(): p.unlink()
def m_au_sidey_val(d):
    for i in (2,4):
        p = d/("side_y_%d.json" % i)
        o = jload(p); o["official_success"] = True; o["release_xy_error_m"] = 0.0
        jdump(p, o)
def m_au_clamp(d):
    for i in range(5):
        p = d/("clamped_%d.json" % i)
        o = jload(p); o["official_success"] = True; jdump(p, o)
def m_au_mode(d):
    o = jload(d/"auto_3.json"); o["mode"] = "top"; jdump(d/"auto_3.json", o)

case("auto: auto_3 success true->false", "evobot_libero_auto_approach_20261111", m_au_success, "FAIL")
case("auto: delete side_y_2/4 (the 'side_y' refutation)", "evobot_libero_auto_approach_20261111", m_au_sidey, "PASS?")
case("auto: side_y runs flip to success 0.0 mm error", "evobot_libero_auto_approach_20261111", m_au_sidey_val, "PASS?")
case("auto: clamped arm now 5/5", "evobot_libero_auto_approach_20261111", m_au_clamp, "FAIL")
case("auto: auto_3 reports mode=top", "evobot_libero_auto_approach_20261111", m_au_mode, "FAIL")

# ---------- holdout ----------
def m_ho_success(d):
    o = jload(d/"s0.json"); o["official_success"] = True; jdump(d/"s0.json", o)
def m_ho_mode(d):
    o = jload(d/"s0.json"); o["mode"] = "top"; jdump(d/"s0.json", o)
def m_ho_err(d):
    o = jload(d/"s0.json"); o["release_xy_error_m"] = 0.05; jdump(d/"s0.json", o)
def m_ho_log(d):
    o = jload(d/"s0.json")
    o["log"] = [l.replace("auto: measured height 0.168", "auto: measured height 0.090") for l in o["log"]]
    jdump(d/"s0.json", o)

case("holdout: one task flips to success", "evobot_libero_holdout_spatial_20261111", m_ho_success, "FAIL")
case("holdout: one task claims mode=top", "evobot_libero_holdout_spatial_20261111", m_ho_mode, "FAIL")
case("holdout: release error 0.48->0.05", "evobot_libero_holdout_spatial_20261111", m_ho_err, "FAIL")
case("holdout: log 'measured height 0.168' -> 0.090", "evobot_libero_holdout_spatial_20261111", m_ho_log, "PASS?")

# ---------- closed loop ----------
def m_cl_success(d):
    o = jload(d/"obj_3.json"); o["official_success"] = False; jdump(d/"obj_3.json", o)
def m_cl_attempt(d):
    o = jload(d/"obj_3.json"); o["attempts"] = o["attempts"][:1]; jdump(d/"obj_3.json", o)
def m_cl_spa(d):
    o = jload(d/"spa_0.json"); o["attempts"][0]["carried"] = True; jdump(d/"spa_0.json", o)
def m_cl_obj2(d):
    o = jload(d/"obj_2.json")
    for a in o["attempts"]: a["carried"] = True; a["lift_m"] = 0.13
    jdump(d/"obj_2.json", o)

case("closed-loop: obj_3 success -> false", "evobot_libero_closed_loop_retry_20261111", m_cl_success, "FAIL")
case("closed-loop: obj_3 loses the retry attempt", "evobot_libero_closed_loop_retry_20261111", m_cl_attempt, "FAIL")
case("closed-loop: spa_0 claims carried=True", "evobot_libero_closed_loop_retry_20261111", m_cl_spa, "FAIL")
case("closed-loop: obj_2 claims both attempts carried", "evobot_libero_closed_loop_retry_20261111", m_cl_obj2, "PASS?")

print("%-62s %-6s %-6s %s" % ("mutation", "expect", "rc", "verifier message"))
bad = 0
for label, src, mutate, expect in CASES:
    d = cp(src)
    mutate(d)
    rc, msg = run(d)
    got = "PASS" if rc == 0 else "FAIL"
    flag = "" if (got == "PASS") == (expect == "PASS?") else "   <== interesting"
    if flag: bad += 1
    print("%-62s %-6s %-6s %s%s" % (label, expect, rc, msg, flag))
print()
print("cases:", len(CASES), "surprises:", bad)
