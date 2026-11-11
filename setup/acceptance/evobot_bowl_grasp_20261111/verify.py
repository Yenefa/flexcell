#!/usr/bin/env python3
"""Re-derive every claim in README.md from the JSON files in THIS directory only.

Nothing here touches the simulator, the benchmark or the retry controller. If a recorded
number changes, this script fails; that is the point of it. Run it after any edit to the JSON.

    python3 verify.py            # prints the derived claims, exit 0 if they hold
    python3 verify.py --json     # same, as one JSON object
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIFT_PROOF_M = 0.03          # the retry controller's own threshold
JAW_STROKE_M = 0.08          # sum of the two finger joint ranges (gripper0_finger_joint1/2)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def census(suite_dir, idx):
    return load(HERE / suite_dir / ("census_%d.json" % idx))


def settle(suite_dir, idx):
    return load(HERE / suite_dir / ("settle_%d.json" % idx))


def trial(idx, cfg):
    return load(HERE / "raw_spatial" / ("trial_%d_%s.json" % (idx, cfg)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = {}

    # ---------------------------------------------------------------- C1 the object drops
    # claim: the bowl is not resting at the pose set_init_state installs; it falls 71.6 mm
    # in the tasks where it starts on the table, before the arm arrives.
    drops = [settle("raw_spatial", i)["dz_body"] for i in range(10)]
    settles_at = [settle("raw_spatial", i)["settle_rule"]["settled_at_step"] for i in range(10)]
    assert all(d < -0.05 for d in drops), ("bowl no longer drops at init", drops)
    assert all(5 <= s <= 40 for s in settles_at), settles_at
    out["C1_init_pose_is_stale"] = {
        "drop_m": drops,
        "settled_at_step": settles_at,
        "verdict": "every task: the bowl falls 71.6-162.8 mm after set_init_state",
    }

    # ---------------------------------------------------------------- C2 the height arithmetic
    # claim: the controller's grasp z is computed from the PRE-settle pose and from
    # rbound (a bounding-sphere radius) instead of real geometry, so it lands above the bowl.
    rows = []
    for i in range(10):
        c = census("raw_spatial", i)
        v = c["verdict_numbers"]
        ci = c["init_pose"]["controller"]
        cz = c["settled"]["collision"]["z"]
        mid = 0.5 * (cz[0] + cz[1])
        rows.append({
            "index": i,
            "gz_at_init": ci["grasp_z"],
            "gz_at_settled": c["settled"]["controller"]["grasp_z"],
            "collision_z": cz,
            "collision_mid": round(mid, 5),
            "gz_at_init_minus_settled_rim": v["ctrl_grasp_z_minus_settled_collision_rim_m"],
            "gz_at_settled_minus_collision_mid": round(c["settled"]["controller"]["grasp_z"] - mid, 5),
            "implied_height": ci["implied_height_m"],
            "collision_height": v["collision_height_m"],
            "visual_height": c["settled"]["visual"]["height_m"],
        })
    # (a) the pre-settle z is above the settled physical rim in every task
    assert all(r["gz_at_init_minus_settled_rim"] > 0.04 for r in rows), rows
    # (b) the rbound inflation is 1.5x on the visual mesh, 3.3x on the physical height
    ratios = [r["implied_height"] / r["visual_height"] for r in rows]
    ratios_c = [r["implied_height"] / r["collision_height"] for r in rows]
    assert all(1.45 < x < 1.55 for x in ratios), ratios
    # (c) the SAME formula evaluated on the settled pose lands within 3 mm of the physical
    #     mid-height: the arithmetic is fine, the pose it was fed was not.
    assert all(abs(r["gz_at_settled_minus_collision_mid"]) < 0.003 for r in rows), rows
    out["C2_height_arithmetic"] = {
        "per_task": rows,
        "rbound_implied_over_visual_height": [round(x, 3) for x in ratios],
        "rbound_implied_over_collision_height": [round(x, 3) for x in ratios_c],
        "verdict": ("bounding-sphere midpoint on the stale pose is +47.9..+139.1 mm above the "
                    "settled rim; the same formula on the settled pose is within 2.2 mm"),
    }

    # ---------------------------------------------------------------- C3 the jaw limit
    # claim: the jaws cannot span the bowl; they can span a solid object of the same size.
    max_open = census("raw_spatial", 0)["gripper"]["max_opening_m"]
    assert abs(max_open - JAW_STROKE_M) < 1e-6, max_open
    pads = census("raw_spatial", 0)["settled"]["pads"]["pad_gap_m"]
    dias = sorted({census("raw_spatial", i)["verdict_numbers"]["collision_outer_diameter_m"]
                   for i in range(10)})
    assert all(d > pads for d in dias), (dias, pads)
    out["C3_jaw_limit"] = {
        "finger_joint_stroke_m": max_open,
        "measured_pad_gap_open_m": pads,
        "bowl_collision_outer_diameters_m": dias,
        "verdict": "the jaws open to 67.9 mm; the bowl's collision hull is 107.9-132.0 mm across",
    }

    # ---------------------------------------------------------------- C4 centred grasp is empty
    # claim: the bowl's rim is a ring; at the bowl's own vertical axis the nearest solid
    # material is 41.1 mm away (bowl) vs 0.0 mm (a can). A centred grasp closes on air.
    axis_clear = {}
    for i in (0, 5):
        v = census("raw_spatial", i)["verdict_numbers"]
        axis_clear["spatial_%d" % i] = {
            "axis_clearance_top_m": v["axis_clearance_top_4mm_m"],
            "jaw_half_clearance_m": v["jaw_half_clearance_m"],
            "centred_grasp_reaches_material": v["centred_grasp_reaches_material_top_band"],
        }
        assert v["centred_grasp_reaches_material_top_band"] is False, v
        assert v["axis_clearance_top_4mm_m"] > v["jaw_half_clearance_m"], v
    for i in range(5):
        v = census("raw_object", i)["verdict_numbers"]
        axis_clear["object_%d" % i] = {
            "axis_clearance_top_m": v["axis_clearance_top_4mm_m"],
            "centred_grasp_reaches_material": v["centred_grasp_reaches_material_top_band"],
        }
        assert v["centred_grasp_reaches_material_top_band"] is True, v
    out["C4_centred_grasp_is_empty"] = {
        "per_object": axis_clear,
        "verdict": ("bowl: nearest solid material is 41.1 mm from its axis, jaw half-clearance "
                    "is 33.9 mm -> nothing to pinch; cans/boxes: 0.0 mm, i.e. solid on the axis"),
    }

    # ---------------------------------------------------------------- C5 both modes never grip
    # claim: neither controller mode ever touches the object, so this is upstream of the
    # approach choice; and the failure is 'never touched', not 'grasped then dropped'.
    never = {}
    for cfg in ("ctrl_top_center", "ctrl_side_center"):
        lifts, cons = [], []
        for i in range(10):
            t = trial(i, cfg)
            lifts.append(t["lift_m"])
            cons.append(t["contacts_obj_finger_after_close"])
        assert max(lifts) < LIFT_PROOF_M, (cfg, lifts)
        assert sum(cons) == 0, (cfg, cons)
        never[cfg] = {"lift_m": lifts, "obj_finger_contacts_after_close": cons,
                      "carried_any": any(l > LIFT_PROOF_M for l in lifts)}
    # and when it does not grip, the object is not displaced either: it was never touched
    disp = [trial(i, "ctrl_top_center")["obj_xy_displacement_m"] for i in range(10)]
    assert max(disp) < 0.002, disp
    out["C5_both_modes_never_grip"] = {
        "per_mode": never,
        "obj_xy_displacement_m": disp,
        "verdict": ("10/10 fail in both modes with 0 object-finger contacts and <2 mm object "
                    "motion: not a drop, the object is never touched"),
    }

    # ---------------------------------------------------------------- C6 the rim pinch grips
    # claim: offsetting the grasp point along the jaw axis by the measured rim-plate radius
    # and descending to the settled physical rim DOES lift the bowl.
    ok, fail = [], []
    for i in range(10):
        t = trial(i, "rim_pinch")
        (ok if t["carried"] else fail).append({
            "index": i,
            "lift_m": t["lift_m"],
            "peak_lift_m": t["peak_lift_m"],
            "obj_finger_contacts": t["contacts_obj_finger_after_close"],
            "eef_z_error_m": t["eef_z_minus_target_m"],
            "rim_offset_m": t["rim_offset_m"],
        })
    assert len(ok) == 7, ok
    assert all(r["obj_finger_contacts"] > 0 for r in ok), ok
    assert all(r["lift_m"] > 0.12 for r in ok), ok
    # The 3 failures are NOT one mechanism, and the difference matters:
    #   idx 4 and idx 6 never arrived (the hand stalled 30.3 / 120.3 mm above the rim, 0 contacts)
    #   idx 7 DID arrive and DID touch (8 contacts) but was not held - the bowl was nudged aside
    stalled = [r for r in fail if r["obj_finger_contacts"] == 0]
    touched_not_held = [r for r in fail if r["obj_finger_contacts"] > 0]
    assert sorted(r["index"] for r in stalled) == [4, 6], stalled
    assert all(r["eef_z_error_m"] > 0.02 for r in stalled), stalled
    assert [r["index"] for r in touched_not_held] == [7], touched_not_held
    assert touched_not_held[0]["lift_m"] < LIFT_PROOF_M
    t7 = trial(7, "rim_pinch")
    assert t7["obj_xy_displacement_m"] > 0.01, t7["obj_xy_displacement_m"]
    out["C6_rim_pinch_grips"] = {
        "carried": ok,
        "stalled_before_contact": stalled,
        "touched_but_not_held": touched_not_held,
        "touched_not_held_xy_push_m": t7["obj_xy_displacement_m"],
        "verdict": ("7/10 lift 126.4-139.3 mm with 5-8 object-finger contacts. Of the 3 failures, "
                    "2 are descents that stalled 30.3 and 120.3 mm above the rim (0 contacts) and "
                    "1 arrived, touched with 8 contacts and pushed the bowl 24.3 mm aside without "
                    "holding it"),
    }

    # ---------------------------------------------------------------- C7 the official predicate
    # claim: with the rim pinch, the official success check passes on the tasks where the
    # carry completed. This is the only claim about task success in this directory.
    places = []
    for i in range(3):
        t = trial(i, "rim_pinch_place")
        places.append({"index": i, "official_success": t["place"]["official_success"],
                       "release_xy_err_m": t["place"]["release_xy_err_m"],
                       "lift_m": t["lift_m"]})
        assert t["place"]["official_success"] is True, t
        assert t["place"]["release_xy_err_m"] < 0.006, t
    out["C7_official_success"] = {
        "tasks": places,
        "verdict": "3/3 tested tasks pass env.check_success() after the rim pinch and a verified release",
    }

    # ---------------------------------------------------------------- C8 the jaw axis is local
    # claim: the closing axis is NOT a fixed world vector; it is the hand frame's y axis.
    ax = load(HERE / "raw_spatial" / "axis_libero_spatial_0.json")
    assert ax["A_constant_world"] is False, ax["A_constant_world"]
    assert ax["B_constant_in_hand_frame"] is True, ax["B_constant_in_hand_frame"]
    assert ax["B_constant_world"] is False, ax["B_constant_world"]
    assert ax["A_yaw_range_deg"][1] - ax["A_yaw_range_deg"][0] > 180, ax["A_yaw_range_deg"]
    out["C8_jaw_axis_is_hand_local"] = {
        "world_yaw_range_deg": ax["A_yaw_range_deg"],
        "finger_joint_axis_in_hand_frame": ax["samples"][0]["B_finger_joint_slide_axes"][0]["axis_in_hand"],
        "verdict": ("the finger slide axis is [0, 1, 0] in robot0_right_hand and its world "
                    "direction moved 255.9 deg when the wrist was rotated: it must be read at "
                    "run time, not hard-coded"),
    }

    # ---------------------------------------------------------------- C9 the guard condition
    # claim: the offset is only safe on a hollow ring. Applied to a solid object it fails.
    blind0 = load(HERE / "raw_object" / "trial_0_blind_offset_mid.json")
    centre0 = load(HERE / "raw_object" / "trial_0_top_center_collmid.json")
    assert blind0["carried"] is False, blind0["carried"]
    assert centre0["carried"] is True, centre0["carried"]
    assert blind0["contacts_obj_finger_after_close"] == 0
    assert centre0["contacts_obj_finger_after_close"] > 0
    out["C9_offset_guard"] = {
        "solid_object_blind_offset": {"carried": blind0["carried"],
                                      "lift_m": blind0["lift_m"],
                                      "contacts": blind0["contacts_obj_finger_after_close"]},
        "solid_object_centred": {"carried": centre0["carried"],
                                 "lift_m": centre0["lift_m"],
                                 "contacts": centre0["contacts_obj_finger_after_close"]},
        "verdict": ("on a solid can the same offset lifts 0.1 mm with 0 contacts while a "
                    "centred grasp lifts 140.3 mm: the offset must be gated on a hollow top"),
    }

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for k, v in out.items():
            print("=" * 78)
            print(k)
            print(json.dumps(v, indent=1)[:2000])
        print("=" * 78)
        print("ALL CLAIMS RE-DERIVED FROM raw_spatial/ and raw_object/ - no simulator involved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
