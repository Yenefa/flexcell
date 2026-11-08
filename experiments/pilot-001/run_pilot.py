#!/usr/bin/env python3
"""P1.0 self-test: prove the measurement chain on five fixtures (no research claim)."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pilot import fixtures, runner
from pilot.manifest import load, verify_seal


def _run(manifest, tmp, name, arm, agent, template=None):
    tpl = template or fixtures.make_template(Path(tmp) / ("tpl-" + name))
    if template is None:
        tpl = fixtures.make_template(Path(tmp) / ("tpl-" + name))
    return runner.run_one(manifest, arm, agent, tpl, Path(tmp) / name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=tempfile.mkdtemp(prefix="pilot001-"))
    ap.add_argument("--manifest", default=str(HERE / "manifest.json"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = load(a.manifest)
    checks = []

    def check(name, cond, detail):
        checks.append({"name": name, "ok": bool(cond), "detail": detail})

    # 1 normal pass
    r1 = runner.run_one(manifest, "B", fixtures.agent_fix_and_execute(),
                        fixtures.make_template(out / "tpl-normal"), out / "normal_pass")
    check("normal_pass", r1["success"] and r1["first_pass"] and r1["evidence"]["completeness"] == 1.0, r1)

    # 2 task fail
    r2 = runner.run_one(manifest, "B", fixtures.agent_wrong(),
                        fixtures.make_template(out / "tpl-fail"), out / "task_fail")
    check("task_fail", (not r2["success"]) and (not r2["false_success"]), r2)

    # 3 false success
    r3 = runner.run_one(manifest, "B", fixtures.agent_false_success(),
                        fixtures.make_template(out / "tpl-false"), out / "false_success")
    check("false_success", (not r3["success"]) and r3["false_success"], r3)

    # 4 protected write refused
    bad_agent = fixtures.ScriptedAgent([("write_file", ("gate/acceptance.py", "print(1)"))])
    r4 = runner.run_one(manifest, "B", bad_agent,
                        fixtures.make_template(out / "tpl-prot"), out / "protected_changed")
    check("protected_changed", bool(r4["violation"]), r4)

    # 5 missing evidence (A arm: no execution -> episode/telemetry absent)
    r5 = runner.run_one(manifest, "A", fixtures.agent_fix_checks_only(),
                        fixtures.make_template(out / "tpl-miss"), out / "missing_evidence")
    check("missing_evidence", r5["success"] and r5["evidence"]["completeness"] < 0.75, r5)

    report = {"out": str(out), "checks": checks,
              "passed": sum(1 for c in checks if c["ok"]), "total": len(checks)}
    (out / "p1.0-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"])
    print("P1.0_SELF_TEST_%s %d/%d" % ("PASS" if report["passed"] == report["total"] else "FAIL",
                                      report["passed"], report["total"]))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
