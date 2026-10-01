#!/usr/bin/env python3
"""Run the SHA-pinned CPU models outside the repository; no paid API calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

BASE = Path.home()/'.local/share/flexcell/inference/linux'
REPO = Path(__file__).resolve().parents[1]
RUNTIME = {'version': 'llama.cpp-b11284-linux-cpu',
           'sha256': 'f53f2534e7ac8df1ef056117d215f1581feb6c426310d6423efac9adcdd5c2c8',
           'url': 'https://github.com/ggml-org/llama.cpp/releases/download/b11284/llama-b11284-bin-ubuntu-x64.tar.gz'}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('install', 'start', 'status', 'stop'))
    args = ap.parse_args()
    assets = json.loads((REPO/'setup/local_inference_assets.json').read_text())
    if args.action == 'install':
        BASE.mkdir(parents=True, exist_ok=True)
        for asset, destination in [(RUNTIME, BASE/'runtime.tar.gz')]+[(assets[a], BASE/assets[a]['file']) for a in ('fast', 'slow')]:
            if destination.exists() and digest(destination) == asset['sha256']:
                continue
            temporary = destination.with_suffix(destination.suffix+'.part')
            with urllib.request.urlopen(asset['url'], timeout=60) as rep, temporary.open('wb') as f:
                for chunk in iter(lambda: rep.read(1024*1024), b''): f.write(chunk)
            if digest(temporary) != asset['sha256']: raise ValueError('download hash mismatch')
            temporary.replace(destination)
        import tarfile
        with tarfile.open(BASE/'runtime.tar.gz') as archive:
            archive.extractall(BASE, filter='data')
        return
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    exe = BASE/'llama-b11284/llama-server'
    for arm, port in [('fast', 18081), ('slow', 18082)]:
        metadata = BASE/(arm+'_server.json')
        saved = json.loads(metadata.read_text()) if metadata.exists() else {}
        pid = saved.get('pid')
        running = pid and Path(f'/proc/{pid}').exists()
        if running and Path(f'/proc/{pid}/exe').resolve() != exe.resolve():
            raise RuntimeError('owned model PID does not match executable')
        if args.action == 'stop':
            if running: os.killpg(pid, signal.SIGTERM)
            continue
        if args.action == 'start' and not running:
            model = BASE/assets[arm]['file']
            assert digest(model) == assets[arm]['sha256']
            assert digest(BASE/'runtime.tar.gz') == RUNTIME['sha256']
            commands = [str(exe), '-m', str(model), '-ngl', '0', '-c', '8192',
                        '-np', '1', '-t', '4', '--host', '127.0.0.1', '--port', str(port),
                        '--alias', 'flexcell-'+arm]
            log = (BASE/(arm+'_server.log')).open('ab')
            process = subprocess.Popen(commands, stdout=log, stderr=log, start_new_session=True)
            log.close()
            saved = {'pid': process.pid, 'model': assets[arm], 'runtime': RUNTIME,
                     'endpoint': f'http://127.0.0.1:{port}/v1/chat/completions',
                     'arguments': commands}
            metadata.write_text(json.dumps(saved, indent=2)+'\n')
        deadline = time.monotonic()+45
        while True:
            try:
                with opener.open(f'http://127.0.0.1:{port}/health', timeout=2) as reply:
                    health = json.load(reply)
                print(json.dumps({'arm': arm, 'health': health, 'model_sha256': assets[arm]['sha256']}))
                if args.action == 'start' and arm == 'fast':
                    config = Path.home()/'.config/flexcell'
                    config.mkdir(parents=True, exist_ok=True)
                    import shlex
                    settings = dict(FLEXCELL_JEV_ENDPOINT=saved['endpoint'], FLEXCELL_JEV_MODEL='flexcell-fast',
                                    FLEXCELL_JEV_MODEL_SHA256=assets['fast']['sha256'], FLEXCELL_JEV_TIMEOUT_S='45',
                                    FLEXCELL_JEV_CALIBRATION=str(config/'jev_calibration_20261002.json'))
                    profile=config/'mainline_jev.sh'
                    profile.write_text('# Local classifier; slow backend remains separately configured.\n'+
                                       ''.join('export %s=%s\n' % (k,shlex.quote(v)) for k,v in settings.items()))
                    profile.chmod(0o600)
                break
            except Exception:
                if args.action != 'start' or time.monotonic() >= deadline: raise
                time.sleep(.5)


if __name__ == '__main__':
    main()
