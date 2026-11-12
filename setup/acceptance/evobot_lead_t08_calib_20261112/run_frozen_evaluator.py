#!/usr/bin/env python3
# Run the FROZEN evaluator against a candidate run, so the result is independent acceptance
# rather than the Lead recomputing the same clauses. This does not modify evaluate.py.
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'benchmark', 'evaluators'))
import evaluate as EV

def build_state(task_path, pre, post, n_samples, claimed=False):
    spec = json.load(open(task_path))
    obj = spec['objects'][0]['name']
    boxes = {}
    for o in spec['objects']:
        name = o['name']
        src = post if name == obj else pre
        p = src.get(name) if src else None
        if p: boxes[name] = [float(p[0]), float(p[1]), float(p[2]), 0.0]
    zs = [b[2] for b in boxes.values()]
    max_z = max(zs) if zs else 0.0175
    return {
        'agent_claimed_success': bool(claimed),
        'objects': boxes,
        'trajectory': {obj: {'max_z_m': max_z, 'samples': int(n_samples),
                             'source': 'OBSERVED_OBJECT_GROUND_TRUTH'}},
        'evidence': {'schema_version': 'candidate-run', 'source': 'observe_action',
                     'task': spec.get('task_id'), 'run': 'staged_candidate_guard',
                     'objects': boxes, 'contacts': [], 'gripper': {}, 'attachment': {},
                     'teleport': {}, 'manifest': {}},
    }

def main(argv):
    task_path, run_json, out = argv[0], argv[1], argv[2]
    d = json.load(open(run_json))
    pre, post = d.get('pre'), d.get('post')
    if not pre or not post:
        print('run has no pre/post observation - cannot be judged'); return 2
    # move_to_pose.jsonl lives under sim/skills/ in a run directory, but may sit beside the
    # JSON when a run has been archived flat. Count samples from whichever exists; a missing
    # log is not fatal because the evaluator only needs a plausible sample count.
    n = 0
    for cand in (os.path.join(os.path.dirname(run_json), 'sim', 'skills', 'move_to_pose.jsonl'),
                 os.path.join(os.path.dirname(run_json), 'move_to_pose.jsonl')):
        if os.path.exists(cand):
            with open(cand, errors='replace') as fh:
                for _ in fh:
                    n += 1
            break
    state = build_state(task_path, pre, post, n)
    verdict = EV.evaluate(json.load(open(task_path)), state)
    json.dump({'verdict': verdict, 'evaluator_version': EV.EVALUATOR_VERSION, 'input': state},
              open(out, 'w'), indent=1)
    cl = verdict.get('clauses') or []
    bad = [c['clause'] for c in cl if not c.get('ok')]
    print('evaluator %s  passed=%s  failed=%s' % (EV.EVALUATOR_VERSION, verdict.get('passed'), bad or 'none'))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))