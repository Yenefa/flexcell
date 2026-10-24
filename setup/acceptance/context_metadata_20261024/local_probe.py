"""One bounded CPU metadata probe; no policy execution or robot action."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = Path('/home/ros/.codex/worktrees/2105/flexcell')
OUT = Path(__file__).resolve().parent
RUNTIME = Path('/home/ros/.local/share/flexcell/inference/linux')
EXE = RUNTIME/'llama-b11284/llama-server'
MODEL = RUNTIME/'qwen2.5-1.5b-instruct-q4_k_m.gguf'
PORT = 21881

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            digest.update(part)
    return digest.hexdigest()

def stop_on_signal(signum, frame):
    raise SystemExit('received signal %s' % signum)

for signum in (signal.SIGTERM, signal.SIGINT):
    signal.signal(signum, stop_on_signal)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', PORT))
weights_sha = sha(MODEL)
assert weights_sha == '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'
commands = ['timeout', '--signal=TERM', '--kill-after=5s', '90s', str(EXE),
            '-m', str(MODEL), '-ngl', '0', '-c', '12288', '-np', '1', '-t', '2',
            '--host', '127.0.0.1', '--port', str(PORT), '--alias', 'context-metadata-check',
            '--no-warmup']
receipt = dict(scope='LOCAL_CPU_METADATA_ONLY_NO_POLICY_OR_ROBOT',
               model_sha256=weights_sha, commands=commands,
               source_head=subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
               source_sha256={name:sha(REPO/name) for name in
                   ('setup/102_mainline_runtime.sh', 'setup/runtime_backend_metadata.py')})
process = None
try:
    with (OUT/'server.log').open('wb') as log:
        process = subprocess.Popen(commands, stdout=log, stderr=log, start_new_session=True)
    receipt['owned_process_group'] = process.pid
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic()+45
    while True:
        if process.poll() is not None:
            raise RuntimeError('CPU metadata server exited before readiness')
        try:
            with opener.open('http://127.0.0.1:%s/health' % PORT, timeout=1) as rep:
                assert json.load(rep)['status'] == 'ok'
            break
        except (OSError, urllib.error.URLError):
            if time.monotonic() >= deadline:
                raise RuntimeError('CPU metadata server readiness deadline exceeded')
            time.sleep(.25)
    code = (REPO/'setup/102_mainline_runtime.sh').read_text().split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    config = dict(os.environ, FLEXCELL_JEV_ENDPOINT='http://127.0.0.1:%s/v1/systemone' % PORT,
                  FLEXCELL_JEV_MODEL='context-metadata-check', FLEXCELL_JEV_MODEL_SHA256=weights_sha)
    manifest = OUT/'deployment_fragment_only.json'
    result = subprocess.run([sys.executable, '-c', code, str(manifest), str(REPO), 'jev', '.7',
                             '/home/ros/.local/share/flexcell/pr40_20261024/install'],
                            env=config, capture_output=True, text=True, timeout=15)
    (OUT/'manifest_generation.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, result.stderr
    deployment = json.loads(manifest.read_text())
    assert deployment['manifest_version'] == 2
    assert deployment['server_context_tokens'] == dict(fast=12288, slow=None)
    assert deployment['server_metadata']['fast']['status'] == 'OBSERVED'
    assert deployment['server_metadata']['fast']['selection'] == 'requested_model'
    expected = deployment['runtime_fingerprint']
    for name in ('runtime_fingerprint', 'install', 'head', 'backend_metadata_observations'):
        deployment.pop(name)
    assert hashlib.sha256(json.dumps(deployment, sort_keys=True).encode()).hexdigest() == expected
    deployment['server_context_tokens']['fast'] = 8192
    assert hashlib.sha256(json.dumps(deployment, sort_keys=True).encode()).hexdigest() != expected
    raw = OUT/'fast_models.json'
    receipt.update(status='PASS', observed_context_tokens=12288,
                   runtime_fingerprint=expected, models_response_sha256=sha(raw),
                   manifest_sha256=sha(manifest))
finally:
    if process is not None:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        # Verify that the owned group and its listening socket are gone.
        try:
            os.killpg(process.pid, 0)
            group_gone = False
        except ProcessLookupError:
            group_gone = True
        with socket.socket() as sock:
            listening = sock.connect_ex(('127.0.0.1', PORT)) == 0
        receipt['shutdown'] = dict(process_returncode=process.returncode,
                                   owned_group_absent=group_gone, port_listening=listening)
    (OUT/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
assert receipt['shutdown']['owned_group_absent'] and not receipt['shutdown']['port_listening']
print(json.dumps({key:receipt[key] for key in ('status', 'scope', 'observed_context_tokens', 'shutdown')}, indent=2))
