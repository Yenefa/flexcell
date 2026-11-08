#!/usr/bin/env python3
"""按官方命名规则打包创意组提交材料。

用法：
  python3 package.py --school "XX大学" --category 本科生 --team-id T001 [--project AgenticFlex] [--out DIR]

生成：创意组+河南+<学校>+<项目>+<类别>+<队伍编号>.zip
"""
import argparse, os, sys, zipfile

REQUIRED = ["项目创意计划书.md", "创意组_AgenticFlex_展示PPT.pptx"]
INCLUDE_DIRS = ["evidence"]
INCLUDE_FILES = ["项目创意计划书.md", "创意组_AgenticFlex_展示PPT.pptx", "PPT大纲.md",
                 "演示脚本.md", "答辩逐字稿.md", "现场操作卡.md", "提交清单.md",
                 "README.md", "RELEASE_NOTES.md"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--school", required=True)
    ap.add_argument("--category", required=True, choices=["研究生", "本科生", "高职高专生"])
    ap.add_argument("--team-id", required=True)
    ap.add_argument("--project", default="AgenticFlex")
    ap.add_argument("--out", default=".")
    ap.add_argument("--here", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    here = a.here
    missing = [f for f in REQUIRED if not os.path.isfile(os.path.join(here, f))]
    if missing:
        print("MISSING required files:", missing); return 2
    if "<" in open(os.path.join(here, "项目创意计划书.md"), encoding="utf-8").read():
        print("WARNING: 计划书仍含占位符 <...>，提交前请填写")
    name = f"创意组+河南+{a.school}+{a.project}+{a.category}+{a.team_id}.zip"
    out = os.path.join(a.out, name)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in INCLUDE_FILES:
            p = os.path.join(here, f)
            if os.path.isfile(p):
                z.write(p, arcname=f); n += 1
        for d in INCLUDE_DIRS:
            base = os.path.join(here, d)
            for root, _, files in os.walk(base):
                for fn in files:
                    fp = os.path.join(root, fn)
                    z.write(fp, arcname=os.path.relpath(fp, here)); n += 1
    print("OK", out)
    print("FILES", n, "SIZE", os.path.getsize(out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
