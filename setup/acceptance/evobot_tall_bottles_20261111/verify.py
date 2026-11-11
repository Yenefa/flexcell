#!/usr/bin/env python3
"""Re-derive every number in README.md from the recorded JSON files.

No simulation is run.  Each claim in the README is restated as a computation over raw/*.json,
and the script exits non-zero if any claim does not follow from the recorded data.

It also re-checks the NEGATIVE results (the regression on cream_cheese), because a verifier
that only confirms the good news is not a verifier.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

FAILS = []
NCHECK = 0


def load(*parts):
    p = os.path.join(RAW, *parts)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def check(label, cond, detail=""):
    global NCHECK
    NCHECK += 1
    ok = bool(cond)
    if not ok:
        FAILS.append(label)
    print(("  OK   " if ok else "  FAIL ") + label + (("   [" + detail + "]") if detail else ""))


def section(t):
    print("\n=== " + t + " ===")


def approx(a, b, tol):
    return abs(float(a) - float(b)) <= tol


# ------------------------------------------------------------------ 1. geometry
section("1. The bottles are tall; geom_rbound over-reports their extent")
# NOTE: rbound_extent is recorded ONLY to reproduce the previously reported -0.069..0.117.
# It is NOT used to choose any grasp height anywhere in this work.
for idx in (2, 4):
    m = load("measure", "measure_%d.json" % idx)
    rb = m["rbound_extent"]
    true_lo, true_hi = m["aabb_collision"][0][2], m["aabb_collision"][1][2]
    check("task %d: the OLD rbound rule reproduces -0.069..0.117" % idx,
          approx(rb[0], -0.0694, 0.002) and approx(rb[1], 0.1172, 0.003), "rbound=%s" % rb)
    check("task %d: rbound says the object starts BELOW the floor (impossible)" % idx,
          rb[0] < -0.05, "rbound_z_lo=%.4f" % rb[0])
    check("task %d: true collision height is %.4f m" % (idx, true_hi - true_lo),
          (true_hi - true_lo) > 0.14, "true=%s" % ([true_lo, true_hi]))
    check("task %d: rbound grasp height is BELOW the true midpoint (why the old grasp missed)"
          % idx, m["rbound_grasp_z_frac0.5"] < (true_lo + true_hi) / 2,
          "rbound_z=%.4f true_mid=%.4f" % (m["rbound_grasp_z_frac0.5"],
                                           (true_lo + true_hi) / 2))

# ------------------------------------------------------------------ 2. spawn pose
section("2. The objects are SPAWNED under the floor and ejected on the first step")
s = load("settle", "settle_2.json")
t0 = s["t0"]["aabb"]
check("task 2: at t0 the collision geometry reaches below the floor plane",
      t0[0][2] < -0.03, "t0_z_lo=%.4f" % t0[0][2])
rows = {r["k"]: r for r in s["rows"]}
last = s["rows"][-1]
check("task 2: it comes to rest ON the floor (z_lo == 0) after the ejection",
      approx(last["aabb_z"][0], 0.0, 0.001), "settled_z_lo=%.5f" % last["aabb_z"][0])
peak = max(r["dz"] for r in s["rows"])
check("task 2: the ejection is a real jump (peak %.1f mm)" % (1000 * peak), peak > 0.05,
      "peak_dz=%.4f" % peak)
check("task 2: t0 geometry differs from settled geometry (so t0 measurement is invalid)",
      not approx(t0[1][2], last["aabb_z"][1], 0.001),
      "t0_top=%.4f settled_top=%.4f" % (t0[1][2], last["aabb_z"][1]))

# ------------------------------------------------------------------ 3. descent
section("3. A top-down descent at the OLD height is stopped by the HAND body")
d = load("descend", "descend_2.json")
lm = d["landmarks"]
check("the old rbound grasp height is %.4f m" % lm["grasp_z_rbound_frac0.5"],
      lm["grasp_z_rbound_frac0.5"] < 0.08)
lastrow = d["rows"][-1]
check("the descent stalls ABOVE the object's top",
      lastrow["eef"][2] > lm["extent_true"][1],
      "eef_z=%.4f > obj_top=%.4f" % (lastrow["eef"][2], lm["extent_true"][1]))
check("the object was NOT moved: it is a collision, not a grasp",
      d.get("object_moved") is None and abs(lastrow["obj_dz"]) < 0.005,
      "obj_dz=%.5f" % lastrow["obj_dz"])
check("the blocking contact is gripper0_hand_collision (the hand, not the pads)",
      all(any("hand_collision" in (c[0] or "") or "hand_collision" in (c[1] or "")
              for c in r["gcon"]) for r in d["rows"] if r["gcon"]),
      "contacts=%d" % sum(1 for r in d["rows"] if r["gcon"]))

# ------------------------------------------------------------------ 4. variant matrix
section("4. Which grasp variants actually CARRY the object (lift > 30 mm)")
for idx in (2, 4):
    rows = load("matrix_%d_summary.json" % idx)["variants"]
    by = {r["variant"]: r for r in rows}
    # MEASURED, and it differs between the two tasks: with the settle step added, the old
    # rbound height happens to land on a workable spot for ketchup but not for salad_dressing.
    # The old rule's failure is therefore NOT purely "wrong height" - see README section 4.
    check("task %d: rbound_mid outcome recorded as measured" % idx,
          by["rbound_mid"]["carried"] == (by["rbound_mid"]["dz_mm"] > 30),
          "carried=%s dz=%.1f mm" % (by["rbound_mid"]["carried"], by["rbound_mid"]["dz_mm"]))
    check("task %d: rbound_mid never passes the official predicate" % idx,
          by["rbound_mid"]["success"] is False,
          "success=%s" % by["rbound_mid"]["success"])
    for v in ("neck", "cap", "neck_yaw90"):
        check("task %d: variant %s carries (>30 mm)" % (idx, v),
              bool(by[v]["carried"]), "dz=%.1f mm" % by[v]["dz_mm"])
    check("task %d: every carrying variant still FAILS the official predicate" % idx,
          all(not r["success"] for r in rows if r["carried"]),
          "grasp and placement are separate failures")
    check("task %d: push_then_neck does NOT carry (pushing loses the neck)" % idx,
          not by["push_then_neck"]["carried"],
          "dz=%.1f mm" % by["push_then_neck"]["dz_mm"])

# ------------------------------------------------------------------ 5. release mechanism
section("5. Why release fails: the BASKET is pushed away")
for idx in (2, 4):
    r = load("release_%d_at_site.json" % idx)
    before = r["release_setup"]["predicate_before"]["basket_pos"]
    atrel = r["predicate_at_release"]["basket_pos"]
    drift = ((atrel[0] - before[0]) ** 2 + (atrel[1] - before[1]) ** 2) ** 0.5
    check("task %d: the basket is displaced %.1f mm during the approach" % (idx, 1000 * drift),
          drift > 0.05, "drift=%.4f m" % drift)
    check("task %d: the object is NOT inside the contain box at release" % idx,
          r["predicate_at_release"]["inside"] is False,
          "margin=%s" % r["predicate_at_release"]["margin"])
    check("task %d: the failing margin is the y axis (the push direction)" % idx,
          r["predicate_at_release"]["margin"][1] < 0,
          "margin_y=%.4f" % r["predicate_at_release"]["margin"][1])
    hang = r["lift"].get("hang_below_grip_m", r["lift"].get("carry_offset"))
    check("task %d: the object hangs well below the grip site while carried" % idx,
          abs(hang) > 0.10, "hang=%.4f m" % hang)

# ------------------------------------------------------------------ 6. clearance sweep
section("6. The fix: carry high enough that the hanging bottle clears the rim")
for idx in (2, 4):
    rows = load("carry_%d_summary.json" % idx)["rows"]
    by = {r["clearance"]: r for r in rows}
    check("task %d: clearance 0.00 m REPRODUCES the failure" % idx,
          by[0.0]["success"] is False and by[0.0]["basket_drift_m"] > 0.05,
          "drift=%.3f m" % by[0.0]["basket_drift_m"])
    for cl in (0.02, 0.04, 0.06):
        check("task %d: clearance %.2f m -> basket does not move AND predicate passes"
              % (idx, cl),
              by[cl]["success"] is True and by[cl]["basket_drift_m"] == 0.0,
              "drift=%.3f inside=%s" % (by[cl]["basket_drift_m"], by[cl]["inside"]))

# ------------------------------------------------------------------ 7. the fix
section("7. The fixed policy over every shipped init state")
tot = ok = 0
for fname, tasks in (("fixed_summary_2_4.json", (2, 4)),
                     ("fixed_summary_0_1.json", (0, 1)),
                     ("fixed_summary_3.json", (3,))):
    rows = load(fname)["rows"]
    for r in rows:
        if "error" in r:
            check("task %d init %d ran without exception" % (r["task"], r["init_idx"]),
                  False, r["error"])
            continue
        tot += 1
        ok += 1 if r["success"] else 0
        if r["task"] in (2, 4):
            check("TARGET task %d init %d: carried and officially succeeded"
                  % (r["task"], r["init_idx"]),
                  bool(r["carried"]) and bool(r["success"]),
                  "lift=%.1f mm drift=%s" % (r["lift_mm"], r["basket_drift_m"]))
        else:
            print("  ..   regression task %d init %d: success=%s lift=%.1f mm"
                  % (r["task"], r["init_idx"], r["success"], r["lift_mm"]))

target = [r for f, _t in (("fixed_summary_2_4.json", (2, 4)),) for r in load(f)["rows"]]
n_t = len(target)
n_ok = sum(1 for r in target if r["success"])
check("TARGET tasks 2 and 4: %d/%d init states officially succeed" % (n_ok, n_t),
      n_ok == n_t and n_t == 10, "%d/%d" % (n_ok, n_t))

# the regression is a RECORDED FACT, not a hidden one
reg = load("fixed_summary_0_1.json")["rows"]
cc = [r for r in reg if r["task"] == 1]
cc_ok = sum(1 for r in cc if r["success"])
check("REGRESSION recorded: cream_cheese (task 1) succeeds %d/%d - NOT fixed by this work"
      % (cc_ok, len(cc)), cc_ok < len(cc), "%d/%d" % (cc_ok, len(cc)))

# ------------------------------------------------------------------ verdict
print("\n=== VERDICT ===")
print("checks run: %d   failed: %d" % (NCHECK, len(FAILS)))
print("target tasks 2+4: %d/%d official successes" % (n_ok, n_t))
if FAILS:
    print("FAILED CHECKS:")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("ALL CHECKS PASS - every README number re-derived from raw/*.json")
sys.exit(0)
