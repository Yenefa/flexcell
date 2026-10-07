#!/usr/bin/env python3
"""Inspect a declared plan or persisted checkpoint; never connect to ROS or infer."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.composite_prepare import checkpoint_report, plan_report
from flexcell_skills.contracts.receipt_json import loads


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path)
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--plan',required=True,type=Path)
    p=sub.add_parser('checkpoint');p.add_argument('--run-id',required=True);p.add_argument('--fingerprint',required=True)
    p.add_argument('--composites',type=Path,default=Path.home()/'.ros/flexcell/composites')
    p.add_argument('--episodes',type=Path,default=Path.home()/'.ros/flexcell/episodes')
    args=ap.parse_args()
    try:
        result=plan_report(loads(args.plan.read_text())) if args.command=='plan' else checkpoint_report(args.composites,args.run_id,args.fingerprint,args.episodes)
    except Exception as exc:result=dict(ok=False,dispatch_authorized=False,error=type(exc).__name__+': '+str(exc))
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('x') as f:f.write(encoded)
    print(encoded,end='');return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
