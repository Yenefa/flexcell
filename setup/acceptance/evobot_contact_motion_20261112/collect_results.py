"""Collect every declared execution, including failed and unearned slots."""
import argparse
import json
import math
from pathlib import Path


VERSIONS={'pilot1':'v2','pilot2':'v3','B1':'v4_fixed_batch','C1':'v5_fixed_batch',
          'D1':'v5_fixed_batch','E1':'v6_fixed_batch','F1':'v7_validation',
          'G1':'v8_validation','H1':'v9_validation','I1':'v10_validation',
          'J1':'v11_validation','K0':'v12_harness','K1':'v12_harness',
          'K2':'v12_harness','K3':'v12_harness'}
PREEXEC={'v2':'preexecution_v2.json','v3':'preexecution_v3.json',
         **{v:'preexecution_'+v+'.json' for v in set(VERSIONS.values())-{'v2','v3'}}}


def read(path):return json.loads(path.read_text())


def collect(root):
    result=[]
    for name,version in VERSIONS.items():
        run=root/name
        entry=dict(run=name,version=version,role='control' if name in ('D1','K0') else
                   'confirmation' if name in ('K2','K3') else 'development_validation')
        if not run.exists():
            entry['execution']='NOT_RUN';result.append(entry);continue
        entry['execution']=read(run/'run_status.json')
        if (run/'gt_before.json').exists() and (run/'gt_after.json').exists():
            before=read(run/'gt_before.json')['objects'];after=read(run/'gt_after.json')['objects']
            entry.update(net_signed_m=before['target_box_a'][0]-after['target_box_a'][0],
                         net_vector_m=[b-a for a,b in zip(before['target_box_a'][:3],after['target_box_a'][:3])],
                         protected_net_m=math.dist(before['target_box_b'][:3],after['target_box_b'][:3]))
        if (run/'verdict.json').exists():
            verdict=read(run/'verdict.json');evidence=verdict.get('evidence',{})
            entry.update(full_task_passed=verdict['passed'],evidence_status=evidence.get('evidence_status'),
                gates=[dict(gate=g['gate'],ok=g['ok'],evidence=g.get('evidence')) for g in evidence.get('gates',[])],
                failed_gates=evidence.get('failed_gates'))
        if name in ('D1','K0'):
            entry['primitive_results']=[dict(outcome=int(row['outcome']),error_code=row['error_code'],
                displacement_m=row['displacement_m']) for row in
                map(json.loads,(run/'sim/skills/push.jsonl').read_text().splitlines())]
            entry['returned_arm_readiness']='NOT_EXPOSED_BY_LEGACY_ACTION'
        else:
            summary=run/'trial/contact_summary.json'
            entry['summary']=read(summary) if summary.exists() else {'status':'NO_DRIVER_SUMMARY'}
            entry['receipts']=[read(p) for p in sorted((run/'trial').glob('receipt_*.json'))]
            consumer=run/'receipt_consumer.jsonl'
            entry['consumer_checks']=[{k:v for k,v in row.items() if k!='receipt'}
                for row in map(json.loads,consumer.read_text().splitlines())] if consumer.exists() else []
            events=run/'trial/events.jsonl'
            selections=[row.get('joint_selection') for row in map(json.loads,events.read_text().splitlines())
                        if row['kind']=='CONSTRAINED_DISPATCH'] if events.exists() else []
            selected=[s for s in selections if s is not None]
            entry['dispatch_joint_source_age_max_s']=max((s['source_age_s'] for s in selected),default=None)
            entry['dispatch_joint_receive_age_max_s']=max((s['wall_age_s'] for s in selected),default=None)
        provenance=read(run/'provenance.json');expected=read(root/PREEXEC[version])['sources']
        matches={}
        for label,source in provenance['sources'].items():
            path=source['path']
            if path.startswith('/candidate/') and path[len('/candidate/'):] in expected:
                matches[label]=source['sha256']==expected[path[len('/candidate/'):]]
        entry['recorded_source_hash_checks']=matches
        required={'flexcell_skills.contact_geometry','flexcell_skills.contact_motion',
                  'flexcell_skills.contact_receipt','flexcell_skills.contact_trace',
                  'run_contact_push.py','run_case.py'}
        entry['recorded_sources_match_preregistration']=required<=matches.keys() and all(matches.values())
        entry['claim_accuracy']='NOT_MEASURED_NO_AGENT_CLAIM'
        result.append(entry)
    return dict(scope='isolated exposed seed2000; no baseline promotion',runs=result,
        aborted_or_unearned_slots={'v3_fixed_batch':['A1','B1','B2','B3'],
            'v4_fixed_batch':['A1','B2','B3'],'v5_fixed_batch':['C2','C3'],
            'v6_fixed_batch':['E2','E3'],'v7_validation':['F2','F3'],
            'v8_validation':['G2','G3'],'v9_validation':['H2','H3'],
            'v10_validation':['I2','I3'],'v11_validation':['J2','J3']},
        ordinary_pick_place_this_round='NOT_RUN; prior mixed release outcomes retained',
        runtime_integration='NOT_DONE',formal_baseline='NOT_PROMOTED',L4='NOT_ACQUIRED')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    with args.out.open('x') as stream:json.dump(collect(args.root),stream,indent=2,allow_nan=False)
