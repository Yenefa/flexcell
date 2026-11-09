"""Unsubscribe is asynchronous: an in-flight native handler can retain Python."""
import signal
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest

from flexcell_skills import common, pose_stream_worker


def test_main_waits_for_last_native_callback_reference(monkeypatch):
    handlers = {}
    released = threading.Event()
    retained = []
    threads = []

    class Node:
        def subscribe_raw(self, topic, callback, message_type, options):
            retained.append(callback)
            handlers[signal.SIGTERM]()
            return True

        def unsubscribe(self, topic):
            # Mimic RecvMsgUpdate retaining HandlerInfo outside the Node mutex.
            def drop_inflight_handler():
                time.sleep(.05)
                retained.clear()
                released.set()
            thread = threading.Thread(target=drop_inflight_handler)
            threads.append(thread)
            thread.start()
            return True

    transport = ModuleType('gz.transport13')
    transport.Node = Node
    transport.SubscribeOptions = SimpleNamespace
    proto = ModuleType('gz.msgs10.pose_v_pb2')
    proto.Pose_V = SimpleNamespace(DESCRIPTOR=SimpleNamespace(full_name='gz.msgs.Pose_V'))
    monkeypatch.setitem(sys.modules, 'gz', ModuleType('gz'))
    monkeypatch.setitem(sys.modules, 'gz.transport13', transport)
    monkeypatch.setitem(sys.modules, 'gz.msgs10', ModuleType('gz.msgs10'))
    monkeypatch.setitem(sys.modules, 'gz.msgs10.pose_v_pb2', proto)
    monkeypatch.setattr(sys, 'argv', ['pose-worker'])
    monkeypatch.setattr(pose_stream_worker.signal, 'signal',
                        lambda number, handler: handlers.update({number: lambda: handler()}))
    try:
        pose_stream_worker.main()
        assert released.is_set(), 'interpreter teardown would race the native callback destructor'
    finally:
        for thread in threads:
            thread.join(1.)


def test_unsubscribe_failure_is_not_success():
    with pytest.raises(RuntimeError, match='unsubscribe'):
        pose_stream_worker._unsubscribe_and_wait(
            SimpleNamespace(unsubscribe=lambda topic: False), '/poses', threading.Event(), .01)


def test_callback_release_timeout_is_not_success():
    with pytest.raises(RuntimeError, match='callback.*release'):
        pose_stream_worker._unsubscribe_and_wait(
            SimpleNamespace(unsubscribe=lambda topic: True), '/poses', threading.Event(), .01)


def test_abort_keeps_native_diagnostic(monkeypatch):
    monkeypatch.setitem(common._GZ_STREAM, 'stop', threading.Event())
    monkeypatch.setitem(common._GZ_STREAM, 'thread', None)
    monkeypatch.setitem(common._GZ_STREAM, 'worker', None)
    monkeypatch.setitem(common._GZ_STREAM, 'worker_rc', -6)
    monkeypatch.setitem(common._GZ_STREAM, 'cb_error',
                        'worker rc=-6: terminate called without an active exception')
    with pytest.raises(RuntimeError, match='terminate called without an active exception'):
        common.stop_gz_pose_stream()
