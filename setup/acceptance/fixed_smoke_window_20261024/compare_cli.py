"""Compare actual old/new CLI admission with synthetic files and no ROS transport."""
import hashlib
import importlib.util
import io
import json
import os
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import sys
import types

REPO=Path(os.environ.get('FLEXCELL_SMOKE_REPO', Path(__file__).resolve().parents[3]))
OUT=Path(os.environ.get('FLEXCELL_SMOKE_OUT') or tempfile.mkdtemp(prefix='flexcell-smoke-cli-'))
OUT.mkdir(parents=True,exist_ok=True)
BASE='071fa1451d07ad2aeb300d176731f2d00d4fa910'
old_source=subprocess.check_output(['git','show',BASE+':setup/94_scenario_runner.py'],cwd=REPO,text=True)
fixture_spec=importlib.util.spec_from_file_location('window_fixture',REPO/'src/flexcell/flexcell_skills/test/test_smoke_window.py')
fixture=importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)

class DispatchBoundary(Exception):
    pass

def module(source,name):
    result=types.ModuleType(name)
    result.__file__=str(REPO/'setup/94_scenario_runner.py')
    exec(compile(source,result.__file__,'exec'),result.__dict__)
    return result

def invoke(source,name,summary):
    runner=module(source,name)
    runner.EPISODE_DIR=str(OUT/(name+'_output'))
    boundary=[]
    def stop_before_transport(*args,**kwargs):
        boundary.append(True)
        raise DispatchBoundary
    runner.run_episode=stop_before_transport
    original=sys.argv
    sys.argv=['runner','--policy','fsm','--stage','baseline','--batch','S1:1',
              '--smoke-summary',str(summary)]
    captured=io.StringIO()
    try:
        with redirect_stdout(captured),redirect_stderr(captured):
            runner.main()
        result=dict(status='UNEXPECTED_RETURN')
    except DispatchBoundary:
        result=dict(status='BASELINE_DISPATCH_BOUNDARY_REACHED')
    except SystemExit as error:
        result=dict(status='ARGUMENT_REJECTED',exit_code=error.code)
    finally:
        sys.argv=original
    (OUT/(name+'.log')).write_text(captured.getvalue())
    return dict(result,transport_boundary_calls=len(boundary),robot_calls=0,model_calls=0)

pool=OUT/'synthetic_pool.jsonl'
rows=[dict(scenario='S1',protocol_sha256=fixture.DIGEST,runtime_fingerprint='runtime',
           policy='fsm',stage='smoke',scenario_exercised=True,harness_error=None,
           outcome='FAILED' if index<2 else 'SUCCEEDED',expected='SUCCEEDED',replay_ok=True)
      for index in range(10)]
fixture.write_rows(pool,rows)
valid,_,_=fixture.make_window(OUT/'synthetic_complete')
duplicate,duplicates,_=fixture.make_window(OUT/'synthetic_duplicate')
for key in ('episode','episode_relative','episode_sha256','evidence_id'):
    duplicates[1][key]=duplicates[0][key]
fixture.write_rows(duplicate,duplicates)
new_source=(REPO/'setup/94_scenario_runner.py').read_text()
results={}
for name,summary in [('pooled_8_success_2_failed',pool),('duplicate_native',duplicate),('complete_window',valid)]:
    results[name]=dict(old=invoke(old_source,'old_'+name,summary),
                       new=invoke(new_source,'new_'+name,summary))
for name in ('pooled_8_success_2_failed','duplicate_native'):
    assert results[name]['old']['status']=='BASELINE_DISPATCH_BOUNDARY_REACHED'
    assert results[name]['new']==dict(status='ARGUMENT_REJECTED',exit_code=2,
                                     transport_boundary_calls=0,robot_calls=0,model_calls=0)
assert results['complete_window']['old']['status']==results['complete_window']['new']['status']=='BASELINE_DISPATCH_BOUNDARY_REACHED'
report=dict(scope='SYNTHETIC_CLI_ADMISSION_ONLY',base_commit=BASE,
            old_runner_sha256=hashlib.sha256(old_source.encode()).hexdigest(),
            source_sha256={name:hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in
                ('setup/94_scenario_runner.py','src/flexcell/flexcell_skills/flexcell_skills/contracts/smoke_window.py')},
            cases=results,robot_calls=0,model_calls=0)
(OUT/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(results,indent=2))
