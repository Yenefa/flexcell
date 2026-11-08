#!/usr/bin/env python3
"""一键出包：填占位符 → 跑自检 → 打包。

用法：
  python3 make_release.py --team team.json [--out build]
"""
import argparse, json, os, re, shutil, subprocess, sys
HERE=os.path.dirname(os.path.abspath(__file__))
def run(args):
    p=subprocess.run(args, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "")+(p.stderr or "")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--out", default=os.path.join(HERE,"build"))
    a=ap.parse_args()
    team=json.load(open(a.team, encoding="utf-8"))
    for k in ("school","category","team_id"):
        if not team.get(k): print("MISSING team field:", k); return 2
    if team["category"] not in ("研究生","本科生","高职高专生"):
        print("category must be 研究生/本科生/高职高专生"); return 2
    build=a.out
    if os.path.isdir(build): shutil.rmtree(build)
    os.makedirs(build)
    for name in os.listdir(HERE):
        if name in ("build",): continue
        src=os.path.join(HERE,name)
        if os.path.isfile(src): shutil.copy2(src, os.path.join(build,name))
        elif os.path.isdir(src) and not name.startswith("build"): shutil.copytree(src, os.path.join(build,name))
    # fill plan placeholders
    plan_path=os.path.join(build,"项目创意计划书.md")
    plan=open(plan_path, encoding="utf-8").read()
    simple={
      "<学校名称>": team["school"], "<学校>": team["school"],
      "<研究生/本科生/高职高专生>": team["category"],
      "<研究生、本科生、高职高专生>": team["category"],
      "<队伍编号>": team["team_id"], "<项目名>": team.get("project","AgenticFlex"),
    }
    for k,v in simple.items(): plan=plan.replace(k,v)
    members=list(team.get("members") or []); advisors=list(team.get("advisors") or [])
    if members: plan=plan.replace("队长：<姓名>", "队长："+members[0])
    plan=plan.replace("成员：<姓名/姓名>", "成员："+"/".join(members[1:3]))
    plan=plan.replace("指导教师：<姓名/姓名>", "指导教师："+"/".join(advisors[:2]))
    names=members+advisors
    for n in names:
        plan=plan.replace("<姓名>", n, 1)
    open(plan_path,"w",encoding="utf-8").write(plan)
    left=len(re.findall(r"<[^>\s]{1,20}>", plan))
    print("remaining <placeholders> in plan:", left)
    # checks
    for script in ("check_consistency.py","score_check.py"):
        rc,out=run([sys.executable, os.path.join(build,script)])
        print(f"[{script}] rc={rc}"); print(out.strip())
        if rc: print("CHECK FAILED:", script); return 1
    # package
    rc,out=run([sys.executable, os.path.join(build,"package.py"),
                "--school",team["school"],"--category",team["category"],
                "--team-id",team["team_id"],"--project",team.get("project","AgenticFlex"),
                "--out",build,"--here",build])
    print(out.strip())
    if rc: return 1
    zips=[f for f in os.listdir(build) if f.endswith(".zip")]
    if zips:
        z=os.path.join(build,zips[0]); print("ZIP:", z, "SIZE:", os.path.getsize(z))
    print("DONE")
    return 0
if __name__=="__main__": sys.exit(main())
