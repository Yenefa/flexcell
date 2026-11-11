"""Build the paired A-prime / B table from the archived verdict files.

Both arms are read from their recorded artefacts, not recomputed, so the table describes
what actually ran. The two source directories are named explicitly rather than discovered,
because a silent glob change would silently change the table.
"""
import json
import os

CI = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence"
A_DIR = os.path.join(CI, "baseline_a_v2_gated_20261111")
B_RUNS = [os.path.join(CI, "b_realexec_20261112"),
          os.path.join(CI, "b_realexec_diff5_20261112")]


def a_verdict(task):
    path = os.path.join(A_DIR, task, "verdict.json")
    if not os.path.exists(path):
        return None
    return json.load(open(path))


def b_rows():
    rows = []
    for run in B_RUNS:
        tsv = os.path.join(run, "b_results.tsv")
        if not os.path.exists(tsv):
            continue
        for i, line in enumerate(open(tsv).read().splitlines()):
            if i == 0 or not line.strip():
                continue
            parts = line.split("\t")
            rows.append(parts)
    return rows


print("%-22s %-9s %-9s %-7s %s" % ("instance", "A-prime", "B", "B-exec", "B false_success"))
both = a_pass = b_pass = 0
for parts in b_rows():
    task, stages, outcome, graded, passed, false_success = parts[:6]
    a = a_verdict(task)
    a_s = "MISSING" if a is None else ("PASS" if a["passed"] else "FAIL")
    b_s = "PASS" if passed == "True" else ("FAIL" if passed == "False" else "N/A")
    print("%-22s %-9s %-9s %-7s %s" % (task, a_s, b_s, outcome, false_success))
    both += 1
    a_pass += 1 if a_s == "PASS" else 0
    b_pass += 1 if b_s == "PASS" else 0
print()
print("instances both arms executed and graded: %d" % both)
print("A-prime passes: %d   B passes: %d" % (a_pass, b_pass))
print("False Success (B): %d" % sum(1 for p in b_rows() if p[5] == "True"))
