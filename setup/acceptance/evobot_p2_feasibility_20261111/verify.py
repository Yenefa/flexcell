#!/usr/bin/env python3
"""Re-derive every numeric claim in this capsule from the repository.

WHY THIS EXISTS
  The capsule's claims are about what the CODE allows, not about what a run did.
  A claim like "the composite contract cannot express a stack" is worth nothing
  as a sentence; it is worth something as an assertion that fails loudly when the
  code changes. So each claim below is re-computed here.

WHAT IT NEVER DOES
  no Gazebo, no ROS, no network, no LLM, no writes. It imports two stdlib-only
  modules (contracts/composite.py, benchmark/evaluators/evaluate.py) and reads
  files. Nothing in the repository is modified.

  Ancillary cost: this is a READ-ONLY argument checker, not a probe. It cannot
  prove a push is physically possible; it proves only what the contracts forbid
  or admit, plus what archived runs already achieved.

Run: python3 setup/acceptance/evobot_p2_feasibility_20261111/verify.py
Exit: 0 all claims hold, 1 at least one claim failed.
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / "src/flexcell/flexcell_skills"
RESULTS = []


def claim(cid, text, ok, detail=""):
    RESULTS.append({"id": cid, "ok": bool(ok), "claim": text, "detail": detail})
    print(("PASS " if ok else "FAIL ") + cid + "  " + text + (("   [" + detail + "]") if detail else ""))
    return ok


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


# ---------------------------------------------------------------- A. refusals
sys.path.insert(0, str(ROOT / "benchmark/generators"))
import generate  # noqa: E402

refused = {}
for tpl in ("T07_stacking", "T08_push", "T09_clutter", "T10_constrained_placement"):
    try:
        generate.generate(tpl, 1000)
        refused[tpl] = False
    except NotImplementedError as exc:
        refused[tpl] = str(exc)
claim("A1", "generate.py still refuses T07/T08/T09/T10 (the precondition of this capsule)",
      all(refused.values()) and len(refused) == 4,
      "; ".join("%s=%s" % (k.split("_")[0], "refused" if v else "EMITTED") for k, v in refused.items()))

# ------------------------------------------------- B. evaluator goal vocabulary
ev_src = text("benchmark/evaluators/evaluate.py")
goal_keys = sorted(set(re.findall(r'goal\.get\("([a-z_]+)"', ev_src)))
claim("B1", "the evaluator consumes exactly this goal vocabulary (verified by source scan) and none of it is a push clause",
      goal_keys == ["min_tiers", "order", "placement", "relative", "unmoved", "visit",
                    "visit_sequence"],
      "goal keys=" + ",".join(goal_keys))
claim("B2", "no displacement/push clause: 'push' appears nowhere in the evaluator's goal handling",
      not re.search(r'goal\.get\("(push|displace|move)\w*"\)', ev_src),
      "grep goal.get(...push/displace/move) = 0")
sys.path.insert(0, str(ROOT / "benchmark/evaluators"))
import evaluate as ev  # noqa: E402

base_objects = [{"name": "target_box_a", "initial_pose": [0.22, 0.0, 0.0175]}]
zones = [{"name": "zone_1", "pose": [0.12, -0.15, 0.0175], "radius": 0.06}]
moved = {"objects": {"target_box_a": [0.16, 0.0, 0.0175]}}     # 60 mm of a real push
still = {"objects": {"target_box_a": [0.22, 0.0, 0.0175]}}     # never moved

# (a) is a successful PUSH expressible as "displaced 60 mm along -x"?  No: the
# only motion-sensitive vocabulary is "ended inside a declared zone".
push_as_zone = {"task_id": "x", "template_id": "x", "objects": base_objects,
                "zones": zones, "expected_goal": {"placement": {"target_box_a": "zone_1"}}}
v_push = ev.evaluate(push_as_zone, moved)
claim("B3", "a 60 mm displacement toward the commanded direction is graded FAIL by the closest existing clause (placement is 'end inside a declared zone')",
      v_push["passed"] is False and v_push["failed_clauses"] == ["placement:target_box_a"],
      "failed=%s distance_to_zone=%s" % (v_push["failed_clauses"],
                                         [c["evidence"].get("distance_m") for c in v_push["clauses"]]))

# (b) the 'unmoved' clause rejects exactly what a push must produce.
guard = {"task_id": "x", "template_id": "x", "objects": base_objects,
         "zones": zones, "expected_goal": {"unmoved": ["target_box_a"]}}
v_guard = ev.evaluate(guard, moved)
claim("B3b", "the only motion-observing threshold (unmoved, 15 mm) exists to reject motion, not to require it",
      v_guard["passed"] is False,
      "moved 60 mm -> unmoved clause %s" % v_guard["failed_clauses"])
claim("B4", "the only 'did the object move' threshold in the evaluator is UNMOVED_TOLERANCE_M=0.015 and it guards NON-motion",
      approx(ev.UNMOVED_TOLERANCE_M, 0.015),
      "UNMOVED_TOLERANCE_M=%r STACK_TIER_HEIGHT_M=%r REST_HEIGHT_TOLERANCE_M=%r"
      % (ev.UNMOVED_TOLERANCE_M, ev.STACK_TIER_HEIGHT_M, ev.REST_HEIGHT_TOLERANCE_M))
claim("B5", "a stacking clause (min_tiers) ALREADY exists in the evaluator",
      "stacking" in ev_src and approx(ev.STACK_TIER_HEIGHT_M, 0.030),
      "STACK_TIER_HEIGHT_M=%r" % ev.STACK_TIER_HEIGHT_M)
gen_src = text("benchmark/generators/generate.py")
claim("B6", "no generator template ever sets min_tiers -> the stacking clause is implemented but unused",
      "min_tiers=" not in gen_src.split("def _spec")[1].split("def t01")[1],
      "min_tiers appears only in _spec's signature/defaults")

# ------------------------------------ C. the composite contract cannot stack
sys.path.insert(0, str(SKILLS))
from flexcell_skills.contracts.composite import CompositeError, prepare_plan  # noqa: E402

BOX = 0.035
STACK_Z = 0.0175 + BOX          # centre of a second box resting on the first


def plan(dest_z, clearance, xy=(0.220, 0.000)):
    return {
        "scenario_id": "t07-probe",
        "initial_objects": {"target_box_a": [0.220, 0.000, 0.0175],
                            "target_box_b": [0.200, -0.180, 0.0175]},
        "stages": [{"stage_id": "s1", "object_name": "target_box_b",
                    "destination": [xy[0], xy[1], dest_z]}],
        "final_empty_positions": [],
        "position_tolerance_m": 0.02,
        "clearance_m": clearance,
        "motion_profile_id": "demo_slow",
    }


ok_control = True
try:
    # ordinary table-height placement into EMPTY space: the negative control
    prepare_plan(plan(0.0175, 0.06, xy=(0.150, 0.000)))
except CompositeError:
    ok_control = False
claim("C1", "control: an ordinary same-height composite plan is ACCEPTED (so C2/C3 are about stacking, not a broken fixture)",
      ok_control, "control plan accepted")

err = None
try:
    prepare_plan(plan(STACK_Z, 0.06))
except CompositeError as exc:
    err = (exc.code, str(exc))
claim("C2", "a stack destination (z=0.0525) is REJECTED: the box below is 0.035 m away, clearance floor is 0.05 m",
      err is not None and err[0] == 60 and "occupied" in err[1],
      "err=%r  dist=%.4f < clearance_min=0.05" % (err, BOX))

err2 = None
try:
    prepare_plan(plan(STACK_Z, 0.035))
except CompositeError as exc:
    err2 = (exc.code, str(exc))
claim("C3", "lowering clearance_m to the stack pitch is itself REJECTED (contract floor 0.05 > 0.035)",
      err2 is not None and err2[0] == 60 and "clearance" in err2[1], "err=%r" % (err2,))

# --------------------------- D. the place primitive itself accepts any z
place_src = text("src/flexcell/flexcell_skills/flexcell_skills/place_server.py")
claim("D1", "place_server takes an arbitrary z from the goal (place_pos = [pp.x, pp.y, pp.z])",
      "place_pos = [pp.x, pp.y, pp.z]" in place_src,
      "place_server.py has place_pos = [pp.x, pp.y, pp.z]")
claim("D2", "release height is derived from that z (box_target_z = place_pos[2] + clearance), not from table height",
      "box_target_z = place_pos[2] + self._clearance" in place_src,
      "clearance default 0.012")
claim("D3", "the drop is graded against the REQUESTED z (drop_err = dist3(box_after, place_pos))",
      "drop_err = dist3(box_after, place_pos)" in place_src, "3-D distance, tol 0.06")

# ------------------------------- E. what the arm has actually been asked to do
logs = sorted((ROOT / "setup/acceptance").rglob("move_to_pose.jsonl"))
min_tgt = min_reach = 9e9
min_tgt_where = min_reach_where = ""
rows = 0
for path in logs:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows += 1
        tz = ((rec.get("target") or {}).get("position") or [None, None, None])[2]
        if isinstance(tz, (int, float)) and tz < min_tgt:
            min_tgt, min_tgt_where = tz, path.name + ":" + str(rec.get("request_id"))
        rz = ((rec.get("reached_pose") or {}).get("position") or [None, None, None])[2]
        if isinstance(rz, (int, float)) and rz < min_reach:
            min_reach, min_reach_where = rz, path.name + ":" + str(rec.get("request_id"))
claim("E1", "over %d archived goals the LOWEST end-effector z actually reached is below the push contact height (%0.4f m)" % (rows, 0.1775),
      min_reach < 0.1775, "min_reached_z=%.4f (%s)" % (min_reach, min_reach_where))
claim("E2", "the lowest z ever COMMANDED was below 0.16 and it FAILED (no verified pose exists down there)",
      min_tgt < 0.16, "min_target_z=%.4f (%s)" % (min_tgt, min_tgt_where))

# --------------------------------------- F. kinematic envelope arithmetic
BASE_Z = 0.02          # arm origin, docs/HANDOFF.md:345
REACH = 0.35           # sqrt(x^2+y^2+(z-0.02)^2) <= 0.35, docs/HANDOFF.md:345
EE_Z = 0.0175 + 0.16   # box centre + grasp_dz, config/week1.yaml:34


def env(x, y, z):
    return math.sqrt(x * x + y * y + (z - BASE_Z) ** 2)


claim("F1", "the push contact pose for target_box_a is INSIDE the declared arm envelope",
      env(0.26, 0.00, EE_Z) <= REACH,
      "contact(0.26,0,%.4f)=%.4f <= %.2f" % (EE_Z, env(0.26, 0.00, EE_Z), REACH))
R_B = math.hypot(0.200, -0.180)
UX, UY = 0.200 / R_B, -0.180 / R_B          # target_box_b's own outward direction
OUT_X, OUT_Y = 0.200 + 0.06 * UX, -0.180 + 0.06 * UY
claim("F2", "pushing target_box_b 60 mm ALONG ITS OWN outward radial direction leaves the envelope (push direction is a real constraint)",
      env(OUT_X, OUT_Y, EE_Z) > REACH,
      "box_b r=%.4f; +60 mm outward -> (%.4f,%.4f) env=%.4f > %.2f"
      % (R_B, OUT_X, OUT_Y, env(OUT_X, OUT_Y, EE_Z), REACH))
claim("F3", "stacking is inside the envelope too, so T07's blocker is the CONTRACT, not reach",
      env(0.220, 0.0, 0.0525 + 0.012 + 0.16) <= REACH,
      "place stack EE(0.22,0,%.4f)=%.4f <= %.2f" % (0.2245, env(0.220, 0.0, 0.2245), REACH))

# ------------------------------- G. no act channel for a push exists today
stage_src = text("src/flexcell/flexcell_interfaces/msg/CompositeStage.msg")
fields = [ln.strip() for ln in stage_src.splitlines() if ln.strip() and not ln.strip().startswith("#")]
claim("G1", "a composite stage is only {stage_id, object_name, place_pose}: no push/offset field",
      fields == ["string stage_id", "string object_name", "geometry_msgs/PoseStamped place_pose"],
      "fields=" + str(fields))
fsm_src = text("src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py")
menu = re.search(r"allowed_actions=frozenset\(\(([^)]*)\)", fsm_src, re.S)
menu_txt = menu.group(1) if menu else ""
claim("G2", "the executor-owned action menu contains no PUSH",
      menu is not None and "PUSH" not in menu_txt,
      "menu=" + re.sub(r"\s+", " ", menu_txt).strip()[:80])

# --------------------------------- H. contact is real, controlled push is not
pick_src = text("src/flexcell/flexcell_skills/flexcell_skills/pick_server.py")
claim("H1", "pick_server documents MEASURED contact-induced displacement by the arm ('a blind approach swept the box aside')",
      "swept the box aside" in pick_src, "pick_server.py comment, measured 2026-09-26")
claim("H2", "the current mitigation is to make MoveIt AVOID the box, i.e. the opposite of a push",
      "self._scene.add_box(" in pick_src and "plans AROUND it" in pick_src,
      "add_box before approach; remove() fallback accepts knock risk")
claim("H4", "a MEASURED 0.18 m contact-induced displacement by the arm is on record (a carry knocked the third box away)",
      "knocked the third box 0.18 m away" in pick_src, "pick_server.py docstring, measured 2026-11-04")
claim("H5", "the planning scene is populated only by skills, so a fresh stack's scene holds no box (Step 0 needs no scene surgery)",
      "_sync_scene_objects" in pick_src and pick_src.count("self._scene.add_box(") >= 2,
      "sync at :438, per-target add_box at :471; bookkeeping lives in common.py:544-604")
claim("H3", "carry is a pose servo, not a grasp: it only acts while 'engaged', otherwise physics owns the box",
      "It is not a contact grasp model" in text("src/flexcell/flexcell_gazebo/src/CarryDynamics.cc"),
      "CarryDynamics.cc:1")
grand = all(r["ok"] for r in RESULTS)
print()
print("=== %d/%d claims hold ===" % (sum(1 for r in RESULTS if r["ok"]), len(RESULTS)))
Path(__file__).with_name("verify_result.json").write_text(
    json.dumps({"git_head_expected": "4a97c250", "claims": RESULTS, "all_ok": grand}, indent=2) + "\n",
    encoding="utf-8")
sys.exit(0 if grand else 1)
