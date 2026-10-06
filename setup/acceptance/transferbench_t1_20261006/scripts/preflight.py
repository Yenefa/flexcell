from pathlib import Path
import hashlib,json,os,socket,subprocess
from urllib.parse import urlparse
from flexcell_skills.confidence_calibration import ConfidenceCalibration,prompt_digest
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.jev_backends import ClefBackend
out=Path('/home/ros/fc_sync_logs/transferbench_t1_20261006')
cal=ConfidenceCalibration()
policy=JevPolicy(ClefBackend())
endpoint=urlparse(os.environ['FLEXCELL_JEV_ENDPOINT'])
try:
    with socket.create_connection((endpoint.hostname,endpoint.port or 80),timeout=3): pass
    tcp=True
except OSError as exc:
    tcp=False
budget_path=os.environ.get('FLEXCELL_LLM_BUDGET_FILE')
budget=json.loads(Path(budget_path).read_text()) if budget_path else None
owners={}
for name in ['gazebo','moveit','move_to_pose','fleet']:
    file=Path('/tmp/flexcell_lifecycle/pids')/(name+'.pid')
    try:
        pid=int(file.read_text())
        os.kill(pid,0)
        owners[name]=dict(pid=pid,alive=True)
    except (OSError,ValueError): owners[name]=dict(alive=False)
result=dict(ros_domain_id=os.environ.get('ROS_DOMAIN_ID'),rmw=os.environ.get('RMW_IMPLEMENTATION'),dds=os.environ.get('CYCLONEDDS_URI'),calibration_error=cal.error,calibration_sha256=cal.sha256,prompt_sha256=prompt_digest(),route_eligible=policy.route_eligible(.85),gpu_tcp_reachable=tcp,owned_stack=owners,clock_authority=subprocess.run(['systemctl','is-active','systemd-timesyncd.service'],capture_output=True,text=True).stdout.strip(),budget=dict(limit_microyuan=budget['limit_microyuan'],committed_upper_bound_microyuan=budget.get('committed_upper_bound_microyuan'),calls=len(budget['calls'])) if budget else None)
result['ok']=result['ros_domain_id']=='45' and not cal.error and tcp and result['route_eligible'] and all(row['alive'] for row in owners.values())
(out/'preflight_attempt01.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
