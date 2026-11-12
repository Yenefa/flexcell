"""Tests for issue #236: the proposal generator must respect existing negative records."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status as ps


def _write(dirpath, name, payload):
    os.makedirs(dirpath, exist_ok=True)
    with open(os.path.join(dirpath, name), 'w', encoding='utf-8') as fh:
        json.dump(payload, fh)


def test_invalidated_signature_is_refused(tmp_path):
    """A record saying the basis was refuted must stop generation."""
    d = str(tmp_path)
    _write(d, 'thing_preregistration.json', {
        'record_kind': 'EVOBOT_PREREGISTRATION',
        'proposal': 'thing',
        'superseded_basis': {'recorded': '2026-11-11', 'why': 'measurement refuted the premise'},
    })
    idx = ps.load_status_index(d)
    allowed, state, why = ps.check('thing', idx)
    assert allowed is False
    assert state == ps.INVALIDATED
    assert 'refuted' in why


def test_unknown_signature_is_allowed_but_not_promoted(tmp_path):
    """No record must NOT become approved or verified by default (acceptance criterion 3)."""
    idx = ps.load_status_index(str(tmp_path))
    allowed, state, why = ps.check('never_reviewed', idx)
    assert allowed is True
    assert state == ps.UNKNOWN
    # The note must say what UNKNOWN means, so a downstream reader cannot mistake it.
    assert 'UNKNOWN' in why
    assert 'not approved' in why or 'not as approved' in why


def test_active_signature_is_allowed(tmp_path):
    """A live record with no negative basis keeps generating (acceptance criterion 2)."""
    d = str(tmp_path)
    _write(d, 'live.json', {'signature': 'live', 'kind': 'bounded_release_retry'})
    idx = ps.load_status_index(d)
    allowed, state, why = ps.check('live', idx)
    assert allowed is True
    assert state == ps.ACTIVE


def test_supersede_relationship_is_refused(tmp_path):
    """Another record naming this one as replaced must stop generation."""
    d = str(tmp_path)
    _write(d, 'replacement_preregistration.json', {
        'record_kind': 'EVOBOT_PROPOSAL_PREREGISTRATION',
        'proposal_id': 'replacement',
        'supersedes': 'old_thing / bounded_release_retry (basis found wrong)',
    })
    idx = ps.load_status_index(d)
    allowed, state, why = ps.check('old_thing', idx)
    assert allowed is False
    assert state == ps.SUPERSEDED
    assert 'replacement_preregistration.json' in why


def test_invalidation_outranks_supersede(tmp_path):
    """When both records exist, the measured reason wins because it is the traceable one."""
    d = str(tmp_path)
    _write(d, 'thing_preregistration.json', {
        'proposal': 'thing',
        'superseded_basis': {'why': 'measured and refuted'}})
    _write(d, 'later_preregistration.json', {
        'proposal_id': 'later',
        'supersedes': 'thing / something'})
    idx = ps.load_status_index(d)
    allowed, state, why = ps.check('thing', idx)
    assert allowed is False
    assert state == ps.INVALIDATED
    assert 'measured and refuted' in why


def test_repository_records_are_read_correctly():
    """Against the REAL proposal records checked into the repository."""
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'evolution', 'proposals')
    idx = ps.load_status_index(d)
    allowed, state, _ = ps.check('actuator_stall', idx)
    assert state == ps.INVALIDATED
    assert allowed is False
    allowed2, state2, _ = ps.check('occupied_destination', idx)
    assert allowed2 is True