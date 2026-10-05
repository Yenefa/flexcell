#!/usr/bin/env bash
# Run only from the authoritative WSL workspace; all evidence is persistent.
set -euo pipefail
cd /home/ros/agentic_workcell_ws
out=/home/ros/fc_sync_logs/clef_route_20261006
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
test "$ROS_DOMAIN_ID" = 45
test "$RMW_IMPLEMENTATION" = rmw_cyclonedds_cpp
python3 - "$out" <<'PY'
import hashlib, json, os, shutil, time
from pathlib import Path
from flexcell_skills.confidence_calibration import ConfidenceCalibration, prompt_digest
from flexcell_skills.jev_backends import make_backend
from flexcell_skills.jev_policy import JevPolicy
root = Path(__import__('sys').argv[1])
candidate = root / 'calibration_assembled.json'
final = Path('/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json')
assert not final.exists(), 'Do not overwrite an existing calibration identity'
calibration = ConfidenceCalibration(candidate)
assert calibration.error == '' and calibration.sha256
os.environ['FLEXCELL_JEV_CALIBRATION'] = str(candidate)
policy = JevPolicy(make_backend('clef'))
assert policy.route_eligible(.85)
source = Path('src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py')
assert hashlib.sha256(source.read_bytes()).hexdigest() == prompt_digest()
shutil.copyfile(candidate, final)
final.chmod(0o600)
assert hashlib.sha256(final.read_bytes()).hexdigest() == calibration.sha256
profile = Path('/home/ros/.config/flexcell/mainline_jev.sh')
backup = profile.with_name(profile.name + '.bak_clef_route_' + time.strftime('%Y%m%d_%H%M%S'))
shutil.copy2(profile, backup)
text = profile.read_text()
assert 'export FLEXCELL_JEV_CALIBRATION=' not in text
text = text.replace('# No FLEXCELL_JEV_CALIBRATION on purpose -- see note in the backup header.\n'
                    '# The clef calibration file is absent on this machine and must be regenerated\n'
                    '# here before any run that claims calibrated routing.\n', '')
profile.write_text(text.rstrip() + '\n\n# Locally generated, identity-checked FSM-action calibration (2026-10-06).\n'
                   'export FLEXCELL_JEV_CALIBRATION=' + str(final) + '\n')
result = dict(error=calibration.error, calibration_sha256=calibration.sha256,
              prompt_sha256=prompt_digest(), route_eligible_085=True,
              model=os.environ['FLEXCELL_JEV_MODEL'],
              model_sha256=os.environ['FLEXCELL_JEV_MODEL_SHA256'],
              calibration_file=str(final), profile_backup=str(backup),
              profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(),
              ros_domain_id=int(os.environ['ROS_DOMAIN_ID']),
              rmw_implementation=os.environ['RMW_IMPLEMENTATION'])
(root / 'activation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
PY
set +u
source setup/104_mainline_env.sh
set -u
python3 - <<'PY'
from flexcell_skills.confidence_calibration import ConfidenceCalibration
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.jev_backends import make_backend
c = ConfidenceCalibration()
assert c.error == '' and c.sha256
assert JevPolicy(make_backend('clef')).route_eligible(.85)
print('Reloaded profile: calibration identity and route_eligible(0.85) PASS')
PY
python3 - "$out" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
decisions = Path.home() / '.ros/flexcell/decisions.jsonl'
episodes = Path.home() / '.ros/flexcell/episodes'
(root / 'before_smoke.json').write_text(json.dumps(dict(
    decisions_bytes=decisions.stat().st_size,
    episodes=[str(p) for p in episodes.glob('*.json')]), indent=2) + '\n')
PY
set +e
bash setup/102_mainline_runtime.sh cold hybrid 0.85 > "$out/deploy.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$out/deploy.rc"
set -e
test "$rc" = 0
set +e
bash setup/106_single_live.sh "$out/smoke" > "$out/smoke_runner.log" 2>&1
rc=$?
printf '%s\n' "$rc" > "$out/smoke.rc"
set -e
printf 'Smoke command finished rc=%s; inspect JSON and routing before accepting.\n' "$rc"
