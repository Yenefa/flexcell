#!/usr/bin/env python3
"""Enforce and VERIFY held-out isolation: turn "must not read" into "cannot read".

WHY THIS FILE EXISTS
--------------------
benchmark/README.md and docs/TASK_BENCHMARK.md section 4 said the agent must not read
benchmark/held_out/ or benchmark/evaluators/. That was a promise. The agent process runs
as uid 1001 and the checkout is a 9p/drvfs mount under /mnt/c, so a POSIX mode change
actually bites - this script applies that change and then TESTS it.

THE LEAK THIS CLOSES (measured, not theorised)
----------------------------------------------
Sealing the answers into /etc/evobot/sealed (root:root 700) was necessary but NOT
sufficient. The held-out public tasks are a deterministic function of
(template, seed), and benchmark/generators/ - which holds that function - was
world-readable. As uid 1001, in under a second:

    import unseen_tasks as U
    for t in sorted(U.TEMPLATES):
        for seed in range(7000, 7010):
            if U.generate(t, seed, "held_out")["instruction"] == public["instruction"]:
                print(U.generate(t, seed, "held_out")["expected_goal"])

recovered the sealed answer for HO-fd5737f932db (template T12_triple_revisit, seed 7009)
with no privilege at all. A sealed answer plus a readable oracle is an open book, so
benchmark/generators/ is part of the isolation surface and is locked here.

WHAT IS LOCKED, AND FOR WHOM
----------------------------
    benchmark/held_out/     the held-out instance set (enumerating it leaks the set)
    benchmark/evaluators/   the grading logic
    benchmark/generators/   the answer ORACLE (the reconstruction path above)

    owner root, group ros, dir 0750, files 0640.

    agent (uid 1001, groups cleared by setpriv --clear-groups) -> EACCES
    evaluator / runner (root, or ros in group ros)             -> normal access

uid 1001 has no passwd entry and no supplementary groups, so it matches neither the
owner nor the group and falls to "other", which has no bits at all. ros is a real group
(gid 1000) so the runner and the offline tests keep working unchanged.

WHY NOT 0700 root:root: that also locks out the evaluator and the 283-test offline
suite, which run as ros. The requirement is bidirectional - the agent must lose access
AND the evaluator must keep grading - so the group bit has to stay.

WHAT THIS CANNOT DO (stated plainly; see residual_risks in the output)
---------------------------------------------------------------------
1. It is OS permission isolation, not a kernel namespace. Anything that runs as root
   defeats it by construction.
2. WSL interop is open to uid 1001. The agent can execute /mnt/c/Windows/System32/
   cmd.exe and read the same file through the Windows API, where these POSIX bits do
   not apply. This is MEASURED by the verifier and reported, not hidden. It cannot be
   closed from inside a running distro without restarting WSL with interop disabled,
   which would break the rest of the host.
3. It cannot undo already-published answers. Historical v0.1 held-out specs were
   committed with expected_goal in clear text and remain in git history.

USAGE
-----
    sudo -n python3 scripts/heldout_isolation.py apply    [--root WT]
    sudo -n python3 scripts/heldout_isolation.py verify   [--root WT] [--json]
    sudo -n python3 scripts/heldout_isolation.py restore  [--root WT]   # for editing
    sudo -n python3 scripts/heldout_isolation.py stage-public <task.json> <run_dir>

Exit codes: 0 = enforced and verified, 1 = verification failed, 2 = environment error.
"""
import argparse
import json
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT_UID = 1001
AGENT_GID = 1001
EVAL_GROUP = "ros"

# Everything under these prefixes is held-out surface. Prefixes, not single dirs,
# because locking benchmark/held_out/ alone left the oracle readable.
LOCKED_PREFIXES = ("benchmark/held_out", "benchmark/evaluators", "benchmark/generators")

# Positive control: the agent is SUPPOSED to read the train split. If this ever stops
# being readable the verifier must not report success - that would mean we locked too
# much and broke the agent instead of isolating it.
CONTROL_PREFIX = "benchmark/tasks/train"

