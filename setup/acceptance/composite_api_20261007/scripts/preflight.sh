#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
from flexcell_skills.confidence_calibration import ConfidenceCalibration,prompt_digest
from flexcell_interfaces.action import RunComposite
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.jev_backends import make_backend
c=ConfidenceCalibration();p=JevPolicy(make_backend('clef'))
assert c.error=='' and c.sha256=='34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c' and p.route_eligible(.85)
assert prompt_digest()=='b37e71cd0b9b0ff81cfa3638111da8375251be2fadeabc01468ce46b5f4e85b8'
assert os.environ['ROS_DOMAIN_ID']=='45' and '100.87.190.44' in os.environ.get('no_proxy','')
src=Path('/home/ros/agentic_workcell_ws/src/flexcell/flexcell_skills/flexcell_skills');dest=Path('/home/ros/.local/share/flexcell/mainline/install/flexcell_skills/lib/python3.12/site-packages/flexcell_skills')
assert all((dest/p.relative_to(src)).read_bytes()==p.read_bytes() for p in src.rglob('*.py'))
fleet=Path('/home/ros/.local/share/flexcell/mainline/runtime/20261007_001918/fleet.log').read_text();assert "jev backend 'clef' unavailable" not in fleet and 'startup:' in fleet
record={'ok':True,'calibration_error':c.error,'calibration_sha256':c.sha256,'route_eligible_085':True,'prompt_sha256':prompt_digest(),'ros_domain_id':45,'no_proxy_literal_present':True,'new_action_type':RunComposite.__name__,'installed_source_identical':True,'startup_backend_unavailable_warning':False}
p=Path('/home/ros/agentic_workcell_ws/setup/acceptance/composite_api_20261007/validation/preflight.json');p.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
PY
