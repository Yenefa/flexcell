"""Misleading EXPECT text must not authorize a failed regression process."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('observed,code,passes', [
    ('False', 6, False), ('True', 6, False), ('', 0, False), ('True', 0, True),
])
def test_regression_requires_observed_motion_and_zero_process_exit(tmp_path, observed, code, passes):
    if os.name != 'posix' or not shutil.which('bash'):
        pytest.skip('Linux acceptance shell')
    repo = Path(__file__).resolve().parents[4]
    setup = tmp_path / 'setup'
    setup.mkdir()
    for name in ('32_day2_acceptance.sh', 'lib_gate.sh'):
        shutil.copyfile(repo / 'setup' / name, setup / name)
    install = tmp_path / 'install'
    install.mkdir()
    (install / 'setup.bash').write_text('')
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    pgrep = fake_bin / 'pgrep'
    pgrep.write_text('#!/bin/sh\nexit 0\n')
    pgrep.chmod(0o755)
    (tmp_path / 'plan_execute.py').write_text(
        "import sys\nprint('PLAN error_code = 1')\nprint('EXECUTE error_code = 1')\nprint('RC=0')\n" +
        ("print('MOTION_DETECTED = %s')\n" % observed if observed else '') +
        'sys.exit(%d)\n' % code)
    result = subprocess.run(['bash', str(setup / '32_day2_acceptance.sh'), 'regression'],
        capture_output=True, text=True, env=dict(os.environ,
            PATH=str(fake_bin) + ':' + os.environ['PATH'],
            FLEXCELL_WS=str(tmp_path), FLEXCELL_STAGE=str(tmp_path / 'evidence')))
    assert 'EXPECT:' in result.stdout  # the misleading old positive text remains present
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
