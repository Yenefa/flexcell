"""A false attachment must stop the carry and fail typed, never pass as success."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from false_attach_gate import FROZEN, verify_run

SESSION = 'c' * 32
FIRST = 1_000_000_000
STEP = 20_000_000


def build(root, *, frames=FROZEN['frames'], offset=FROZEN['offset_m'],
          first=FIRST + FROZEN['after_samples'] * STEP, fault='measured relative pose exceeded follow limits',
          outcome='1', error_code=2,
          detail='physical follow unconfirmed: measured relative pose exceeded follow limits; '
                 'motion terminal confirmed; carry held for reconciliation',
          places=0, drift=.031):
    skills = root / 'skills'
    skills.mkdir(parents=True)
    follow = dict(object='target_box_a', session=SESSION, samples=FROZEN['after_samples'] + 1,
                  max_translation_m=drift, max_rotation_rad=1e-4, fault=fault, active=False,
                  first_sim_ns=FIRST, last_sim_ns=first + frames * STEP,
                  reference_source='preposition')
    carry = [
        dict(event='start', object='target_box_a', session=SESSION, backend='detachable_joint'),
        dict(event='false_attach_injected', object='target_box_a', session=SESSION,
             offset_m=offset, frames=frames, axis=FROZEN['axis'], boundary=FROZEN['boundary'],
             first_sim_ns=first, last_sim_ns=first + (frames - 1) * STEP, follow_fault=fault),
        dict(event='follow_final', object='target_box_a', session=SESSION, follow=follow),
    ]
    (skills / 'carry.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in carry))
    (skills / 'pick.jsonl').write_text(json.dumps(dict(
        object_name='target_box_a', outcome=outcome, error_code=error_code, detail=detail)) + '\n')
    if places:
        (skills / 'place.jsonl').write_text(''.join(
            json.dumps(dict(object_name='target_box_a', outcome='0')) + '\n' for _ in range(places)))
    return dict(required_false_attach=True,
                false_attach={key: FROZEN[key] for key in ('object', 'offset_m', 'hold_s')})


def test_declared_false_attachment_is_typed_stop_without_success_claim(tmp_path):
    declaration = build(tmp_path)
    result = verify_run(tmp_path, 'target_box_a', declaration)
    assert result['status'] == 'FALSE_ATTACH_REJECTED'
    assert result['injected_frames'] == FROZEN['frames']
    assert result['place_dispatched'] is False


def test_injection_before_the_session_followed_is_refused(tmp_path):
    declaration = build(tmp_path, first=FIRST + 2 * STEP)
    with pytest.raises(ValueError, match='before the session was following'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_missing_injection_record_is_refused(tmp_path):
    declaration = build(tmp_path)
    (tmp_path / 'skills/carry.jsonl').write_text('\n'.join(
        line for line in (tmp_path / 'skills/carry.jsonl').read_text().splitlines()
        if 'false_attach_injected' not in line) + '\n')
    with pytest.raises(ValueError, match='exactly once'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_invisible_displacement_proves_nothing(tmp_path):
    declaration = build(tmp_path, drift=.001)
    with pytest.raises(ValueError, match='never reached the sampled drift'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_a_successful_claim_after_the_fault_is_refused(tmp_path):
    declaration = build(tmp_path, outcome='0', error_code=0,
                        detail='picked target_box_a: attached, measured rise 0.120m')
    with pytest.raises(ValueError, match='claimed success'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_unconfirmed_stop_is_refused(tmp_path):
    declaration = build(tmp_path, detail='physical follow unconfirmed: measured relative pose exceeded '
                                         'follow limits; MotionTerminalUnknown: movement stop was not confirmed')
    with pytest.raises(ValueError, match='no confirmed terminal state|stop was not confirmed'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_place_after_the_fault_is_refused(tmp_path):
    declaration = build(tmp_path, places=1)
    with pytest.raises(ValueError, match='PLACE'):
        verify_run(tmp_path, 'target_box_a', declaration)


def test_changed_fixture_is_refused(tmp_path):
    declaration = build(tmp_path)
    declaration['false_attach'] = dict(declaration['false_attach'], offset_m=.05)
    with pytest.raises(ValueError, match='fixture changed'):
        verify_run(tmp_path, 'target_box_a', declaration)