DIR_MODE = 0o750
FILE_MODE = 0o640


# --------------------------------------------------------------------------- helpers
def _wt(root=None):
    if root:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[1]


def _ros_gid():
    try:
        return pwd.getpwnam(EVAL_GROUP).pw_gid
    except KeyError:
        return None


def _can_sudo():
    try:
        r = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _as_agent(cmd, timeout=120):
    """Run a command exactly the way the runner launches the agent."""
    return subprocess.run(
        ["sudo", "-n", "setpriv", "--reuid=%d" % AGENT_UID, "--regid=%d" % AGENT_GID,
         "--clear-groups"] + cmd,
        capture_output=True, text=True, timeout=timeout)


def _as_root(cmd, timeout=120):
    return subprocess.run(["sudo", "-n"] + cmd, capture_output=True, text=True,
                          timeout=timeout)


def _locked_paths(wt):
    out = []
    for prefix in LOCKED_PREFIXES:
        top = wt / prefix
        if not top.exists():
            continue
        out.append(top)
        for dirpath, dirnames, filenames in os.walk(top):
            for name in dirnames + filenames:
                out.append(Path(dirpath) / name)
    return out


# ----------------------------------------------------------------------------- apply
def apply_policy(wt, quiet=False):
    """chown root:<eval group> + 0750 dirs / 0640 files under every locked prefix."""
    gid = _ros_gid()
    if gid is None:
        raise SystemExit("environment error: group %r does not exist" % EVAL_GROUP)
    changed = 0
    for path in _locked_paths(wt):
        try:
            st = path.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            continue
        mode = DIR_MODE if stat.S_ISDIR(st.st_mode) else FILE_MODE
        # chown first: chown clears setuid/setgid bits and can change the mode we set.
        if st.st_uid != 0 or st.st_gid != gid:
            os.chown(path, 0, gid)
        if stat.S_IMODE(st.st_mode) != mode:
            os.chmod(path, mode)
        changed += 1
    if not quiet:
        print(json.dumps({"applied": True, "paths": changed,
                          "owner": "root:%s" % EVAL_GROUP,
                          "dir_mode": oct(DIR_MODE), "file_mode": oct(FILE_MODE),
                          "locked_prefixes": list(LOCKED_PREFIXES)}, indent=2))
    return changed


def restore_policy(wt):
    """Put the tree back to world-readable so the repo can be edited normally.

    This is the MUTATION path used to prove the verifier can fail. It is deliberately
    a supported command rather than a one-off chmod, so the mutation is reproducible.
    """
    changed = 0
    for path in _locked_paths(wt):
        try:
            st = path.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            continue
        mode = 0o755 if stat.S_ISDIR(st.st_mode) else 0o644
        if stat.S_IMODE(st.st_mode) != mode:
            os.chmod(path, mode)
            changed += 1
    print(json.dumps({"restored": True, "paths": changed,
                      "note": "world-readable again - this is the MUTATION state"},
                     indent=2))
    return changed


# ------------------------------------------------------------------------ static check
def static_check(wt, expect_owner=True, expected_uid=0, expected_gid=None):
    """Mode-only check. Pure enough to run against a temp tree in a unit test.

    expected_uid/expected_gid are parameters rather than hardcoded 0/<ros gid> so the
    ownership rule can be exercised deterministically: a test running as root would
    otherwise see its own files as correctly owned and pass vacuously, which is the
    same class of bug as a verifier that cannot fail.
    """
    gid = _ros_gid() if expected_gid is None else expected_gid
    violations = []
    for path in _locked_paths(wt):
        try:
            st = path.lstat()
        except OSError as exc:
            violations.append({"path": str(path), "why": "lstat failed: %s" % exc})
            continue
        if stat.S_ISLNK(st.st_mode):
            continue
        rel = str(path.relative_to(wt))
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o007:
            violations.append({"path": rel, "why": "world-accessible",
                               "mode": oct(mode)})
        if mode & 0o020:
            violations.append({"path": rel, "why": "group-writable",
                               "mode": oct(mode)})
        if stat.S_ISDIR(st.st_mode) and not mode & 0o010:
            violations.append({"path": rel, "why": "no group traverse",
                               "mode": oct(mode)})
        if expect_owner:
            if st.st_uid != expected_uid:
                violations.append({"path": rel, "why": "not owned by root",
                                   "uid": st.st_uid})
            if gid is not None and st.st_gid != gid:
                violations.append({"path": rel, "why": "not group %s" % EVAL_GROUP,
                                   "gid": st.st_gid})
    return violations


