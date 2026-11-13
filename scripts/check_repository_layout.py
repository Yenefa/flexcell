#!/usr/bin/env python3
"""Check first-party ROS package boundaries without starting a robot/simulator."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def tracked_manifests(root):
    listed=subprocess.run(['git','-C',str(root),'ls-files','-z','--','**/package.xml'],
                          check=True,capture_output=True).stdout
    return [p.decode() for p in listed.split(b'\0') if p]


def audit(root,layout,manifests):
    root=Path(root);problems=[];packages=[];ignored=[]
    expected={str(Path(path)/'package.xml'):name for name,path in layout['ros_packages'].items()}
    for archive in layout['archive_roots']:
        if not (root/archive/'COLCON_IGNORE').is_file():
            problems.append('archive lacks COLCON_IGNORE: '+archive)
    for relative in sorted(manifests):
        path=root/relative
        parents=list(path.parent.parents)
        if any((directory/'COLCON_IGNORE').is_file() for directory in [path.parent,*parents]
               if directory==root or root in directory.parents):
            ignored.append(relative);continue
        try:name=ET.parse(path).getroot().findtext('name')
        except (OSError,ET.ParseError) as exc:
            problems.append('unreadable package '+relative+': '+str(exc));continue
        packages.append(dict(name=name,manifest=relative))
        if relative not in expected:problems.append('ROS package outside declared source: '+relative)
        elif expected[relative]!=name:problems.append('package name disagrees with registry: '+relative)
    discovered={p['manifest'] for p in packages}
    for path in sorted(set(expected)-discovered):problems.append('declared package not discoverable: '+path)
    for name,count in Counter(p['name'] for p in packages).items():
        if not name or count!=1:problems.append('missing/duplicate live package name: '+str(name))
    for module in layout['modules']:
        for path in module['paths']:
            if not (root/path).exists():problems.append('module path missing: '+path)
    return dict(passed=not problems,problems=problems,packages=packages,
                ignored_archive_packages=ignored,colcon_check='NOT_RUN')


def check_colcon(root,binary,expected_names):
    # An audit of a read-only checkout must not create log/build state there.
    with tempfile.TemporaryDirectory(prefix='flexcell-layout-') as logs:
        process=subprocess.run([binary,'--log-base',logs,'list','--base-paths',str(root),'--names-only'],
                               cwd=root,capture_output=True,text=True,timeout=90.)
    names=process.stdout.split()
    ok=(process.returncode==0 and Counter(names)==Counter(expected_names))
    return dict(passed=ok,exit_code=process.returncode,names=names,stderr=process.stderr.strip())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--colcon',help='Path/name of colcon; enables real root-workspace discovery')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args();root=args.root.resolve()
    layout=json.loads((root/'config/repository_layout.json').read_text())
    result=audit(root,layout,tracked_manifests(root))
    versions=json.loads((root/'config/version_baselines.json').read_text())
    for key,checkpoint in versions['checkpoints'].items():
        for field in ('executed_source_commit','evidence_commit'):
            if not re.fullmatch(r'[0-9a-f]{40}',checkpoint.get(field,'')):
                result['problems'].append('invalid checkpoint commit: '+key+'/'+field)
        if not (root/checkpoint['report']).is_file():
            result['problems'].append('checkpoint report missing: '+key)
    result['passed']=not result['problems']
    if args.colcon:
        actual=check_colcon(root,args.colcon,layout['ros_packages'])
        result['colcon_check']=actual
        if not actual['passed']:result['passed']=False;result['problems'].append('actual colcon package discovery differs from registry')
    if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
