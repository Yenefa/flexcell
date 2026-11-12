#!/usr/bin/env python3
"""Acceptance test for a fix to the T08 push primitive.

contracts/push.py is outside this session's granted scope, so the fix is not made here. This is the
test that decides whether a fix worked, so the owner does not have to reconstruct the acceptance
argument from prose.

THREE MEASUREMENTS, because one is not enough:
  1. FINGER HEIGHT - the defect is that contact_height_m is applied to end_effector_link, which sits
     44.3 mm ahead of the fingers, so the fingers ride ~21.7 mm above the box top. Measured from the
     pose each approach actually reached, using the same URDF chain as the diagnosis.
  2. DIRECTION RATE - the symptom is 44% of pushes driving the box the wrong way. A fix that corrects
     height but leaves top-face contact will still reverse sometimes.
  3. TASK PASS RATE - does one push land the box in the zone.

A fix that improves height but not direction has not worked; reporting only height would let it pass.

USAGE, once per fresh world (a push moves the box, so each attempt needs its own world):
    python3 t08_fix_acceptance.py --workdir /tmp/w1 --collect >> /tmp/acc.jsonl
    python3 t08_fix_acceptance.py --report --out /tmp/acc.jsonl --runs 12

PRE-REGISTERED CRITERIA, fixed before any run so they cannot be chosen afterwards:
    finger height within +/-5 mm of the requested contact height, AND
    direction-correct in >= 75% of attempts (cos >= 0.9), AND
    task pass in >= 75% of attempts.

BASELINE ON CURRENT CODE: finger height +17 to +25 mm too high; direction-correct 11/26 = 42%;
task pass 7/16 = 44%.
"""
import argparse, json, math, os, sys

EE_X, FINGER_X, BOX_TOP, BOX_CENTRE = 0.1260, 0.0817, 0.0350, 0.0175
OFFSET = EE_X - FINGER_X
HEIGHT_TOL_M = 0.005
DIRECTION_TOL_COS = 0.9
MIN_PASS_FRACTION = 0.75


def link5_x_world(q):
    x, y, z, w = [float(v) for v in q]
    return [1 - 2*(y*y + z*z), 2*(x*y + z*w), 2*(x*z - y*w)]


def finger_height(ee_position, ee_quaternion):
    """Height of the finger midpoint, derived from the ee frame pose actually reached."""
    lx = link5_x_world(ee_quaternion)
    return float(ee_position[2]) - OFFSET * lx[2]


def approach_record(workdir, contact_height):
    """The move_to_pose record whose target z is closest to the requested contact height."""
    log = os.path.join(workdir, 'sim', 'skills', 'move_to_pose.jsonl')
    best = None
    if not os.path.exists(log):
        return None
    for line in open(log, errors='replace'):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        rp = rec.get('reached_pose') or {}
        p, q = rp.get('position'), rp.get('orientation')
        tgt = (rec.get('target') or {}).get('position') or []
        if not p or not q or len(q) != 4 or len(tgt) < 3:
            continue
        try:
            tz = float(tgt[2])
        except Exception:
            continue
        if tz >= 0.06:
            continue
        d = abs(tz - contact_height)
        if best is None or d < best[0]:
            best = (d, [float(v) for v in p], [float(v) for v in q])
    return best[1:] if best else None