# -------------------------------------------------------------------------- live probes
def probe_agent_blocked(wt):
    """The agent must be unable to enumerate or read the locked tree."""
    checks = []
    for prefix in LOCKED_PREFIXES:
        top = wt / prefix
        if not top.exists():
            continue
        r = _as_agent(["ls", str(top)])
        checks.append({
            "probe": "list:" + prefix,
            "expected": "denied",
            "exit": r.returncode,
            "ok": r.returncode != 0,
            "stderr": (r.stderr or "").strip().splitlines()[-1:] or [""],
        })
        # a specific file, not just the directory bit
        sample = None
        for dirpath, _dirnames, filenames in os.walk(top):
            if filenames:
                sample = Path(dirpath) / sorted(filenames)[0]
                break
        if sample is not None:
            r = _as_agent(["cat", str(sample)])
            checks.append({
                "probe": "read:" + str(sample.relative_to(wt)),
                "expected": "denied",
                "exit": r.returncode,
                "ok": r.returncode != 0,
                "stderr": (r.stderr or "").strip().splitlines()[-1:] or [""],
            })
    return checks


def probe_control_still_readable(wt):
    """The agent must STILL be able to read the train split it is supposed to use."""
    top = wt / CONTROL_PREFIX
    if not top.exists():
        return [{"probe": "control:" + CONTROL_PREFIX, "ok": True,
                 "note": "control path absent, not scored"}]
    sample = None
    for dirpath, _d, filenames in os.walk(top):
        if filenames:
            sample = Path(dirpath) / sorted(filenames)[0]
            break
    if sample is None:
        return [{"probe": "control:" + CONTROL_PREFIX, "ok": True, "note": "no files"}]
    r = _as_agent(["cat", str(sample)])
    return [{"probe": "control:read:" + str(sample.relative_to(wt)),
             "expected": "allowed", "exit": r.returncode,
             "ok": r.returncode == 0,
             "stderr": (r.stderr or "").strip().splitlines()[-1:] or [""]}]


def probe_reconstruction(wt):
    """The decisive one: with a public task in hand, can the agent rebuild the answer?

    This reproduces the leak that made the first sealing round insufficient. It must
    FAIL at the import. A partially-blocked state (import works, this seed happens not
    to match) is still a failure, because the oracle is what is being closed.
    """
    publics = sorted((wt / "benchmark" / "held_out" / "unseen_public").glob("*.json"))
    if not publics:
        return [{"probe": "reconstruction", "ok": True,
                 "note": "no unseen_public set present, not scored"}]

    tmp = Path(tempfile.mkdtemp(prefix="evobot-isolation-"))
    try:
        # the verifier is privileged: it may copy one public task somewhere the agent
        # can read, so the probe cannot be dodged by "the agent could not open its own
        # task file". Hand the agent its input and STILL deny the answer.
        staged = tmp / "public_task.json"
        shutil.copyfile(publics[0], staged)
        os.chmod(tmp, 0o755)
        os.chmod(staged, 0o644)

        attack = tmp / "reconstruct.py"
        attack.write_text(
            "import json, sys\n"
            "W = sys.argv[1]\n"
            "sys.path.insert(0, W + '/benchmark/generators')\n"
            "import unseen_tasks as U\n"   # <- the import that must be denied
            "pub = json.load(open(sys.argv[2]))\n"
            "for t in sorted(U.TEMPLATES):\n"
            "    for seed in range(7000, 7010):\n"
            "        try:\n"
            "            s = U.generate(t, seed, 'held_out')\n"
            "        except Exception:\n"
            "            continue\n"
            "        if s.get('instruction') == pub.get('instruction'):\n"
            "            print('RECOVERED ' + t + ' ' + str(seed))\n"
            "            print(json.dumps(s['expected_goal']))\n"
            "            sys.exit(0)\n"
            "print('NO_MATCH')\n"
            "sys.exit(3)\n", encoding="utf-8")
        os.chmod(attack, 0o644)

        r = _as_agent([sys.executable, str(attack), str(wt), str(staged)], timeout=180)
        recovered = "RECOVERED" in (r.stdout or "")
        return [{
            "probe": "reconstruction:" + publics[0].name,
            "expected": "denied at import",
            "exit": r.returncode,
            "ok": (r.returncode != 0) and not recovered,
            "recovered_answer": recovered,
            "stderr": (r.stderr or "").strip().splitlines()[-1:] or [""],
        }]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe_sealed_blocked():
    """The sealed answers themselves must stay unreadable by the agent."""
    sealed = Path("/etc/evobot/sealed")
    if not sealed.is_dir():
        return [{"probe": "sealed", "ok": True, "note": "no sealed dir, not scored"}]
    r = _as_agent(["sh", "-c", "cat /etc/evobot/sealed/*.json >/dev/null 2>&1"])
    return [{"probe": "sealed:read-all", "expected": "denied", "exit": r.returncode,
             "ok": r.returncode != 0}]


