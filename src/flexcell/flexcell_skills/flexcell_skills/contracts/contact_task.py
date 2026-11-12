"""Executor checks for the opt-in ContactPush component."""
import math


def returned_component_ready(component):
    return (type(component.get('stroke_outcome')) is int and component['stroke_outcome']==0
        and type(component.get('stroke_error_code')) is int and component['stroke_error_code']==0
        and all(component.get(k) is True for k in ('motion_terminal_known','return_completed',
            'arm_ready','has_returned_state','physical_contact_observed','returned_gripper_known','returned_objects_complete'))
        and component.get('returned_source')=='SIMULATION_GROUND_TRUTH'
        and component.get('returned_frame')=='world' and component.get('returned_carry_engaged') is False
        and component.get('child_goal_uuid')==component.get('goal_uuid')
        and type(component.get('request_id')) is str and bool(component['request_id'])
        and component.get('request_id')==component.get('receipt_request_id')
        and type(component.get('receipt_age_s')) in (int,float)
        and math.isfinite(component['receipt_age_s']) and 0<=component['receipt_age_s']<=.25
        and type(component.get('returned_object_age_s')) in (int,float)
        and math.isfinite(component['returned_object_age_s']) and 0<=component['returned_object_age_s']<=.5)
