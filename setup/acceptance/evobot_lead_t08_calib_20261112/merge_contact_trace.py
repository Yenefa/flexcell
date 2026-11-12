#!/usr/bin/env python3
# Merge a real contact trace into a bundle built by build_evidence_bundle.py.
#
# Kept separate from the builder because the two inputs come from different sources: the timeline
# capture gives per-step poses, the contact trace gives named collision pairs. Requiring a bundle
# builder to also parse the trace would couple them for no reason.
#
# The trace structure, learned by inspecting it:
#   {'targets': {<model>: {'component_present': bool,
#                          'contacts': {'contact': [ {'collision1': {'id','name'},
#                                                    'collision2': {'id','name'}, ...} ]}}}}
import argparse, hashlib, json

def partners(trace_path):
    all_partners, gripper_pairs = set(), []
    present_true = present_false = 0
    contact_entries = 0
    with open(trace_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            for name, tg in (r.get('targets') or {}).items():
                if tg.get('component_present'):
                    present_true += 1
                else:
                    present_false += 1
                for c in ((tg.get('contacts') or {}).get('contact') or []):
                    a = (c.get('collision1') or {}).get('name')
                    b = (c.get('collision2') or {}).get('name')
                    if not a or not b:
                        continue
                    contact_entries += 1
                    all_partners.add(a); all_partners.add(b)
                    if 'gripper' in a or 'gripper' in b:
                        gripper_pairs.append((a, b))
    pusher = sorted({x for pr in gripper_pairs for x in pr if 'gripper' in x})
    return {'component_present_true': present_true, 'component_present_false': present_false,
            'contact_entries': contact_entries, 'all_partners_seen': sorted(all_partners),
            'pusher_links': pusher, 'gripper_contact_pairs': len(gripper_pairs)}

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--bundle', required=True)
    ap.add_argument('--trace', required=True)
    ap.add_argument('--timeline', required=True,
                    help='the timeline capture the bundle was built from; gripper.span needs real samples')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    state = json.load(open(a.bundle))
    p = partners(a.trace)
    if not p['pusher_links']:
        print('REFUSING: no gripper link appears in the trace, so the contact component observed')
        print('nothing involving the pusher. Writing nothing rather than claiming contact.')
        return 2
    if p['component_present_false'] and not p['component_present_true']:
        print('REFUSING: component_present was false in every record'); return 2
    ev = state['evidence']

    # gripper.span must be [[mono_ns, aperture_rad], ...] - real samples from the timeline,
    # not a count. The validator rejected an integer with 'must be a list of [mono_ns, aperture_rad]'.
    tl = json.load(open(a.timeline))
    span = []
    for s in (tl.get('timeline') or []):
        g, t = s.get('grip'), s.get('t')
        if isinstance(g, (int, float)) and isinstance(t, (int, float)):
            span.append([int(round(float(t) * 1e9)), float(g)])
    if span:
        ev['gripper'] = {'joint_name': ev['gripper'].get('joint_name', 'gripper_left_joint'),
                         'min_aperture_rad': min(x[1] for x in span),
                         'max_aperture_rad': max(x[1] for x in span),
                         'span': span,
                         'note': 'aperture samples from the timeline; not a grasp event log'}

    ev['contacts'] = {'component_present': True,
                      'trusted_source_id': 'flexcell::PhysicsTrace/v1',
                      # intervals is required by the bundle validator; an empty list is permitted.
                      # I am not synthesising intervals from the per-step contacts because a
                      # contact present in consecutive physics steps is not the same thing as a
                      # declared contact interval, and inventing boundaries is exactly what the
                      # #233 work forbids.
                      'intervals': [],
                      'events': p['contact_entries'],
                      'all_partners_seen': p['all_partners_seen'],
                      'pusher_links': p['pusher_links'],
                      'source_note': 'merged from contact_steps.jsonl written by flexcell::ContactTrace'}
    body = json.dumps({k: v for k, v in ev.items() if k != 'manifest'}, sort_keys=True).encode()
    ev['manifest']['bundle_sha256'] = hashlib.sha256(body).hexdigest()
    json.dump(state, open(a.out, 'w'), indent=1)
    print('merged: %d contact entries, %d partners, %d pusher links, component_present true %d / false %d'
          % (p['contact_entries'], len(p['all_partners_seen']), len(p['pusher_links']),
             p['component_present_true'], p['component_present_false']))
    for x in p['pusher_links']:
        print('   pusher link:', x)
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))