# ------------------------------------------------------------- evaluator-side (the other direction)
def _perfect_and_wrong_observations(spec, sealed):
    """Build one observation that satisfies the goal and one that does not.

    This is a PLUMBING probe of the grading path, not a benchmark result: it proves the
    evaluator can still read the answer and return a real verdict after the agent was
    locked out. It is never reported as a task outcome.
    """
    goal = sealed.get("expected_goal") or {}
    rest = {o["name"]: list(o["initial_pose"]) for o in spec["objects"]}
    zones = {z["name"]: z for z in spec["zones"]}

    good = {n: list(rest[n]) for n in rest}
    for name, zone_name in (goal.get("placement") or {}).items():
        if zone_name in zones:
            good[name] = list(zones[zone_name]["pose"])
    good_obs = {
        "objects": good,
        "move_sequence": list(goal.get("order") or []),
        "visits": {k: list(v) for k, v in (goal.get("visit_sequence") or {}).items()},
        "agent_claimed_success": False,
    }
    for k, v in (goal.get("visit") or {}).items():
        good_obs["visits"].setdefault(k, list(v))
    if not good_obs["move_sequence"] and goal.get("placement"):
        good_obs["move_sequence"] = sorted(goal["placement"])

    bad = {n: list(rest[n]) for n in rest}
    bad_obs = {"objects": bad, "move_sequence": [], "visits": {},
               "agent_claimed_success": False}
    return good_obs, bad_obs


def probe_evaluator_can_grade(wt):
    """Both directions: the evaluator must still say pass on a pass and fail on a fail."""
    pubdir = wt / "benchmark" / "held_out" / "unseen_public"
    publics = sorted(pubdir.glob("*.json"))
    sealed_dir = Path("/etc/evobot/sealed")
    if not publics or not sealed_dir.is_dir():
        return [{"probe": "evaluator", "ok": True,
                 "note": "no public/sealed pair present, not scored"}]

    target = None
    sealed = None
    for p in publics:
        cand = sealed_dir / (json.loads(p.read_text(encoding="utf-8"))["task_id"] + ".json")
        r = _as_root(["test", "-f", str(cand)])
        if r.returncode == 0:
            target, sealed_path = p, cand
            sealed = json.loads(_as_root(["cat", str(sealed_path)]).stdout)
            break
    if target is None:
        return [{"probe": "evaluator", "ok": True,
                 "note": "no public task has a sealed answer here, not scored"}]

    spec = json.loads(target.read_text(encoding="utf-8"))
    good_obs, bad_obs = _perfect_and_wrong_observations(spec, sealed)
    evaluator = wt / "benchmark" / "evaluators" / "sealed_evaluate.py"

    tmp = Path(tempfile.mkdtemp(prefix="evobot-evalprobe-"))
    results = []
    try:
        for label, obs, want in (("pass", good_obs, True), ("fail", bad_obs, False)):
            f = tmp / (label + ".json")
            f.write_text(json.dumps(obs), encoding="utf-8")
            os.chmod(f, 0o644)
            r = _as_root([sys.executable, str(evaluator),
                          "--public", str(target), "--observation", str(f)])
            try:
                verdict = json.loads(r.stdout)
            except Exception:
                results.append({"probe": "evaluator:" + label, "ok": False,
                                "exit": r.returncode,
                                "why": "evaluator produced no verdict",
                                "stderr": (r.stderr or "").strip().splitlines()[-2:]})
                continue
            results.append({
                "probe": "evaluator:" + label,
                "expected_passed": want,
                "observed_passed": verdict.get("passed"),
                "clauses": len(verdict.get("clauses") or []),
                "ok": verdict.get("passed") is want and bool(verdict.get("clauses")),
            })
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return results


