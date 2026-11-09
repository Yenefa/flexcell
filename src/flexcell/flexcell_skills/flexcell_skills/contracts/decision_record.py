"""The decision-log record, built once instead of twice (P2-B).

The executor writes one record per policy decision: a dispatched decision and a
safety-gate rejection differ ONLY in `dispatched`, `safety_rejection` and the
typed rejection fields. Both sites used to spell the whole dict out, so a field
added to one silently went missing from the other. This module owns the shape.

Pure: no ROS, no I/O, no clock. The caller passes every value in.
"""


def decision_record(*, run_id, scenario, seq, previous_skill_result, recovery,
                    decision, policy_name, policy_version, world_revision,
                    observe_evidence_id, decide_latency_ms, dispatched,
                    rejection_kind=None, rejection_error_code=None):
    """One decision-log record.

    `dispatched=False` must carry the gate reason; `dispatched=True` must not.
    The rejection fields are additive so existing readers keep working.
    """
    if not dispatched and not rejection_kind:
        raise ValueError('a non-dispatched decision needs its rejection reason')
    record = {
        'run_id': run_id, 'scenario_id': scenario,
        'seq': seq,
        'previous_skill_result': previous_skill_result,
        'recovery': recovery,
        'action': decision.action, 'target': decision.target,
        'confidence': decision.confidence,
        'reason_code': decision.reason_code,
        'explanation': decision.explanation,
        'policy': policy_name,
        'policy_version': policy_version,
        'world_revision': world_revision,
        'observe_evidence_id': observe_evidence_id,
        'decide_latency_ms': decide_latency_ms,
        'policy_trace': decision.policy_trace,
        'dispatched': bool(dispatched),
        'safety_rejection': rejection_kind,
    }
    if rejection_kind is not None:
        record['rejection_kind'] = rejection_kind
        record['rejection_error_code'] = int(rejection_error_code)
    return record
