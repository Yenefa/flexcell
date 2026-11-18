#!/usr/bin/env python3
"""Check first-party ROS package boundaries without starting a robot/simulator."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_COLCON_TIMEOUT=90.


class UsageError(Exception):
    """Bad input or bad configuration: exit 2, never a partial report."""


def load_json(path):
    try:
        raw=Path(path).read_text(encoding='utf-8')
    except (OSError,UnicodeDecodeError) as exc:
        raise UsageError('cannot read config %s: %s'%(path,exc))
    try:
        data=json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError('config %s is not valid JSON: %s'%(path,exc))
    if not isinstance(data,dict):
        raise UsageError('config %s must be a JSON object'%path)
    return data


def load_layout(path):
    layout=load_json(path)
    packages=layout.get('ros_packages')
    if not isinstance(packages,dict) or not packages:
        raise UsageError('%s needs a non-empty ros_packages object'%path)
    for name,relative in packages.items():
        if not name or not isinstance(relative,str) or not relative:
            raise UsageError('%s has an invalid ros_packages entry: %r'%(path,name))
    for key in ('archive_roots','modules'):
        if not isinstance(layout.get(key),list):
            raise UsageError('%s needs a %s list'%(path,key))
    for index,module in enumerate(layout['modules']):
        if not isinstance(module,dict) or not isinstance(module.get('paths'),list) \
                or not module['paths']:
            raise UsageError('%s modules[%d] needs a non-empty paths list'%(path,index))
    return layout


def load_baselines(path):
    baselines=load_json(path)
    checkpoints=baselines.get('checkpoints')
    if not isinstance(checkpoints,dict):
        raise UsageError('%s needs a checkpoints object'%path)
    for key,checkpoint in checkpoints.items():
        if not isinstance(checkpoint,dict) or not isinstance(checkpoint.get('report'),str) \
                or not checkpoint['report']:
            raise UsageError('%s checkpoint %s needs a report path'%(path,key))
    return baselines


def tracked_manifests(root):
    # Container checkouts can have a different filesystem owner. Trust only
    # this explicitly selected checkout for this read, never all directories.
    process=subprocess.run(['git','-c','safe.directory='+str(root),'-C',str(root),
                            'ls-files','-z','--','**/package.xml'],capture_output=True)
    if process.returncode:
        raise RuntimeError('git ls-files failed: '+process.stderr.decode(errors='replace').strip())
    return [p.decode() for p in process.stdout.split(b'\0') if p]


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


def check_colcon(root,binary,expected_names,timeout=DEFAULT_COLCON_TIMEOUT):
    # An audit of a read-only checkout must not create log/build state there.
    try:
        with tempfile.TemporaryDirectory(prefix='flexcell-layout-') as logs:
            process=subprocess.run([binary,'--log-base',logs,'list','--base-paths',str(root),'--names-only'],
                                   cwd=root,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(passed=False,exit_code=None,names=[],stderr='',
                    error='colcon timed out after %gs'%timeout)
    except OSError as exc:
        return dict(passed=False,exit_code=None,names=[],stderr='',
                    error='cannot run colcon %s: %s'%(binary,exc))
    names=process.stdout.split()
    ok=(process.returncode==0 and Counter(names)==Counter(list(expected_names)))
    return dict(passed=ok,exit_code=process.returncode,names=names,stderr=process.stderr.strip())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--colcon',help='Path/name of colcon; enables real root-workspace discovery')
    parser.add_argument('--colcon-timeout',type=float,default=DEFAULT_COLCON_TIMEOUT,
                        help='seconds before colcon discovery is reported as failed (default: 90)')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args(argv);root=args.root.resolve()
    if args.colcon_timeout<=0:
        print('ERROR: --colcon-timeout must be positive',file=sys.stderr)
        return 2
    try:
        layout=load_layout(root/'config/repository_layout.json')
        versions=load_baselines(root/'config/version_baselines.json')
        result=audit(root,layout,tracked_manifests(root))
    except (UsageError,RuntimeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 2
    for key,checkpoint in versions['checkpoints'].items():
        for field in ('executed_source_commit','evidence_commit'):
            if not re.fullmatch(r'[0-9a-f]{40}',checkpoint.get(field,'')):
                result['problems'].append('invalid checkpoint commit: '+key+'/'+field)
        if not (root/checkpoint['report']).is_file():
            result['problems'].append('checkpoint report missing: '+key)
    result['passed']=not result['problems']
    if args.colcon:
        actual=check_colcon(root,args.colcon,layout['ros_packages'],args.colcon_timeout)
        result['colcon_check']=actual
        if not actual['passed']:result['passed']=False;result['problems'].append('actual colcon package discovery differs from registry')
    encoded=json.dumps(result,indent=2)+'\n'
    if args.out:
        try:
            args.out.write_text(encoded)
        except OSError as exc:
            print('ERROR: cannot write %s: %s'%(args.out,exc),file=sys.stderr)
            return 2
    print(encoded,end='')
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