# ------------------------------------------------------------------- residual risk probe
def measure_residual_risks(wt):
    """Measure the bypasses that POSIX modes do not close. Reported, never hidden."""
    risks = []

    # pick a real file inside the locked tree; a directory cannot be "read" and
    # would make the root probe silently report "closed" when it is not.
    sample = None
    for prefix in LOCKED_PREFIXES:
        top = wt / prefix
        if not top.exists():
            continue
        for dirpath, _d, filenames in os.walk(top):
            if filenames:
                sample = Path(dirpath) / sorted(filenames)[0]
                break
        if sample:
            break

    # 1. root bypass - by definition it works; we only record that the mechanism
    #    assumes the agent is NOT root.
    if sample is not None:
        r = _as_root(["cat", str(sample)])
        risks.append({
            "risk": "root process",
            "closed": False,
            "measured": r.returncode == 0 and r.stdout.strip() != "",
            "detail": "any process running as root reads the locked tree; the mechanism "
                      "assumes the agent is launched as uid 1001 with no sudo",
        })

    # 2. WSL interop - the real hole. uid 1001 can run a Windows binary and read the
    #    same file through the Win32 API, where POSIX modes do not apply.
    if sample is not None:
        win = "/mnt/c/Windows/System32/cmd.exe"
        r = _as_agent([win, "/c", "type",
                       subprocess.run(["wslpath", "-w", str(sample)],
                                      capture_output=True, text=True).stdout.strip()])
        leaked = r.returncode == 0 and r.stdout.strip() != ""
        risks.append({
            "risk": "WSL interop (Windows binary reads the file)",
            "closed": False,
            "measured": leaked,
            "detail": "uid 1001 can execute cmd.exe and read the same file through the "
                      "Win32 API; POSIX bits do not apply there. Cannot be closed from "
                      "inside a running distro without restarting WSL with interop "
                      "disabled, which would break the rest of the host.",
            "sample": str(sample.relative_to(wt)),
        })
    return risks


