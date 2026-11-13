#!/usr/bin/env python3
"""Issue #243: versioned PUSH task declaration validation, with explicit legacy adaptation.

WHY THIS EXISTS
  benchmark/schemas/taskspec.schema.json is FROZEN and requires expected_goal.placement,
  a template_id enum without T08_push_manipulation, zone names ^zone_[0-9]+$, and forbids
  extra keys. The existing frozen T08 TaskSpecs violate all four at once. The experiment
  probe schema on develop/physical-capabilities-20261113 uses a different shape again
  (T08_push, 0.5.x, zone_1). Declaration format and consumer had drifted apart.

WHAT THIS DOES
  Adds TWO NEW versioned contracts and a validator. It does not edit the frozen schema, the
  evaluator, any threshold, any TaskSpec or any evidence file. Inputs are opened read-only.

  classify(obj) -> 'v2' | 'v1' | 'legacy_v1' | 'unknown'
  validate()    -> structured result with source_format, declaration_version, problems,
                   compat_notes, and the SHA256 of the bytes that were read.
  to_v2_view()  -> a READ-ONLY intermediate view for consumers doing explicit adaptation.
                   It preserves original values and lists every divergence in compat_notes.
                   It is NOT a valid v2 declaration and must never be written back.

COMPATIBILITY RULE (deliberate):
  A declaration with NO declaration_version is NOT silently promoted to v2. It is accepted
  only when its shape matches the legacy v1 signature exactly, and is reported as legacy_v1.
  An explicitly unknown version is refused. A missing version must not become a validated one.

NO EXTERNAL DEPENDENCY: jsonschema is not installed, so this implements only the small
draft-2020-12 subset these two contracts use. Unsupported keywords are ignored.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    with open(os.path.join(HERE, name), encoding='utf-8') as fh:
        return json.load(fh)


def _type_ok(node, want):
    if want == 'object':
        return isinstance(node, dict)
    if want == 'array':
        return isinstance(node, list)
    if want == 'string':
        return isinstance(node, str)
    if want == 'integer':
        return isinstance(node, int) and not isinstance(node, bool)
    if want == 'number':
        return isinstance(node, (int, float)) and not isinstance(node, bool)
    if want == 'boolean':
        return isinstance(node, bool)
    if want == 'null':
        return node is None
    return True


def _check(node, rule, path, problems):
    if not isinstance(rule, dict):
        return
    want = rule.get('type')
    if want and not _type_ok(node, want):
        problems.append('%s: expected type %s, got %s' % (path, want, type(node).__name__))
        return
    if 'const' in rule and node != rule['const']:
        problems.append('%s: must equal %r (got %r)' % (path, rule['const'], node))
    if 'enum' in rule and node not in rule['enum']:
        problems.append('%s: %r not in %r' % (path, node, rule['enum']))
    if isinstance(node, str):
        if 'pattern' in rule and not re.search(rule['pattern'], node):
            problems.append('%s: %r does not match %s' % (path, node, rule['pattern']))
        if 'minLength' in rule and len(node) < rule['minLength']:
            problems.append('%s: shorter than %d' % (path, rule['minLength']))
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        if 'minimum' in rule and node < rule['minimum']:
            problems.append('%s: %r < minimum %r' % (path, node, rule['minimum']))
        if 'maximum' in rule and node > rule['maximum']:
            problems.append('%s: %r > maximum %r' % (path, node, rule['maximum']))
        if 'exclusiveMinimum' in rule and node <= rule['exclusiveMinimum']:
            problems.append('%s: %r <= exclusiveMinimum %r' % (path, node, rule['exclusiveMinimum']))
    if isinstance(node, list):
        if 'minItems' in rule and len(node) < rule['minItems']:
            problems.append('%s: fewer than %d items' % (path, rule['minItems']))
        if 'maxItems' in rule and len(node) > rule['maxItems']:
            problems.append('%s: more than %d items' % (path, rule['maxItems']))
        item_rule = rule.get('items')
        if isinstance(item_rule, dict):
            for i, item in enumerate(node):
                _check(item, item_rule, '%s[%d]' % (path, i), problems)
    if isinstance(node, dict):
        props = rule.get('properties') or {}
        for key in rule.get('required') or []:
            if key not in node:
                problems.append('%s: missing required %r' % (path, key))
        extra_rule = rule.get('additionalProperties')
        for key, value in node.items():
            if key in props:
                _check(value, props[key], '%s.%s' % (path, key), problems)
            elif extra_rule is False:
                problems.append('%s.%s: additional property not allowed' % (path, key))
            elif isinstance(extra_rule, dict):
                _check(value, extra_rule, '%s.%s' % (path, key), problems)
        if 'minProperties' in rule and len(node) < rule['minProperties']:
            problems.append('%s: fewer than %d properties' % (path, rule['minProperties']))
        if 'maxProperties' in rule and len(node) > rule['maxProperties']:
            problems.append('%s: more than %d properties' % (path, rule['maxProperties']))


def classify(obj):
    if not isinstance(obj, dict):
        return 'unknown'
    version = obj.get('declaration_version')
    if version == '2.0':
        return 'v2'
    if version == '1.0':
        return 'v1'
    if version is not None:
        return 'unknown'
    goal = obj.get('expected_goal') or {}
    if obj.get('template_id') == 'T08_push_manipulation' and 'push' in goal:
        return 'legacy_v1'
    return 'unknown'


def _compat_notes(kind):
    if kind in ('v1', 'legacy_v1'):
        return [
            'source is a FROZEN legacy TaskSpec; validated against v1.schema.json, not v2',
            'frozen canonical taskspec.schema.json does not admit the push form; no frozen file changed',
            'template_id T08_push_manipulation and evaluator_version 0.3.x are preserved as-is',
            'zone naming such as zone_push does not satisfy v2 pattern and is preserved',
            'instance_sha256 is a legacy integrity field; v2 forbids it, so it stays in the',
            '  original file and is dropped only from the read-only v2 view',
            'a consumer targeting v2 must use to_v2_view() and resolve each divergence',
        ]
    return []


def validate(obj, source_name='<object>'):
    kind = classify(obj)
    result = {
        'source': source_name,
        'source_format': kind,
        'declaration_version': obj.get('declaration_version') if isinstance(obj, dict) else None,
        'problems': [],
        'compat_notes': _compat_notes(kind),
    }
    if kind == 'unknown':
        result['problems'].append(
            'unrecognised declaration: no declaration_version and no legacy v1 signature, '
            'or an explicitly unsupported version')
        result['status'] = 'INVALID'
        return result
    rule = _load('v2.schema.json' if kind == 'v2' else 'v1.schema.json')
    _check(obj, rule, '$', result['problems'])
    goal = obj.get('expected_goal') or {}
    pushes = goal.get('push') or {}
    zone_names = {z.get('name') for z in (obj.get('zones') or []) if isinstance(z, dict)}
    for box, spec in pushes.items():
        if isinstance(spec, dict) and spec.get('zone') not in zone_names:
            result['problems'].append(
                '$.expected_goal.push.%s.zone: %r is not a declared zone' % (box, spec.get('zone')))
        if isinstance(spec, dict):
            lo, hi = spec.get('min_displacement_m'), spec.get('max_displacement_m')
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo >= hi:
                result['problems'].append(
                    '$.expected_goal.push.%s: min_displacement_m >= max_displacement_m' % box)
    if kind in ('v1', 'legacy_v1') and result['declaration_version'] is None:
        result['declaration_version'] = '1.0 (implicit, legacy)'
    result['status'] = 'VALID' if not result['problems'] else 'INVALID'
    return result


def to_v2_view(obj):
    """Read-only intermediate view. Divergences are reported, never silently fixed."""
    view = dict(obj)
    notes = list(_compat_notes(classify(obj)))
    if view.get('template_id') == 'T08_push_manipulation':
        view['template_id'] = 'T08_push'
        notes.append('MAPPED template_id T08_push_manipulation -> T08_push')
    view['declaration_version'] = '2.0'
    notes.append('SET declaration_version 2.0 (was implicit legacy 1.0)')
    for key in ('instance_sha256',):
        if key in view:
            view.pop(key)
            notes.append('DROPPED %s from the view only; original file untouched' % key)
    for z in view.get('zones') or []:
        if isinstance(z, dict) and not re.match(r'^zone_[0-9]+$', str(z.get('name'))):
            notes.append('UNRESOLVED zone name %r does not satisfy v2 pattern; ' % z.get('name')
                         + 'consumer must rename or map it before the view can be validated')
    return {'view': view, 'compat_notes': notes,
            'is_valid_v2': False, 'note': 'This is an adaptation view, NOT a valid v2 declaration.'}


def validate_file(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    try:
        obj = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        return {'source': path, 'status': 'INVALID', 'source_format': 'unknown',
                'declaration_version': None,
                'problems': ['not valid UTF-8 JSON: %s' % exc], 'compat_notes': []}, raw
    res = validate(obj, path)
    res['input_sha256'] = hashlib.sha256(raw).hexdigest()
    res['input_bytes'] = len(raw)
    return res, raw


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Validate versioned EvoBot PUSH task declarations (issue #243).')
    ap.add_argument('files', nargs='+', help='declaration JSON files (read-only)')
    ap.add_argument('--json', action='store_true', help='emit one JSON array')
    ap.add_argument('--view', action='store_true',
                    help='also emit the read-only v2 adaptation view for legacy inputs')
    args = ap.parse_args(argv)
    out = []
    bad = 0
    for path in args.files:
        res, _ = validate_file(path)
        if res['status'] != 'VALID':
            bad += 1
        if args.view and res['source_format'] in ('v1', 'legacy_v1'):
            with open(path, encoding='utf-8') as fh:
                res['v2_view'] = to_v2_view(json.load(fh))
        out.append(res)
        if not args.json:
            print('%s  %s  format=%s  version=%s' % (
                res['status'], os.path.basename(path),
                res['source_format'], res['declaration_version']))
            for p in res['problems']:
                print('    PROBLEM ' + p)
            for n in res['compat_notes']:
                print('    NOTE    ' + n)
    if args.json:
        print(json.dumps(out, indent=2))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
