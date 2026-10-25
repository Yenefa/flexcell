#!/usr/bin/env python3
"""Differential proof that recording carry identity did not change behaviour.

#32's sixth acceptance item requires that a change touching the frozen carry
backend prove it did not alter the mechanism. This imports `_on_stop` from the
pre-change revision AND from the working tree, runs both over the same matrix
of synthetic states, and requires them to agree on everything the server does:

    return value, _object_id, _offset, _session, _retired_sessions,
    number of _publish_state calls, number of _guard_release calls

The log payload is compared separately and is allowed to differ only by the
added keys (`session`, `object`, `engaged`, `cause`). Every shared key must
hold the same value.

Extract the pre-change file first (it is vendored here, so normally you do not):
  git show main:src/flexcell/flexcell_skills/flexcell_skills/carry_server.py \
      > carry_server_before.txt

Run:  python3 prove_no_control_flow_change.py [carry_server_before.txt]
Exit: 0 equivalent on every state tried; 1 a behavioural difference was found.
"""
import hashlib
import itertools
import os
import sys
import threading
import types
from unittest.mock import Mock

TOKEN = 'a1b2c3d4e5f60718293a4b5c6d7e8f90'
ADDED_KEYS = {'session', 'object', 'engaged', 'cause'}
BEFORE_SHA256 = '15f9f1b9cbbdd772a6bab1fe644a066e468c0484cf2b7a7e3be72caa834d55db'


def load(path, name):
    """Compile from source text so the vendored reference can stay a .txt and
    never be mistaken for an importable module by lint or build tooling."""
    module = types.ModuleType(name)
    module.__file__ = path
    sys.modules[name] = module
    with open(path, 'rb') as fh:
        source = fh.read()
    exec(compile(source, path, 'exec'), module.__dict__)
    return module.CarryServer, hashlib.sha256(source).hexdigest()


def state(thread_state, backend, guard_ok, session, object_id, offset):
    if thread_state == 'none':
        thread = None
    else:
        thread = Mock()
        thread.is_alive.return_value = (thread_state == 'alive')
    node = types.SimpleNamespace(
        _thread=thread, _stop_evt=threading.Event(), _backend=backend,
        _session=session, _object_id=object_id, _offset=offset,
        _retired_sessions=set(), _log=Mock(), get_logger=Mock())
    node._publish_state = Mock()
    node._guard_release = Mock(return_value=guard_ok)
    return node


def snapshot(node):
    return (node._object_id, list(node._offset) if node._offset else node._offset,
            node._session, sorted(node._retired_sessions),
            node._publish_state.call_count, node._guard_release.call_count)


def main():
    before_path = (sys.argv[1] if len(sys.argv) > 1
                   else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'carry_server_before.txt'))
    before_cls, digest = load(before_path, 'carry_server_before')
    print('reference : %s' % os.path.basename(before_path))
    print('sha256    : %s %s' % (digest,
                                 'MATCHES the pinned value'
                                 if digest == BEFORE_SHA256 else 'DIFFERS from pinned'))
    if digest != BEFORE_SHA256:
        print('refusing to compare against an unpinned reference')
        return 1

    repo = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    after = os.path.join(repo, 'src', 'flexcell', 'flexcell_skills',
                         'flexcell_skills', 'carry_server.py')
    after_cls, _ = load(after, 'carry_server_after')
    print('candidate : src/flexcell/flexcell_skills/flexcell_skills/carry_server.py')

    combos = list(itertools.product(
        ('none', 'alive', 'dead'), ('teleport', 'velocity_servo'),
        (True, False), ('', TOKEN), ('', 'target_box_a'),
        (None, [0.0, 0.0, 0.0])))
    print('state matrix: %d combinations' % len(combos))

    behavioural, payload, compared = [], [], 0
    for combo in combos:
        old_node = state(*combo)
        new_node = state(*combo)
        old_ret = before_cls._on_stop(old_node, None)
        new_ret = after_cls._on_stop(new_node, None)
        compared += 1

        if old_ret != new_ret:
            behavioural.append((combo, 'return', old_ret, new_ret))
        if snapshot(old_node) != snapshot(new_node):
            behavioural.append((combo, 'state', snapshot(old_node),
                                snapshot(new_node)))

        old_log = [c.args[0] for c in old_node._log.write.call_args_list]
        new_log = [c.args[0] for c in new_node._log.write.call_args_list]
        if len(old_log) != len(new_log):
            # a stop that fails early may log nothing at all; still a difference
            payload.append((combo, 'record count', len(old_log), len(new_log)))
            continue
        for old_rec, new_rec in zip(old_log, new_log):
            if set(old_rec) - set(new_rec):
                payload.append((combo, 'lost keys',
                                sorted(set(old_rec) - set(new_rec)), ''))
            for key in set(old_rec) & set(new_rec):
                if old_rec[key] != new_rec[key]:
                    payload.append((combo, 'value drift', key,
                                    '%r -> %r' % (old_rec[key], new_rec[key])))
            if not set(new_rec) - set(old_rec) <= ADDED_KEYS:
                payload.append((combo, 'unexpected new keys',
                                sorted(set(new_rec) - set(old_rec)), ''))

    print('compared %d states' % compared)
    print('behavioural differences: %d' % len(behavioural))
    for item in behavioural[:8]:
        print('  %s' % (item,))
    print('log differences other than the declared added keys: %d' % len(payload))
    for item in payload[:8]:
        print('  %s' % (item,))

    ok = not behavioural and not payload
    print('\n%s' % ('EQUIVALENT: the only change is what the record contains'
                    if ok else 'DIFFERENT: behaviour or payload drifted'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
