"""A real crashing child must never produce a successful admin result."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def test_native_sigsegv_after_success_is_rejected(monkeypatch, capsys):
    path=Path(__file__).resolve().parents[4]/'setup/flexcell_admin.py'
    spec=importlib.util.spec_from_file_location('admin_exit_test', path)
    admin=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admin)
    real_popen=subprocess.Popen
    code="import json,os,signal,resource; resource.setrlimit(resource.RLIMIT_CORE,(0,0)); print(json.dumps({'ok':True}),flush=True); os.kill(os.getpid(),signal.SIGSEGV)"
    def crash(_args, **kwargs):
        return real_popen([sys.executable, '-c', code], **kwargs)
    monkeypatch.setattr(admin.subprocess, 'Popen', crash)
    monkeypatch.setattr(sys, 'argv', [str(path),'reset'])
    assert admin.main()==1
    result=json.loads(capsys.readouterr().out)
    assert result['ok'] is False and result['worker_rc']==-11
