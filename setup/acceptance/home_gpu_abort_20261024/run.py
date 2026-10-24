import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

root=Path(__file__).resolve().parent
repo=Path('/home/ros/.codex/worktrees/2105/flexcell')
socket='/tmp/flexcell-pr40-home-20261024.sock'
runtime=Path('/home/ros/.local/share/flexcell/pr40_20261024')
stop_event=threading.Event()
started=False
server_channel=None
server_log=None

def decode(data):
    for encoding in ('utf-8-sig','gb18030'):
        try:return data.decode(encoding)
        except UnicodeDecodeError:pass
    return data.decode('utf-8',errors='replace')

def remote(script):
    cmd=['ssh','-S',socket,'-o','BatchMode=yes','-o','ConnectTimeout=10','fuker@100.87.190.44','powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()]
    result=subprocess.run(cmd,capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError('remote command failed: '+decode(result.stderr)[-1500:])
    return json.loads(decode(result.stdout).strip())

def heartbeat():
    while not stop_event.wait(20):
        try:remote("(Get-Item 'F:\\flexcell-models\\pr40-20261024-01a169ef-batch5\\heartbeat.txt').LastWriteTimeUtc=[DateTime]::UtcNow; '{}' ")
        except Exception as exc:
            with (root/'heartbeat_errors.log').open('a') as stream:stream.write(str(exc)+'\n')

def local(script,log,timeout):
    env=dict(os.environ,FLEXCELL_MAINLINE_ROOT=str(runtime),FLEXCELL_INSTALL=str(runtime/'install'),FLEXCELL_JEV_ENV=str(root/'profile.sh'))
    with (root/log).open('w') as output:
        process=subprocess.Popen(['bash','-c',script],cwd=repo,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        try:return process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL)
            raise

status={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'planned':{'S4':2,'S5':2,'S1':1}}
try:
    identity=json.loads((root/'identity.json').read_text().lstrip('\ufeff'))
    assert identity['weights']['sha256']=='8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9'
    forwarding=['ssh','-S',socket,'-O','forward','-L','127.0.0.1:21435:127.0.0.1:11435','fuker@100.87.190.44']
    subprocess.run(forwarding,check=True,capture_output=True)
    cmd=['ssh','-S',socket,'-o','BatchMode=yes','fuker@100.87.190.44','powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode((root/'start.ps1').read_text().encode('utf-16le')).decode()]
    server_log=(root/'ssh_session.log').open('wb')
    server_channel=subprocess.Popen(cmd,stdout=server_log,stderr=subprocess.STDOUT)
    for attempt in range(20):
        if server_channel.poll() is not None:raise RuntimeError('foreground GPU session exited during startup')
        time.sleep(.5)
        try:
            owner=remote("[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); Get-Content 'F:\\flexcell-models\\pr40-20261024-01a169ef-batch5\\owner.json' -Raw")
            break
        except Exception:
            if attempt==19:raise
    started=True
    (root/'owner.json').write_text(json.dumps(owner,indent=2,ensure_ascii=False)+'\n')
    print('HOME_GPU_STARTED pid='+str(owner['pid']),flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(90):
        if server_channel.poll() is not None:raise RuntimeError('GPU session exited before readiness')
        try:
            with opener.open('http://127.0.0.1:21435/health',timeout=3) as response:
                health=json.load(response)
            if health.get('status')=='ok':break
        except Exception:pass
        time.sleep(2)
    else:raise RuntimeError('home inference endpoint did not become healthy')
    shared_read="""$s=[IO.File]::Open('F:\\flexcell-models\\pr40-20261024-01a169ef-batch5\\stderr.log',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite); try { $m=New-Object IO.MemoryStream; $s.CopyTo($m); @{data_b64=[Convert]::ToBase64String($m.ToArray())} | ConvertTo-Json -Compress } finally { $s.Dispose() }"""
    log=decode(base64.b64decode(remote(shared_read)['data_b64']))
    (root/'model_startup.log').write_text(log)
    if not re.search(r'offload.*layers.*GPU',log,re.IGNORECASE):raise RuntimeError('GPU offload not confirmed by model log')
    status['model_gpu_offload_confirmed']=True
    print('HOME_GPU_READY weights_and_offload_confirmed',flush=True)
    cold_rc=local('bash setup/102_mainline_runtime.sh cold jev','cold.log',300)
    status['cold_rc']=cold_rc
    print('COLD_RC='+str(cold_rc),flush=True)
    if cold_rc:raise RuntimeError('cold startup failed; no episodes started')
    deployments=sorted((runtime/'runtime').glob('*/deployment.json'))
    deployment=deployments[-1]
    (root/'deployment.json').write_bytes(deployment.read_bytes())
    strict_rc=local('source setup/104_mainline_env.sh && python3 setup/flexcell_admin.py health','health.log',60)
    status['health_rc']=strict_rc
    if strict_rc:raise RuntimeError('strict health failed; no episodes started')
    before={str(p) for p in Path('/home/ros/.ros/flexcell/episodes').glob('batch_*.jsonl')}
    rc=local('source setup/104_mainline_env.sh && python3 setup/94_scenario_runner.py --stage smoke --policy jev --batch S4:2 S5:2 S1:1','batch.log',1800)
    status['batch_rc']=rc
    after={str(p) for p in Path('/home/ros/.ros/flexcell/episodes').glob('batch_*.jsonl')}
    status['new_batches']=sorted(after-before)
    print('BATCH_RC='+str(rc),flush=True)
except BaseException as exc:
    status['error']=str(exc)
    print('RUN_ERROR: '+str(exc),flush=True)
finally:
    if started:
        try:
            shutdown=remote((root/'stop.ps1').read_text())
            (root/'shutdown.json').write_text(json.dumps(shutdown,indent=2,ensure_ascii=False)+'\n')
            status['shutdown']=shutdown
            print('HOME_GPU_EXITED='+str(shutdown['exited']),flush=True)
        except Exception as exc:
            status['shutdown_error']=str(exc)
            print('SHUTDOWN_ERROR: '+str(exc),flush=True)
        stop_event.set()
        try:
            logs=remote("@{stdout=[Convert]::ToBase64String([IO.File]::ReadAllBytes('F:\\flexcell-models\\pr40-20261024-01a169ef-batch5\\stdout.log'));stderr=[Convert]::ToBase64String([IO.File]::ReadAllBytes('F:\\flexcell-models\\pr40-20261024-01a169ef-batch5\\stderr.log'))} | ConvertTo-Json -Compress")
            for key,value in logs.items(): (root/('server_'+key+'.log')).write_bytes(base64.b64decode(value))
        except Exception as exc:status['log_copy_error']=str(exc)
        try:status['local_stop_rc']=local('source setup/104_mainline_env.sh && bash setup/flexcell stop','local_stop.log',90)
        except Exception as exc:status['local_stop_error']=str(exc)
    if server_channel is not None:
        try:server_channel.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server_channel.terminate()
            server_channel.wait(timeout=10)
    if server_log is not None:server_log.close()
    subprocess.run(['ssh','-S',socket,'-O','cancel','-L','127.0.0.1:21435:127.0.0.1:11435','fuker@100.87.190.44'],capture_output=True)
    (root/'run_status.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(status,ensure_ascii=False),flush=True)
