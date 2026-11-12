"""Incremental native-file replay, including bootstrap and two-step read skew.

Recorded data and a simulated replay clock test acquisition logic only. This is
not a new physical run or evidence of real-time scheduling reliability.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src/flexcell/flexcell_skills'))
from flexcell_skills import contact_trace


def replay(directory,module):
    physics=[json.loads(line) for line in (directory/'physics.jsonl').open()]
    contacts=[json.loads(line) for line in (directory/'contacts.jsonl').open()]
    clock=[0];wall=[0];old=module.time.monotonic_ns;checks=0;failed=0;offset=0
    try:
        module.time.monotonic_ns=lambda:wall[0]
        with tempfile.TemporaryDirectory(prefix='contact_replay_') as scratch:
            root=Path(scratch);native=module.NativeContact(root,'target_box_a',{'target_box_b':[.2,-.18,.0175]})
            native.sim_clock=lambda:clock[0]
            for start in range(0,len(physics),100):
                chunk=physics[start:start+100];last=chunk[-1]
                with (root/'physics.jsonl').open('a') as stream:
                    stream.writelines(json.dumps(row)+'\n' for row in chunk)
                # Exercise the real sequential-reader counterexample: contacts
                # are allowed two steps ahead of the current physics tail.
                end=offset
                while end<len(contacts) and contacts[end]['sim_ns']<=last['sim_ns']+10_000_000:end+=1
                with (root/'contacts.jsonl').open('a') as stream:
                    stream.writelines(json.dumps(row)+'\n' for row in contacts[offset:end])
                offset=end;clock[0]=last['sim_ns']+(-5_000_000 if checks%2 else 5_000_000)
                wall[0]=last['monotonic_ns']+500_000_000
                native.poll();checks+=1
                if not native.fresh():failed+=1
            return dict(kind='READ_ONLY_TELEMETRY_REPLAY',physical_run=False,realtime_evidence=False,
                run=directory.name,physics_rows=len(physics),contact_rows=len(contacts),chunks=checks,
                stale_or_invalid_chunks=failed,source_problem=native.error,
                pre_robot_contact_prefix_records=getattr(native,'pre_robot_contact_prefix_records',None),
                pending_shutdown_tail=len(native.pending),protected_peak_m=native.protected_peak)
    finally:module.time.monotonic_ns=old


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories',type=Path,nargs='+');parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--module',type=Path)
    args=parser.parse_args();module=contact_trace
    if args.module:
        spec=importlib.util.spec_from_file_location('archived_contact_trace',args.module)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=[replay(directory,module) for directory in args.directories]
    with args.out.open('x') as stream:json.dump(data,stream,indent=2,allow_nan=False)
    print(json.dumps(data,indent=2))
