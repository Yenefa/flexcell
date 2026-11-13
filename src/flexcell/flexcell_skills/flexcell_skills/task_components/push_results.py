"""Pure push-result adapters. No ROS client, arm ownership or budget mutation."""
import json

from flexcell_skills.contracts.contact_task import returned_component_ready


def legacy_push_result(skill_result, context, request_id, terminal_status, goal_uuid):
    final = dict(
        goal_uuid=goal_uuid,
        outcome=str(int(skill_result.outcome)),
        error_code=int(skill_result.error_code))
    return dict(
        context,
        terminal_status=terminal_status,
        outcome=int(skill_result.outcome),
        error_code=int(skill_result.error_code),
        detail=skill_result.detail,
        run_id=getattr(skill_result, 'run_id', '') or request_id,
        evidence_id=getattr(skill_result, 'evidence_id', ''),
        displacement_m=float(skill_result.displacement_m),
        direction_cos=float(skill_result.direction_cos),
        lateral_m=float(skill_result.lateral_m),
        delta_z_m=float(skill_result.delta_z_m),
        contact_made=bool(skill_result.contact_made),
        contact_lost=bool(skill_result.contact_lost),
        carry_engaged_during=bool(skill_result.carry_engaged_during),
        final_state=final)


def contact_push_result(reply, context, initial_objects, remaining_budget, goal_uuid, monotonic_ns):
    ws=reply.returned_state
    receipt={}
    try:receipt=json.loads(reply.receipt_json)
    except (ValueError,TypeError):pass
    component=dict(context,child_goal_uuid=reply.goal_uuid,receipt_request_id=receipt.get('request_id'),
        outcome=int(reply.outcome),error_code=int(reply.error_code),detail=reply.detail,
        evidence_id=reply.evidence_id,displacement_m=float(reply.displacement_m),
        direction_cos=float(reply.direction_cos),lateral_m=float(reply.lateral_m),delta_z_m=float(reply.delta_z_m),
        contact_made=bool(reply.contact_made),contact_lost=bool(reply.contact_lost),
        carry_engaged_during=bool(reply.carry_engaged_during),stroke_outcome=int(reply.stroke_outcome),
        stroke_error_code=int(reply.stroke_error_code),motion_terminal_known=bool(reply.motion_terminal_known),
        return_completed=bool(reply.return_completed),arm_ready=bool(reply.arm_ready),
        has_returned_state=bool(reply.has_returned_state),physical_contact_observed=bool(reply.physical_contact_observed),
        returned_source=ws.source,returned_frame=ws.header.frame_id,returned_carry_engaged=bool(ws.carry.engaged),
        returned_gripper_known=bool(ws.robot.has_gripper_state),
        returned_objects_complete=({o.name for o in ws.objects}==set(initial_objects) and all(o.available for o in ws.objects)),
        returned_object_age_s=max((o.pose_age_s for o in ws.objects),default=float('inf')),
        receipt_age_s=(monotonic_ns()-int(reply.observed_monotonic_ns))/1e9,
        motion_goals_used=int(reply.motion_goals_used))
    if not reply.motion_terminal_known:
        component.update(outcome=3,error_code=33,detail='contact motion terminal is unknown')
    elif component['outcome']==0 and (not returned_component_ready(component) or remaining_budget<0):
        component.update(outcome=1,error_code=62,detail='contact success lacks a fresh known ready return or budget')
    component['terminal_status']='SUCCEEDED' if component['outcome']==0 else 'CANCELED' if component['outcome']==2 else 'FAILED'
    component['final_state']=dict(goal_uuid=goal_uuid,error_code=component['error_code'])
    return component