# ------------------------------------------------------------------------------- verify
def verify(wt, as_json=False, expect_owner=True):
    """Run every probe and gate on all of them.

    expect_owner=False exists so the gate can be driven against a temporary tree the
    caller does not own (the offline tests). Production always passes True: a tree that
    is merely chmod'ed but still owned by the agent's uid is not isolated, because the
    owner can chmod it back.
    """
    report = {"root": str(wt), "locked_prefixes": list(LOCKED_PREFIXES),
              "agent_uid": AGENT_UID, "eval_group": EVAL_GROUP,
              "expected": {"owner": "root:%s" % EVAL_GROUP,
                           "dir_mode": oct(DIR_MODE), "file_mode": oct(FILE_MODE)}}

    static = static_check(wt, expect_owner=expect_owner)
    report["static"] = {"ok": not static, "violations": static[:20],
                        "violation_count": len(static)}

    if not _can_sudo():
        report["verdict"] = "UNVERIFIED"
        report["why"] = "no passwordless sudo: cannot drop to uid 1001 or run the evaluator"
        _emit(report, as_json)
        return 2

    agent = probe_agent_blocked(wt)
    control = probe_control_still_readable(wt)
    recon = probe_reconstruction(wt)
    sealed = probe_sealed_blocked()
    evaluator = probe_evaluator_can_grade(wt)

    report["agent_blocked"] = agent
    report["agent_control"] = control
    report["reconstruction"] = recon
    report["sealed"] = sealed
    report["evaluator_side"] = evaluator
    report["residual_risks"] = measure_residual_risks(wt)

    gate = (not static) and all(c["ok"] for c in agent + control + recon + sealed + evaluator)
    report["gate"] = gate
    report["verdict"] = ("HELDOUT_ISOLATION_ENFORCED" if gate
                         else "HELDOUT_ISOLATION_NOT_ENFORCED")
    report["claim_level"] = ("Simulation-free OS-level isolation, verified by probe. "
                            "Not a kernel namespace; not a claim of absolute safety.")
    _emit(report, as_json)
    return 0 if gate else 1


def _emit(report, as_json):
    if as_json:
        print(json.dumps(report, indent=2))
        return
    print("=" * 72)
    print("held-out isolation verification")
    print("=" * 72)
    print("static modes      :", "OK" if report["static"]["ok"] else
          "FAIL (%d violations)" % report["static"]["violation_count"])
    for v in report["static"]["violations"][:5]:
        print("    -", v)
    for group in ("agent_blocked", "agent_control", "reconstruction", "sealed",
                  "evaluator_side"):
        for c in report.get(group, []):
            print("%-18s: %-4s %s" % (group, "OK" if c["ok"] else "FAIL",
                                      {k: v for k, v in c.items()
                                       if k in ("probe", "exit", "stderr",
                                                "expected_passed", "observed_passed",
                                                "recovered_answer")}))
    print("-" * 72)
    print("RESIDUAL RISKS (not closed by this mechanism, measured not assumed):")
    for r in report.get("residual_risks", []):
        print("  [%s] %s" % ("BYPASSES" if r.get("measured") and not r.get("closed")
                             else "ok", r["risk"]))
    print("-" * 72)
    print("VERDICT:", report["verdict"])
    print(report.get("claim_level", ""))


# ------------------------------------------------------------------------- stage-public
def stage_public(wt, task_path, run_dir):
    """Copy ONE public task into the run dir so the agent can read its own input.

    benchmark/held_out/ is locked, so the runner cannot hand the agent a path inside it.
    The copy carries only the public fields; the sealed answer stays in /etc/evobot.
    """
    src = Path(task_path)
    spec = json.loads(src.read_text(encoding="utf-8"))
    banned = [k for k in ("expected_goal", "constraints", "template_id", "random_seed",
                          "instance_sha256") if k in spec]
    if banned:
        raise SystemExit("refusing to stage a task carrying answer fields: %r" % banned)
    out = Path(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "public_task.json"
    dest.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    os.chmod(out, 0o777)
    os.chmod(dest, 0o644)
    print(str(dest))
    return 0


# --------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["apply", "verify", "restore", "stage-public",
                                       "static-check"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--root", default=None)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    wt = _wt(ns.root)

    if ns.action == "apply":
        apply_policy(wt)
        return 0
    if ns.action == "restore":
        restore_policy(wt)
        return 0
    if ns.action == "static-check":
        v = static_check(wt)
        print(json.dumps({"ok": not v, "violations": v[:20],
                          "violation_count": len(v)}, indent=2))
        return 0 if not v else 1
    if ns.action == "verify":
        return verify(wt, as_json=ns.json)
    if ns.action == "stage-public":
        if len(ns.args) != 2:
            print("usage: stage-public <task.json> <run_dir>", file=sys.stderr)
            return 2
        return stage_public(wt, ns.args[0], ns.args[1])
    return 2


if __name__ == "__main__":
    sys.exit(main())
