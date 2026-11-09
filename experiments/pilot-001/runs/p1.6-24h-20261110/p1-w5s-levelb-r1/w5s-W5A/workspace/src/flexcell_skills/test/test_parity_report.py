"""Reject forged summaries and missing/ambiguous transported receipts."""
import json
from pathlib import Path
import shutil
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from parity_report import CASES, compare


@pytest.fixture
def sealed(tmp_path):
    with tarfile.open(ROOT/'setup/acceptance/native_portable_20261101/legacy-review-source.tar') as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith(('setup/acceptance/legacy_parity_20261031/',
                                                           'setup/acceptance/legacy_skill_matrix_20261031/')):
                assert '..' not in Path(member.name).parts
                path = tmp_path/member.name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
    return tmp_path/'setup/acceptance'


def paths(root, matrix=False):
    directory='legacy_skill_matrix_20261031' if matrix else 'legacy_parity_20261031'
    return [root/directory/name/'window.json' for name in
            (['teleport','detachable_joint'] if matrix else ['teleport','velocity_servo','detachable_joint'])]


def edit(path, change):
    value=json.loads(path.read_text()); change(value);path.write_text(json.dumps(value))


def verify_path(path, index=0):
    data=json.loads(path.read_text());return path.parent/Path(data['episodes'][index]['run']).name/'skills/verify.jsonl'


def edit_verify(path, change):
    rows=[json.loads(l) for l in path.read_text().splitlines()];change(rows)
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def test_original_receipts_keep_pass_and_use_actual_60mm_tolerance(sealed):
    report=compare(paths(sealed))
    assert report['status']=='CARRY_BACKEND_PARITY_PASS' and report['declared_tolerance_m']==.06
    assert report['skill_backend']=='mtc' and report['default_admission']=='NO_GO'
    assert report['max_verified_error_m']['detachable_joint']==pytest.approx(.012252028927226412)
    assert set(report['attempts']['teleport'])=={c+'/'+o for c,o in CASES}
    for p in paths(sealed):
        original=ROOT/'setup/acceptance/legacy_parity_20261031'/p.parent.name/'window.json'
        assert p.read_bytes()==original.read_bytes()


@pytest.mark.parametrize('defect',['duplicate_backend','mixed_skill','stopped_window','missing_error','wrong_negative',
                                 'missing_skill','different_manifest','short','different_cases','failed_case'])
def test_report_rejects_summary_counterexamples(sealed,defect):
    ps=paths(sealed)
    def change(w):
        if defect=='duplicate_backend':w['backend']='teleport'
        elif defect=='mixed_skill':w['skill_backend']='legacy'
        elif defect=='stopped_window':w['status']='STOPPED'
        elif defect=='missing_error':w['episodes'][0]['result']['task'].pop('final_position_error_m')
        elif defect=='wrong_negative':
            w['episodes'][0]['result'].update(status='EXPECTED_FAILURE')
            w['episodes'][0]['result']['task'].update(outcome='OUTCOME_FAILED',error_code='ERR_INTERNAL')
        elif defect=='missing_skill':w.pop('skill_backend')
        elif defect=='different_manifest':w['declaration_sha256']='e'*64
        elif defect=='short':w['episodes'].pop()
        elif defect=='different_cases':w['episodes'][0]['case']='budget_exhaustion'
        else:w['episodes'][0]['result']['expectation_met']=False
    edit(ps[-1],change)
    with pytest.raises(ValueError):compare(ps)


@pytest.mark.parametrize('value',[None,True,False,-.1,float('nan'),float('inf'),'0.004'])
@pytest.mark.parametrize('field',['task_error','verify_error','verify_tolerance'])
def test_metrics_must_be_actual_finite_nonboolean_numbers(sealed,value,field):
    ps=paths(sealed)
    if field=='task_error':edit(ps[0],lambda w:w['episodes'][0]['result']['task'].update(final_position_error_m=value))
    else:edit_verify(verify_path(ps[0]),lambda rows:rows[0].update(**{('position_error_m' if field=='verify_error' else 'tolerance_m'):value}))
    with pytest.raises(ValueError):compare(ps)


@pytest.mark.parametrize('defect',['missing_zone','missing_verify_zone','different_tolerance','too_far','wrong_outcome',
                                 'no_verify','empty_verify','negative_error','negative_outcome','negative_metric'])
