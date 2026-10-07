#!/usr/bin/env python3
"""One registered malformed-chain control request. No local prepare_plan bypass in product CLI."""
import json
from pathlib import Path
import sys
import uuid
import rclpy
from rclpy.action import ActionClient
from flexcell_interfaces.action import RunComposite
from flexcell_interfaces.msg import ObjectPosition,CompositeStage
from geometry_msgs.msg import Point
from unique_identifier_msgs.msg import UUID
from flexcell_skills.contracts.receipt_json import loads


def main():
    p=loads(Path(sys.argv[1]).read_text());g=RunComposite.Goal();g.scenario_id=p['scenario_id'];g.motion_profile_id=p['motion_profile_id']
    g.position_tolerance_m=p['position_tolerance_m'];g.clearance_m=p['clearance_m']
    for name,xyz in p['initial_objects'].items():
        o=ObjectPosition();o.object_name=name;o.position.x,o.position.y,o.position.z=map(float,xyz);g.initial_objects.append(o)
    for stage in p['stages']:
        s=CompositeStage();s.stage_id=stage['stage_id'];s.object_name=stage['object_name'];s.place_pose.header.frame_id='world';s.place_pose.pose.orientation.w=1.
        s.place_pose.pose.position.x,s.place_pose.pose.position.y,s.place_pose.pose.position.z=map(float,stage['destination']);g.stages.append(s)
    for xyz in p['final_empty_positions']:
        pt=Point();pt.x,pt.y,pt.z=map(float,xyz);g.final_empty_positions.append(pt)
    rclpy.init();node=rclpy.create_node('prebatch_invalid_control');gid=uuid.uuid4().hex
    try:
        client=ActionClient(node,RunComposite,'/run_composite')
        if not client.wait_for_server(timeout_sec=5):raise RuntimeError('composite unavailable')
        sf=client.send_goal_async(g,goal_uuid=UUID(uuid=list(bytes.fromhex(gid))));rclpy.spin_until_future_complete(node,sf,timeout_sec=5)
        if not sf.done() or not sf.result() or not sf.result().accepted:raise RuntimeError('acceptance unknown/rejected')
        rf=sf.result().get_result_async();rclpy.spin_until_future_complete(node,rf,timeout_sec=15)
        if not rf.done() or not rf.result():raise RuntimeError('terminal unknown')
        value=rf.result();r=value.result
        record=dict(goal_uuid=gid,action_status=int(value.status),outcome_val=int(r.outcome),error_code_val=int(r.error_code),run_id=r.run_id,evidence_id=r.evidence_id,detail=r.detail,component_run_ids=list(r.component_run_ids))
        print('RESULT '+json.dumps(record),flush=True)
        return 0 if value.status==5 and r.outcome==1 and r.error_code==60 and not r.component_run_ids else 2
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':raise SystemExit(main())
