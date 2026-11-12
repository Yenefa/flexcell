"""Bounded public-instruction push planner using live measured positions.

This is a deterministic rule policy, not a language-model or learning claim.
It supports an unambiguous object name/colour and one named/unique goal region.
"""
import math
import re
from runtime.planner.public_observation import assert_public


class PushTaskRejected(ValueError):pass


def _word(text,value):
    return re.search(r'(?<![\w])'+re.escape(value.casefold())+r'(?![\w])',text) is not None


def resolve_goal(public):
    assert_public(public)
    instruction=public['instruction'].casefold()
    match=re.search(r'\bpush\s+(?:the\s+)?(.+?)\s+(?:into|to)\b',instruction)
    if not match:raise PushTaskRejected('unsupported instruction: an explicit push target is required')
    phrase=re.sub(r'\b(block|box|object)\b','',match.group(1)).strip()
    candidates=[obj for obj in public['objects']
                if _word(phrase,obj['name']) or obj.get('color') and _word(phrase,obj['color'])]
    if len(candidates)!=1:raise PushTaskRejected('push target is missing or ambiguous')
    target=candidates[0]['name']
    for negative in re.findall(r'(?:do not|don.t)\s+move\s+([^.;]+)',instruction):
        if _word(negative,target) or candidates[0].get('color') and _word(negative,candidates[0]['color']):
            raise PushTaskRejected('the selected push target is also protected by the instruction')
    zones=[zone for zone in public['zones'] if _word(instruction,zone['name'])]
    if not zones and len(public['zones'])==1:zones=list(public['zones'])
    if len(zones)!=1:raise PushTaskRejected('destination region is missing or ambiguous')
    zone=zones[0]
    if len(zone['pose'])!=3 or not all(math.isfinite(float(v)) for v in zone['pose']):
        raise PushTaskRejected('invalid public goal region')
    radius=float(zone['radius'])
    if not math.isfinite(radius) or radius<=.005:raise PushTaskRejected('unsupported goal radius')
    return dict(target=target,zone=zone,preserve=sorted(o['name'] for o in public['objects'] if o['name']!=target))


def plan(public,world,capabilities):
    goal=resolve_goal(public)
    if capabilities.get('push_backend') not in ('legacy','finger_tcp'):
        raise PushTaskRejected('no registered push capability')
    if world.get('source')!='SIMULATION_GROUND_TRUTH' or world['header']['frame_id']!='world' or world['carry']['engaged']:
        raise PushTaskRejected('a fresh world-frame observation with released carry is required')
    expected={obj['name'] for obj in public['objects']};objects=world['objects']
    if {o['name'] for o in objects}!=expected or len(objects)!=len(expected):
        raise PushTaskRejected('public and measured object registries disagree')
    positions={}
    for obj in objects:
        if not obj['available'] or not 0<=obj['pose_age_s']<=.5:raise PushTaskRejected('object measurement unavailable or stale')
        p=obj['pose']['position'];position=[p['x'],p['y'],p['z']]
        if not all(math.isfinite(v) for v in position):raise PushTaskRejected('non-finite measured pose')
        positions[obj['name']]=position
    budget=public.get('execution_budget') or {}
    steps=budget.get('max_steps');wall=budget.get('max_wall_s')
    if type(steps) is not int or steps<1 or type(wall) not in (int,float) or not math.isfinite(wall) or wall<=0:
        raise PushTaskRejected('an explicit finite task budget is required')
    motion_budget=min(steps,int(capabilities['motion_budget']))
    maximum=min(8,motion_budget//13)
    start=positions[goal['target']];zone=goal['zone'];count=None
    for n in range(1,maximum+1):
        predicted=[start[0]-.03*n,start[1],start[2]]
        if math.dist(predicted,zone['pose'])<=zone['radius']-.005:count=n;break
    if count is None:raise PushTaskRejected('goal cannot be reached with the registered direction, primitive and budget')
    return dict(scenario_id=public.get('task_id','public-push-task'),initial_objects=positions,
        stages=[dict(stage_id='push_%02d'%i,object_name=goal['target'],action=1,
                     direction=[-1.,0.,0.],distance_m=.03) for i in range(count)],
        final_empty_positions=[],position_tolerance_m=.005,clearance_m=.05,
        motion_profile_id='demo_veryslow'),goal,dict(max_motion_goals=motion_budget,
        max_wall_s=min(float(wall),float(capabilities['wall_s'])))


def goal_satisfied(goal,initial,world):
    if world.get('source')!='SIMULATION_GROUND_TRUTH' or world['carry']['engaged']:return False
    positions={}
    for obj in world['objects']:
        if not obj['available'] or not 0<=obj['pose_age_s']<=.5:return False
        p=obj['pose']['position'];positions[obj['name']]=[p['x'],p['y'],p['z']]
    if goal['target'] not in positions:return False
    return (math.dist(positions[goal['target']],goal['zone']['pose'])<=goal['zone']['radius']
            and all(n in positions and math.dist(positions[n],initial[n])<=.005 for n in goal['preserve']))
