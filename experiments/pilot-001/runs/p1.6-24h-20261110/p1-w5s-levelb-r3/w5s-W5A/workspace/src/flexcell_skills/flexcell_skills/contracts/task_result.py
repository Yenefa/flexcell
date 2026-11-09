"""Task result diagnostics derived from executor-owned skill evidence."""

from flexcell_skills.contracts.error_codes import STATUS_SUCCESS, error_name


def task_abort_detail(reason_code, explanation, trace, previous=None):
    """Keep policy telemetry and the last failed skill's typed cause together.

    `previous` is the executor's previous_skill_result view, not model text.
    Only the latest skill is considered: a successful intervening skill must
    not make an old failure appear to cause a later model abort. Task-level
    50/51 mapping, action selection, history and recovery budgets stay separate.
    """
    detail = 'policy abort (%s): %s (trace=%s)' % (
        reason_code, explanation, ','.join(trace))
    if previous and previous['status'] != STATUS_SUCCESS:
        detail += '; previous_skill=%s cause=%s legacy_error_code=%d' % (
            previous['skill'], error_name(previous['canonical_error_code']),
            previous['error_code'])
        if previous.get('mapping_warning'):
            detail += ' mapping_warning=%s' % previous['mapping_warning']
    return detail
