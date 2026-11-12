"""Versioned post-return receipt. Stroke, return and arm readiness stay separate."""
from dataclasses import asdict,dataclass
import math
import time
from flexcell_skills.contracts import push


@dataclass(frozen=True)
class ReturnedState:
    source: str
    frame: str
    source_age_s: float
    arm_quiet: bool
    object_stable: bool
    carry_disengaged: bool
    gripper_state_known: bool
    tool_clearance_m: float
    protected_excursion_m: float
    position: tuple
    revision: int
    source_stamp_ns: int
    observed_monotonic_ns: int

    def usable(self,now_monotonic_ns=None,now_sim_ns=None):
        values=[self.source_age_s,self.tool_clearance_m,self.protected_excursion_m,*self.position]
        now_monotonic_ns=time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        return (self.source=='SIMULATION_GROUND_TRUTH' and self.frame=='world'
                and len(self.position)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in values)
                and 0<=self.source_age_s<=.5 and self.arm_quiet is True and self.object_stable is True
                and self.carry_disengaged is True and self.gripper_state_known is True
                and self.tool_clearance_m>=.055 and 0<=self.protected_excursion_m<=.005
                and type(self.revision) is int and self.revision>=0
                and type(self.observed_monotonic_ns) is int and self.observed_monotonic_ns>0
                and 0<=now_monotonic_ns-self.observed_monotonic_ns<=250_000_000
                and type(self.source_stamp_ns) is int and self.source_stamp_ns>=0
                and (now_sim_ns is None or 0<=now_sim_ns-self.source_stamp_ns<=500_000_000))


@dataclass(frozen=True)
class ContactReceipt:
    request_id: str
    primitive_outcome: str
    primitive_error_code: int
    stroke_signed_m: float | None
    requested_m: float
    physical_contact_observed: bool | None
    motion_terminal_known: bool
    return_completed: bool
    canceled: bool
    post_return: ReturnedState | None
    attempt_start: tuple

    def __post_init__(self):
        if (not isinstance(self.request_id,str) or not self.request_id
                or self.primitive_outcome not in ('SUCCEEDED','FAILED','CANCELED','STATE_UNKNOWN','NOT_EXECUTED')
                or type(self.primitive_error_code) is not int or self.primitive_error_code<0
                or type(self.requested_m) not in (int,float) or not math.isfinite(self.requested_m)
                or not .01<=self.requested_m<=.15 or len(self.attempt_start)!=3
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in self.attempt_start)
                or self.stroke_signed_m is not None and (type(self.stroke_signed_m) not in (int,float)
                                                       or not math.isfinite(self.stroke_signed_m))
                or any(type(v) is not bool for v in (self.motion_terminal_known,self.return_completed,self.canceled))
                or self.physical_contact_observed is not None and type(self.physical_contact_observed) is not bool):
            raise ValueError('invalid contact receipt')
        if self.primitive_outcome=='SUCCEEDED' and self.physical_contact_observed is not True:
            raise ValueError('stroke success requires independently observed contact')

    @property
    def arm_ready(self):
        return (self.motion_terminal_known is True and self.return_completed is True
                and self.canceled is False and self.post_return is not None and self.post_return.usable())

    def to_dict(self):
        result=asdict(self)
        net=None
        geometry=None
        if self.post_return is not None and len(self.attempt_start)==3:
            # This adapter's supported development direction is explicitly -x.
            net=float(self.attempt_start[0]-self.post_return.position[0])
        if self.arm_ready:
            metrics,_=push.contact_metrics(list(self.attempt_start),list(self.post_return.position),[-1.,0.,0.])
            geometry=(metrics is not None
                      and abs(metrics['displacement_m']-self.requested_m)<=push.DEFAULTS['displacement_tolerance_m']
                      and metrics['direction_cos']>=push.DEFAULTS['direction_cos_min']
                      and metrics['lateral_m']<=push.DEFAULTS['lateral_max_m']
                      and abs(metrics['delta_z_m'])<=push.DEFAULTS['delta_z_max_m'])
        result.update(schema_version='contact-push-receipt/1',arm_ready=self.arm_ready,
                      clock_domain='ROS_SIM_TIME',monotonic_clock_scope='same_host',
                      direction=[-1.,0.,0.],
                      returned_signed_m=net,
                      return_loss_m=(self.stroke_signed_m-net if net is not None and self.stroke_signed_m is not None else None),
                      progress_preserved=(self.stroke_signed_m-net<=.005 if self.arm_ready and net is not None and self.stroke_signed_m is not None else None),
                      returned_request_geometry_satisfied=geometry,
                      independent_acceptance_claim=False)
        return result


def ready_for_next(value,now_sim_ns,current_world_revision,now_monotonic_ns=None):
    """Consumers re-check freshness/revision; a latched arm_ready bit is not authority."""
    try:
        if (value['schema_version']!='contact-push-receipt/1'
                or value['clock_domain']!='ROS_SIM_TIME'
                or value['motion_terminal_known'] is not True or value['return_completed'] is not True
                or value['canceled'] is not False or not isinstance(value['post_return'],dict)):
            return False
        post=ReturnedState(**value['post_return'])
        return (type(current_world_revision) is int and current_world_revision==post.revision
                and post.usable(now_monotonic_ns,now_sim_ns))
    except (KeyError,TypeError,ValueError):return False
