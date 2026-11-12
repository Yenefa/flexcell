"""Instantiate declared initial object poses BEFORE launch; never mutate live state.

Only existing same-size box models are supported. Missing models, changed shapes,
relative frames and invalid numbers are refused. No goal/answer fields are read.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


class LayoutError(ValueError):
    pass


def _numbers(value, length):
    if (not isinstance(value, (list, tuple)) or len(value) != length
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in value)):
        raise LayoutError('expected %d finite numeric coordinates' % length)
    return [float(v) for v in value]


def _objects(objects):
    if not isinstance(objects, list) or not objects:
        raise LayoutError('a nonempty public object list is required')
    result = {}
    for obj in objects:
        name = obj.get('name') if isinstance(obj, dict) else None
        if not isinstance(name,str) or not name or name in result:
            raise LayoutError('missing or duplicate object name')
        result[name] = _numbers(obj.get('initial_pose'),4)
    return result


def _nonpose_digest(tree, names):
    root = copy.deepcopy(tree.getroot())
    world = root.find('world')
    for model in world.findall('model'):
        if model.get('name') in names:
            model.find('pose').text = '$DECLARED_INITIAL_POSE'
    return hashlib.sha256(ET.tostring(root,encoding='utf-8')).hexdigest()


def materialize(source, destination, objects):
    """Write a new world differing only in tracked model root initial poses.

    Does not overwrite source/output or synthesize models, masses, friction,
    shapes, constraints, answers or success thresholds.
    """
    source,destination = Path(source),Path(destination)
    expected = _objects(objects)
    tree = ET.parse(source)
    world = tree.getroot().find('world')
    if world is None:
        raise LayoutError('exactly one SDF world is required')
    if len(tree.getroot().findall('world')) != 1:
        raise LayoutError('exactly one SDF world is required')
    models = {}
    for model in world.findall('model'):
        name = model.get('name')
        if name in models:
            raise LayoutError('duplicate world model: '+str(name))
        models[name] = model
    for obj in objects:
        name = obj['name']
        if name not in models:
            raise LayoutError('declared object has no existing model: '+name)
        model = models[name]
        pose = model.find('pose')
        if pose is None or pose.attrib or any(p.get('relative_to') for p in model.iter('pose')):
            raise LayoutError('only explicit unframed model poses are supported: '+name)
        if (model.findtext('static','false').strip().lower() in ('true','1')
                or model.find('include') is not None or model.find('joint') is not None):
            raise LayoutError('static/included/articulated object is unsupported: '+name)
        sizes = model.findall('link/collision/geometry/box/size')
        if len(sizes)!=1 or len(model.findall('link/collision'))!=1:
            raise LayoutError('only a single box collision is supported: '+name)
        size = _numbers([float(v) for v in sizes[0].text.split()],3)
        declared_size = _numbers(obj.get('size'),3)
        if any(v<=0 for v in size) or any(abs(a-b)>1e-9 for a,b in zip(size,declared_size)):
            raise LayoutError('declared geometry differs from existing model: '+name)
        # A world-framed link would not follow a model root translation.
        for link_pose in model.findall('link/pose'):
            if link_pose.attrib or any(abs(v)>1e-12 for v in map(float,link_pose.text.split())):
                raise LayoutError('nonzero or framed link origins are unsupported: '+name)
    before = _nonpose_digest(tree,expected)
    for name,(x,y,z,yaw) in expected.items():
        models[name].find('pose').text = ' '.join(format(v,'.17g') for v in (x,y,z,0.,0.,yaw))
    if before != _nonpose_digest(tree,expected):
        raise LayoutError('world properties changed outside model initial poses')
    payload = ET.tostring(tree.getroot(),encoding='utf-8',xml_declaration=True)
    with destination.open('xb') as stream:
        stream.write(payload)
    return dict(schema_version=1,phase='BEFORE_LAUNCH_INITIALIZATION',
                source_world_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                world_sha256=hashlib.sha256(payload).hexdigest(),
                nonpose_properties_sha256=before,initial_objects=expected,
                reads_goal_fields=False,live_state_mutation=False)


def verify_initial(observed, objects, position_tolerance_m=.001, yaw_tolerance_rad=.01):
    """Require measured initial xyz/yaw to agree; unknown is never a zero error."""
    expected = _objects(objects)
    if (type(position_tolerance_m) not in (int,float) or not math.isfinite(position_tolerance_m)
            or position_tolerance_m<=0 or type(yaw_tolerance_rad) not in (int,float)
            or not math.isfinite(yaw_tolerance_rad) or yaw_tolerance_rad<=0):
        raise LayoutError('invalid initial-state tolerance')
    report = {}
    for name,pose in expected.items():
        if name not in observed:
            raise LayoutError('initial object was not measured: '+name)
        actual = _numbers(observed[name],4)
        error = math.dist(actual[:3],pose[:3])
        yaw_error = abs(math.atan2(math.sin(actual[3]-pose[3]),math.cos(actual[3]-pose[3])))
        report[name] = dict(position_error_m=error,yaw_error_rad=yaw_error)
        if error>position_tolerance_m or yaw_error>yaw_tolerance_rad:
            raise LayoutError('measured initial pose disagrees with declaration: '+name)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    build = commands.add_parser('materialize',help='write a fresh SDF before starting Gazebo')
    build.add_argument('--source',type=Path,required=True)
    build.add_argument('--objects',type=Path,required=True,help='JSON list of public object declarations')
    build.add_argument('--out',type=Path,required=True)
    check = commands.add_parser('verify',help='check measured initial xyz/yaw before task dispatch')
    check.add_argument('--objects',type=Path,required=True)
    check.add_argument('--observed',type=Path,required=True)
    args = parser.parse_args(argv)
    objects = json.loads(args.objects.read_text())
    try:
        if args.command=='materialize':
            result = materialize(args.source,args.out,objects)
        else:
            result = dict(status='INITIAL_STATE_VERIFIED',
                          measured_errors=verify_initial(json.loads(args.observed.read_text()),objects),
                          physical_task_dispatched=False,independent_acceptance_claim=False)
    except LayoutError as exc:
        parser.error(str(exc))
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