def test_real_verification_and_negative_contract_are_required(sealed,defect):
    ps=paths(sealed)
    if defect=='missing_zone':edit(ps[0],lambda w:w['episodes'][2]['result']['task'].pop('zone_b_error_m'))
    elif defect=='missing_verify_zone':edit_verify(verify_path(ps[0],2),lambda rows:rows.pop())
    elif defect=='different_tolerance':edit_verify(verify_path(ps[0]),lambda rows:rows[0].update(tolerance_m=.05))
    elif defect=='too_far':edit_verify(verify_path(ps[0]),lambda rows:rows[0].update(position_error_m=.061))
    elif defect=='wrong_outcome':edit_verify(verify_path(ps[0]),lambda rows:rows[0].update(outcome='1',verified=False,error_code=25))
    elif defect=='no_verify':verify_path(ps[0]).unlink()
    elif defect=='empty_verify':verify_path(ps[0]).write_text('')
    else:
        def change(w):
            task=w['episodes'][-1]['result']['task']
            if defect=='negative_error':task['error_code']='ERR_INTERNAL'
            elif defect=='negative_outcome':task['outcome']='OUTCOME_SUCCEEDED'
            else:task['final_position_error_m']=0.
        edit(ps[0],change)
    with pytest.raises(ValueError):compare(ps)


def test_transported_ci_trial_layout_cannot_skip_metrics(sealed):
    ps=paths(sealed,matrix=True)
    for p in ps:
        data=json.loads(p.read_text())
        for index,e in enumerate(data['episodes'],1):
            old=p.parent/Path(e['run']).name
            new=p.parent/('trial-%02d'%index)/old.name;new.parent.mkdir();old.rename(new)
            e['run']='/artifacts/legacy-skill-'+data['backend']+'/'+new.parent.name+'/'+new.name
        p.write_text(json.dumps(data))
    report=compare(ps)
    assert report['declared_tolerance_m']==.06
    assert report['max_verified_error_m']['detachable_joint']==pytest.approx(.045006972)
    assert all(r['receipt'] for t in report['table'].values() for r in t['cases'])
    for p in ps:
        for f in p.parent.glob('trial-*/run-*/skills/verify.jsonl'):f.unlink()
    with pytest.raises(ValueError,match='verify receipt'):compare(ps)


def test_ambiguous_flat_and_trial_receipts_are_rejected(sealed):
    ps=paths(sealed);p=ps[0];run=p.parent/Path(json.loads(p.read_text())['episodes'][0]['run']).name
    copy=p.parent/'trial-01'/run.name;copy.parent.mkdir();shutil.copytree(run,copy)
    with pytest.raises(ValueError,match='ambiguous'):compare(ps)


def test_duplicate_table_labels_do_not_overwrite_backends(sealed,tmp_path):
    ps=paths(sealed);copies=[]
    for index,p in enumerate(ps):
        new=tmp_path/str(index)/'same-label';shutil.copytree(p.parent,new);copies.append(new/'window.json')
    with pytest.raises(ValueError,match='table identity'):compare(copies)


def test_tolerance_cannot_be_replaced_by_caller(sealed):
    assert compare(paths(sealed),max_placement_error_m=.06)['declared_tolerance_m']==.06
    with pytest.raises(ValueError,match='requested tolerance'):compare(paths(sealed),max_placement_error_m=.012)


def test_bare_archived_summaries_do_not_supply_missing_raw_receipts():
    with pytest.raises(ValueError,match='receipt'):compare(paths(ROOT/'setup/acceptance'))


@pytest.mark.parametrize('selection', [[], [0], [0, 0]])
def test_comparison_needs_distinct_windows(sealed, selection):
    ps = paths(sealed)
    with pytest.raises(ValueError):
        compare([ps[index] for index in selection])


def test_damaged_verify_json_is_rejected(sealed):
    ps = paths(sealed)
    verify_path(ps[0]).write_text('{broken receipt}\n')
    with pytest.raises(ValueError):
        compare(ps)


def test_budget_negative_cannot_borrow_zone_metric(sealed):
    ps = paths(sealed)
    edit(ps[0], lambda w: w['episodes'][-1]['result']['task'].update(zone_a_error_m=0.))
    with pytest.raises(ValueError, match='negative case'):
        compare(ps)
