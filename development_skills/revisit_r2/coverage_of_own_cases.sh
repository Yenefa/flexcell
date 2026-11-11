#!/usr/bin/env bash
# M5 -- how many of ros2-interface-preflight's OWN six cited cases does preflight.py catch?
set -u
DS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$DS" <<'PY'
import sys
DS = sys.argv[1]
sys.path.insert(0, DS + "/ros2-interface-preflight/scripts")
import preflight

class P:
    def __init__(self, **kw): self.__dict__.update(kw)

def good_stage():
    pose = P(header=P(frame_id="world"), pose=P(orientation=P(x=0.,y=0.,z=0.,w=1.)))
    return P(stage_id="s-0", object_name="probe", place_pose=pose)

def good_goal(**over):
    kw = dict(stages=[good_stage()], initial_objects=[P(object_name="probe")],
              position_tolerance_m=0.02, clearance_m=0.05)
    kw.update(over); return P(**kw)

def verdict(label, fn):
    try:
        caught = bool(fn())
    except Exception as exc:
        print("  %-44s CRASH   %s" % (label, type(exc).__name__)); return False
    print("  %-44s %s" % (label, "CAUGHT" if caught else "MISSED")); return caught

print("case 1  PushObject.Result.success     -> preflight.py never inspects PushObject.Result: MISSED")
print("case 2  direction_cosine vs _cos      -> preflight.py never inspects PushObject.Result: MISSED")
print("case 3  sample_gz_pose(node, ...)     -> preflight.py never inspects the signature:     MISSED")
n = 0
n += verdict("case 4  ObjectPosition.name",
             lambda: preflight.validate_goal(good_goal(initial_objects=[P(name="probe")])))
n += verdict("case 5  place_pose assigned a Point",
             lambda: preflight.validate_stage(P(stage_id="s-0", object_name="p", place_pose=P(x=0.,y=0.,z=0.))))
n += verdict("case 6  header.frame_id missing",
             lambda: preflight.validate_stage(P(stage_id="s-0", object_name="p",
                 place_pose=P(header=P(frame_id=""), pose=P(orientation=P(x=0.,y=0.,z=0.,w=1.))))))
print()
print("  CAUGHT %d / 6 cited cases" % n)
PY
