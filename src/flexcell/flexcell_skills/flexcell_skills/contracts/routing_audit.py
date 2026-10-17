"""Fail-closed provenance checks against one frozen deployment manifest."""


def audit_routing_episode(record, deployment):
    fast_identity = deployment.get('active_backends', {}).get('fast', {})
    expected_sha = fast_identity.get('calibration_sha256')
    report = dict(ok=False, errors=[], bootstrap=0, model_decisions=0,
                  fast_selected=0, slow_selected=0, fsm_fallbacks=0,
                  fast_calls=0, fast_tokens=0, calibration_sha256=expected_sha)
    errors = report['errors']
    if not expected_sha:
        errors.append('deployment has no calibration SHA')
    if record.get('runtime_fingerprint') != deployment.get('runtime_fingerprint'):
        errors.append('runtime fingerprint mismatch')
    if not record.get('steps'):
        errors.append('episode has no decisions')
    for step in record.get('steps', []):
        trace = (step.get('policy_output') or {}).get('policy_trace') or {}
        seq = step.get('seq')
        def reject(reason):
            errors.append('seq=%s: %s' % (seq, reason))
        if trace.get('threshold') != deployment.get('threshold'):
            reject('threshold mismatch')
        if trace.get('calibration_sha256') != expected_sha:
            reject('loaded calibration SHA mismatch')
        source = trace.get('source')
        bootstrap = (step.get('policy_input') or {}).get('world_state_canonical') is None
        if bootstrap:
            report['bootstrap'] += 1
            if source != 'fsm' or trace.get('failure') != 'bootstrap':
                reject('invalid bootstrap provenance')
            continue
        if source in ('jev', 'llm') and trace.get('fallback') is False:
            report['model_decisions'] += 1
            report['fast_selected' if source == 'jev' else 'slow_selected'] += 1
        else:
            report['fsm_fallbacks'] += 1
            reject('non-bootstrap FSM fallback or missing model provenance')
        fast_proposals = [p for p in trace.get('proposals', []) if p.get('policy') == 'jev']
        selected_fast = None
        for proposal in fast_proposals:
            if proposal.get('skipped'):
                continue
            report['fast_calls'] += 1
            fast = proposal.get('policy_trace') or {}
            if fast.get('source') != 'jev' or fast.get('fallback') is not False:
                reject('fast backend failed or silently fell back')
            if fast.get('calibration_sha256') != expected_sha:
                reject('fast proposal calibration SHA mismatch')
            for field in ('model', 'model_sha256'):
                if not fast_identity.get(field) or fast.get(field) != fast_identity[field]:
                    reject('fast proposal %s mismatch' % field)
            tokens = fast.get('tokens')
            if type(tokens) is not int or tokens <= 0:
                reject('fast proposal has no positive measured token usage')
            else:
                report['fast_tokens'] += tokens
            selected_fast = fast
        if source == 'jev' and (selected_fast is None or
                selected_fast.get('calibration') != expected_sha or
                selected_fast.get('confidence_calibrated') is not True):
            reject('selected fast route is not calibrated')
    if report['model_decisions'] and not report['fast_calls']:
        errors.append('no real fast proposal in a model-driven hybrid episode')
    report['ok'] = not errors
    return report


def audit_routing_batch(rows, deployment):
    """Qualify recorded hybrid rows against one frozen fast-arm identity.

    A paid slow decision is not evidence that the fast arm ran. Real fast
    calls may all escalate; fast *selection* is deliberately not required.
    The same check applies to archived smoke before dispatching a baseline.
    """
    expected_sha = deployment.get('active_backends', {}).get('fast', {}).get('calibration_sha256')
    fingerprint = deployment.get('runtime_fingerprint')
    counters = ('bootstrap', 'model_decisions', 'fast_selected', 'slow_selected',
                'fsm_fallbacks', 'fast_calls', 'fast_tokens')
    report = dict(ok=False, errors=[], episodes=len(rows),
                  runtime_fingerprint=fingerprint, calibration_sha256=expected_sha,
                  **{key: 0 for key in counters})
    errors = report['errors']
    if not rows:
        errors.append('batch has no episodes')
    if not expected_sha or not fingerprint:
        errors.append('deployment has no calibration SHA or runtime fingerprint')
    for index, row in enumerate(rows, 1):
        def reject(reason):
            errors.append('row=%d: %s' % (index, reason))
        if row.get('policy') != 'hybrid' or row.get('runtime_fingerprint') != fingerprint:
            reject('policy or runtime fingerprint mismatch')
        if row.get('harness_error') or row.get('outcome') == 'HARNESS_ERROR':
            reject('episode has a harness error')
        audit = row.get('routing_audit')
        if not isinstance(audit, dict):
            reject('missing episode routing audit')
            continue
        if audit.get('ok') is not True:
            reject('episode routing audit failed')
        if audit.get('calibration_sha256') != expected_sha:
            reject('episode calibration SHA mismatch')
        valid_counts = True
        for key in counters:
            value = audit.get(key)
            if type(value) is not int or value < 0:
                reject('invalid %s count' % key)
                valid_counts = False
            else:
                report[key] += value
        if valid_counts:
            if audit['model_decisions'] and not audit['fast_calls']:
                reject('no real fast proposal in this hybrid episode')
            if audit['model_decisions'] != audit['fast_selected'] + audit['slow_selected']:
                reject('model selection counts disagree')
            if audit['fast_tokens'] < audit['fast_calls'] or audit['fsm_fallbacks']:
                reject('invalid fast usage or non-bootstrap FSM fallback')
    if not report['fast_calls'] or not report['fast_tokens']:
        errors.append('batch has no real fast calls with measured tokens')
    report['ok'] = not errors
    return report
