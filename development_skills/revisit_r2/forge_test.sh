#!/usr/bin/env bash
# N2b -- the forgery measurement behind the self-declared-reference finding.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
python3 - <<'PY'
import copy, json, sys
WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, WT)
from benchmark.evidence.verify import verify
from benchmark.evidence import fixtures

B = WT + "/setup/acceptance/evobot_t08_trajectory_verifier_20261112/evidence/evidence_bundle.json"
base = json.load(open(B))
term = {"passed": True}; lim = fixtures.limits()
REST = float(base["task"]["rest_height_m"])
# sample layout: [sim_step, sim_ns, wall_ns, x, y, z, qx, qy, qz, qw]  (z at index 5)

def run(tag, mutate):
    b = copy.deepcopy(base); mutate(b)
    r = verify(b, term, lim)
    g = {x.get("gate"): x.get("ok") for x in (r.get("gates") or [])}
    failed = sorted(k for k, v in g.items() if v is False)
    print("  %-52s passed=%-5s failed=%s" % (tag, r.get("passed"), failed or "NONE"))
    return r.get("passed"), failed

def carry(b):
    s = b["objects"]["target_box_a"]["samples"]; n = len(s)
    lo, hi = int(n*0.30), int(n*0.70)
    for i in range(lo, hi):
        t = (i-lo)/float(hi-lo)
        s[i][5] = REST + 0.060*(1.0 if 0.2 < t < 0.8 else 0.0)

print("BASELINE")
run("honest archived bundle", lambda b: None)
print()
print("FORGERY ATTEMPTS")
run("F1 carry, rest honest", carry)
def f2(b):
    carry(b); b["task"]["rest_height_m"] = REST + 0.060
run("F2 carry + rest_height_m re-declared to apex", f2)
def f5(b):
    b["contacts"]["pusher_links"] = ["made_up_link"]
run("F5 pusher_links invented", f5)
def f7(b):
    b["manifest"]["bundle_sha256"] = "0"*64
run("F7 manifest.bundle_sha256 zeroed", f7)
print()
print("READING:")
print("  F2: no_lift is defeated, table_support still catches it -> redundancy holds.")
print("  F7: zeroing the bundle digest changes NOTHING -> no gate verifies the seal.")
print("      This is a separate, measured hole from the self-declared-reference pattern.")
PY
