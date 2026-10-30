"""A declared false attachment must be caught mid-motion, stop it and fail typed.

A rigid fixed joint cannot physically slip, so the injection is applied at the
follow guard's input boundary: the body keeps reporting an attachment while its
reported pose stops following its parent. This gate proves the whole chain —
guard fault, cancel, confirmed stop, typed failure, no success claim — and refuses
a window whose declaration differs from the frozen fixture.
"""
import json
import math
from pathlib import Path

from contact_gate import require

#: Frozen fixture. Change these only together with the declaration and the code.
FROZEN = dict(object='target_box_a', offset_m=.03, hold_s=.2, frames=10,
              axis='world_x', boundary='guard_input_pose', after_samples=30)
ERR_INTERNAL = 2

#: The injected displacement must be visible as sampled drift, or the guard was
#: never actually lied to and the window proves nothing.
MIN_VISIBLE_DRIFT_M = .02


def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_run(run, object_id, declaration):
    run = Path(run)
    declared = declaration.get('false_attach')
    require(declaration.get('required_false_attach') is True, 'false-attach window is not declared')
    require(isinstance(declared, dict) and declared == {key: FROZEN[key]
                                                       for key in ('object', 'offset_m', 'hold_s')},
            'false-attach fixture changed or undeclared')
    require(object_id == FROZEN['object'], 'window target differs from the frozen fixture')

    carry = rows(run / 'skills/carry.jsonl')
    finals = [row for row in carry if row.get('event') == 'follow_final']
    require(len(finals) == 1, 'ambiguous carried session')
    final = finals[0]
    follow = final['follow']
    session = final.get('session')
    require(final.get('object') == object_id and follow.get('object') == object_id,
            'carried session belongs to another object')
    require(follow.get('reference_source') == 'preposition',
            'the session was not anchored on a pre-attach reference')

    injected = [row for row in carry if row.get('event') == 'false_attach_injected']
    require(len(injected) == 1, 'the declared injection did not happen exactly once')
    event = injected[0]
    require(event.get('object') == object_id and event.get('session') == session,
            'injection does not belong to this session')
    require(event.get('offset_m') == FROZEN['offset_m'] and event.get('frames') == FROZEN['frames'],
            'injection differs from the declaration')
    require(event.get('boundary') == FROZEN['boundary'] and event.get('axis') == FROZEN['axis'],
            'injection boundary or axis changed')
    require(isinstance(event.get('first_sim_ns'), int) and isinstance(event.get('last_sim_ns'), int)
            and event['last_sim_ns'] > event['first_sim_ns'], 'injected frames have no span')
    require(FROZEN['after_samples'] * 20_000_000 <=
            event['first_sim_ns'] - follow['first_sim_ns'],
            'injection fired before the session was following')

    require(str(follow.get('fault') or '') != '', 'the guard did not latch a fault')
    require('relative pose' in follow['fault'], 'the fault is not the measured pose mismatch')
    require(follow.get('active') is False, 'follow monitor still active after the fault')
    require(follow.get('samples', 0) >= FROZEN['after_samples'] + FROZEN['frames'],
            'too few following samples to cover the injection')
    require(math.isfinite(follow.get('max_translation_m', -1)) and
            follow['max_translation_m'] >= MIN_VISIBLE_DRIFT_M,
            'the injected displacement never reached the sampled drift')

    picks = rows(run / 'skills/pick.jsonl')
    require(len(picks) == 1 and picks[0].get('object_name') == object_id,
            'the pick record is missing or ambiguous')
    pick = picks[0]
    require(str(pick.get('outcome')) != '0', 'the skill claimed success while the body did not follow')
    require(pick.get('error_code') == ERR_INTERNAL,
            'the failure was not the typed follow error (%r)' % (pick.get('error_code'),))
    detail = str(pick.get('detail', ''))
    require('physical follow unconfirmed' in detail, 'the failure detail hides the follow fault')
    require('motion terminal confirmed' in detail,
            'the interrupted motion has no confirmed terminal state')
    require('MotionTerminalUnknown' not in detail, 'motion terminal unknown; stop was not confirmed')

    places = rows(run / 'skills/place.jsonl')
    require(not places, 'a PLACE was dispatched after the attachment was refused')
    return dict(status='FALSE_ATTACH_REJECTED', object=object_id, session=session,
                injected_frames=event['frames'], offset_m=event['offset_m'],
                injection_first_sim_ns=event['first_sim_ns'],
                injection_last_sim_ns=event['last_sim_ns'],
                follow_fault=follow['fault'], max_translation_m=follow['max_translation_m'],
                pick_error_code=pick['error_code'], pick_detail=detail,
                motion_error_code=pick.get('motion_error_code'),
                place_dispatched=False, boundary=FROZEN['boundary'],
                interpretation='Guard-input injection of a false attachment; the fixed-joint oracle '
                               'cannot slip physically, so this qualifies the response chain only')
