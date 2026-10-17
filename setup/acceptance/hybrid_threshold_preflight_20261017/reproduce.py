"""Synthetic missing-threshold counterexample. Never call ROS or a model."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types

BASE = 'c79e0c672c95e2d9cd04112ef42b65e4c67e1845'
ROOT = Path(__file__).resolve().parents[3]


def probe(source):
    module = types.ModuleType('threshold_probe')
    module.__file__ = str(ROOT / 'setup/94_scenario_runner.py')
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    reached = []

    class TransportReached(Exception):
        pass

    def forbidden_transport(*args, **kwargs):
        reached.append('offline sentinel only')
        raise TransportReached

    module.run_episode = forbidden_transport
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        manifest = root / 'deployment.json'
        manifest.write_text(json.dumps(dict(policy='hybrid', runtime_fingerprint='runtime',
            active_backends=dict(fast=dict(model='q8', model_sha256='weights',
                                           calibration_sha256='cal')))))
        module.EPISODE_DIR = str(root / 'episodes')
        previous = sys.argv
        sys.argv = ['runner', '--policy', 'hybrid', '--batch', 'S1:1', '--deployment', str(manifest)]
        stderr, stdout = io.StringIO(), io.StringIO()
        result = {}
        try:
            with redirect_stderr(stderr), redirect_stdout(stdout):
                try:
                    module.main()
                except TransportReached:
                    result['terminal'] = 'REACHED_OFFLINE_TRANSPORT_SENTINEL'
                except SystemExit as error:
                    result.update(terminal='ARGUMENT_REJECTED', exit_code=error.code)
        finally:
            sys.argv = previous
        result.update(reached_dispatch_boundary=bool(reached),
                      threshold_error='finite numeric threshold' in stderr.getvalue(),
                      robot_dispatch='NOT_RUN', model_calls='NOT_RUN')
        return result


if __name__ == '__main__':
    before = subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE + ':setup/94_scenario_runner.py'], text=True)
    after = (ROOT / 'setup/94_scenario_runner.py').read_text()
    report = dict(record_kind='SYNTHETIC_TRANSPORT_COUNTEREXAMPLE', source_base=BASE,
                  before=probe(before), after=probe(after))
    print(json.dumps(report, indent=2))
    assert report['before']['reached_dispatch_boundary'] is True
    assert report['after']['reached_dispatch_boundary'] is False
    assert report['after']['exit_code'] == 2 and report['after']['threshold_error']
