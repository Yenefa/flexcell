"""Facts can be verified without promoting residuals into causal bounds."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('phase3_facts', ROOT / 'setup/verify_phase3_facts.py')
facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)


def test_archived_window_has_complete_evidence_but_unknown_cause():
    report = facts.adjudicate()
    assert report['status'] == 'FACTS_VERIFIED'
    assert (report['successes'], report['failures']) == (9, 1)
    assert report['mechanism'] == report['historical_same_mechanism'] == 'UNKNOWN'
    failed = next(t for t in report['trials'] if not t['pick_ok'])
    assert failed['error_code'] == 23 and failed['rise_m'] > 0
    assert failed['session_totals']['pin_failed'] == 0


def test_observed_maximum_is_not_a_bound_on_future_fall():
    # 49 mm assumes zero initial speed; neither speed nor maximum interval was
    # measured by #52. A valid model already refutes the categorical claim.
    assert facts.ballistic_drop(0., .1) == pytest.approx(.04905)
    assert .0891 - facts.ballistic_drop(1., .1) < 0
    assert .0891 - facts.ballistic_drop(0., .2) < 0


@pytest.mark.parametrize('defect', ['false_success', 'lost_final', 'wrong_rise', 'dirty_health'])
def test_recovered_raw_facts_still_reject_tampering(tmp_path, defect):
    archive = tmp_path / 'archive'
    shutil.copytree(facts.DEFAULT_ARCHIVE, archive)
    if defect == 'dirty_health':
        path = archive / 'health_after.json'
        doc = json.loads(path.read_text())
        doc['checks']['carry_engaged'] = True
        path.write_text(json.dumps(doc))
    else:
        path = archive / ('logs/carry_window.jsonl' if defect == 'lost_final' else 'B5.jsonl')
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        for row in rows:
            if defect == 'lost_final' and row.get('final'):
                row['final'] = False
            if defect == 'false_success' and row.get('pick_ok') is False:
                row.update(pick_ok=True, error_code=0)
            if defect == 'wrong_rise' and row.get('pick_ok') is False:
                row['rise_m'] = .2
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert facts.adjudicate(archive)['status'] == 'FACTS_REJECTED'
