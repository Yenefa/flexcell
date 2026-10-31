"""Read-only inventory; never normalize or restore the old WSL checkout."""
import hashlib
import json
from pathlib import Path
import subprocess

repo=Path('/home/ros/agentic_workcell_ws')
out=repo/'artifacts/preposition-world-20261031'
def git(*args):
    return subprocess.check_output(['git','-C',str(repo),'-c','core.filemode=false',*args],stderr=subprocess.DEVNULL)
patch=git('diff','--binary')
(out/'old-wsl-dirty.patch').write_bytes(patch)
status=git('status','--porcelain=v1','-z')
(out/'old-wsl-status.bin').write_bytes(status)
dirty=git('diff','--name-only','--ignore-space-at-eol').decode().splitlines()
process=subprocess.run(['pgrep','-af','[g]z sim|[m]ove_group|[m]tc_planner|[c]arry_server|[r]ecord_sim_data'],text=True,capture_output=True)
assert process.returncode==1,process.stdout
identity={'old_head':git('rev-parse','HEAD').decode().strip(),'old_branch':git('branch','--show-current').decode().strip(),
          'substantively_modified':dirty,'dirty_patch_sha256':hashlib.sha256(patch).hexdigest(),
          'tracked_files_present':len(git('ls-files','-z').split(b'\0'))-1,
          'untracked_paths':len(git('ls-files','--others','--exclude-standard','-z').split(b'\0'))-1,
          'running_simulation_processes':0,
          'preservation':'No restore, clean, reset, normalization, merge or build in this checkout.'}
(out/'old-wsl-preflight.json').write_text(json.dumps(identity,indent=2)+'\n')
print(json.dumps(identity,indent=2))