def collect(workdir, task_path, contact_height, request_m):
    """Read one attempt's result out of a world directory and emit a JSON line."""
    sys.path.insert(0, os.environ.get('FLEXCELL_SKILLS',
                   '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/src/flexcell/flexcell_skills'))
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from flexcell_interfaces.action import Observe, PushObject

    spec = json.load(open(task_path))
    want = spec['expected_goal']['push']['target_box_a']
    zone = [z for z in spec['zones'] if z['name'] == want['zone']][0]
    objname = 'target_box_a'

    rclpy.init()
    node = Node('t08_acceptance')
    ob = ActionClient(node, Observe, 'observe')
    pu = ActionClient(node, PushObject, 'push_object')
    ob.wait_for_server(timeout_sec=30.0); pu.wait_for_server(timeout_sec=30.0)

    def snap():
        g = Observe.Goal(); g.refresh = True; g.max_age_s = 0.0
        f = ob.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=30.0)
        h = f.result()
        if h is None or not h.accepted: return None
        rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
        ws = rf.result().result.world_state
        for attr in ('objects', 'tracked_objects', 'items'):
            for o in (getattr(ws, attr, None) or []):
                if getattr(o, 'name', '') == objname:
                    p = o.pose.position
                    return [float(p.x), float(p.y), float(p.z)]
        return None

    pre = snap()
    g = PushObject.Goal(); g.object_name = objname
    g.direction.x = -1.0; g.direction.y = 0.0; g.direction.z = 0.0
    g.distance_m = request_m; g.contact_height_m = contact_height
    g.overdrive_m = float('nan')
    f = pu.send_goal_async(g); rclpy.spin_until_future_complete(node, f, timeout_sec=60.0)
    h = f.result(); res = None
    if h is not None and h.accepted:
        rf = h.get_result_async(); rclpy.spin_until_future_complete(node, rf, timeout_sec=240.0)
        r = rf.result().result
        res = {'ec': int(r.error_code), 'skill_disp': round(float(r.displacement_m), 5)}
    post = snap()
    node.destroy_node(); rclpy.shutdown()

    row = {'contact_height': contact_height, 'request': request_m,
           'skill_disp': res['skill_disp'] if res else None, 'ec': res['ec'] if res else None}
    appr = approach_record(workdir, contact_height)
    if appr:
        row['finger_z'] = round(finger_height(appr[0], appr[1]), 5)
        row['ee_z'] = round(appr[0][2], 5)
    if pre and post:
        disp = math.hypot(post[0]-pre[0], post[1]-pre[1])
        along = (post[0]-pre[0]) * -1.0
        row['actual_disp'] = round(disp, 5)
        row['cos'] = round(along/disp if disp > 1e-6 else 0.0, 4)
        zd = math.hypot(post[0]-zone['pose'][0], post[1]-zone['pose'][1])
        row['zone_distance'] = round(zd, 5)
        row['passed'] = bool(want['min_displacement_m'] <= disp <= want['max_displacement_m']
                             and abs(post[2]-pre[2]) <= want['max_vertical_m']
                             and row['cos'] >= want['min_direction_cosine']
                             and zd <= zone['radius'])
    print(json.dumps(row))
    return 0


def report(path, expected_runs, contact_height):
    if not os.path.exists(path):
        print('no results file at %s - run --collect against each world first' % path)
        return 2
    rows = []
    for line in open(path):
        line = line.strip()
        if line:
            try: rows.append(json.loads(line))
            except Exception: pass
    n = len(rows)
    if not n:
        print('no attempts recorded'); return 1
    heights = [r['finger_z'] for r in rows if r.get('finger_z') is not None]
    ok_dir = sum(1 for r in rows if (r.get('cos') or 0) >= DIRECTION_TOL_COS)
    ok_task = sum(1 for r in rows if r.get('passed'))
    mean_h = sum(heights)/len(heights) if heights else None
    err = (mean_h - contact_height) if mean_h is not None else None
    height_ok = err is not None and abs(err) <= HEIGHT_TOL_M
    dir_ok = ok_dir >= MIN_PASS_FRACTION * n
    task_ok = ok_task >= MIN_PASS_FRACTION * n
    print('T08 fix acceptance report')
    print('  attempts: %d (expected %d)' % (n, expected_runs))
    print('  mean finger height: %s  requested %.4f  error %s' % (
        ('%.4f' % mean_h) if mean_h is not None else 'n/a', contact_height,
        ('%+.4f m' % err) if err is not None else 'n/a'))
    print('  height_ok: %s (needs |error| <= %.3f m)' % (height_ok, HEIGHT_TOL_M))
    print('  direction-correct: %d/%d = %.0f%%  direction_ok: %s' % (ok_dir, n, 100*ok_dir/n, dir_ok))
    print('  task pass: %d/%d = %.0f%%  task_ok: %s' % (ok_task, n, 100*ok_task/n, task_ok))
    verdict = bool(height_ok and dir_ok and task_ok and n >= expected_runs)
    print()
    print('  VERDICT: %s' % ('PASS' if verdict else 'FAIL'))
    if not verdict:
        print('  baseline on current code: height +17..+25 mm, direction 42%, task 44%')
    return 0 if verdict else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--workdir')
    ap.add_argument('--task', default=os.environ.get('T08_TASK', 'benchmark/tasks/t08_dev/T08-push-seed2000.json'))
    ap.add_argument('--contact-height', type=float, default=0.0200)
    ap.add_argument('--request', type=float, default=0.0400)
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--out', default='t08_fix_acceptance.jsonl')
    ap.add_argument('--runs', type=int, default=12)
    a = ap.parse_args(argv)
    if a.collect:
        if not a.workdir:
            print('--collect needs --workdir'); return 2
        return collect(a.workdir, a.task, a.contact_height, a.request)
    if a.report:
        return report(a.out, a.runs, a.contact_height)
    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())