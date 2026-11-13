#!/usr/bin/env python3
"""Check Python import direction; report exact, pre-existing experiment dependencies."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def qualified(node, aliases):
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return qualified(node.value, aliases) + '.' + node.attr
    return ''


def dependencies(tree):
    """Static imports, literal dynamic imports and known path-based loader calls."""
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or '') + '.' + item.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                yield node, 'import', item.name
        elif isinstance(node, ast.ImportFrom):
            # Relative imports remain inside the current Python package.
            if node.level == 0:
                yield node, 'import', node.module or ''
        elif isinstance(node, ast.Call):
            name = qualified(node.func, aliases)
            if name in ('__import__', 'importlib.import_module') and node.args:
                target = node.args[0]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    yield node, 'import', target.value
            elif name in ('sys.path.insert', 'sys.path.append', 'sys.path.extend',
                          'importlib.util.spec_from_file_location', 'runpy.run_path'):
                yield node, 'loader_path', ast.unparse(node)
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(qualified(t.value if isinstance(t, ast.Subscript) else t, aliases) == 'sys.path'
                   for t in targets):
                yield node, 'loader_path', ast.unparse(node)


def scan(root, config):
    root = Path(root)
    violations = []
    scanned = set()
    for rule in config['rules']:
        for relative in rule['roots']:
            directory = root / relative
            if not directory.is_dir():
                violations.append(dict(rule=rule['id'], path=relative, kind='missing_root', expression=relative, line=0))
                continue
            for path in sorted(directory.rglob('*.py')):
                source = path.relative_to(root).as_posix()
                scanned.add(source)
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8'))
                except (OSError, SyntaxError) as exc:
                    violations.append(dict(rule=rule['id'], path=source, kind='parse_error', expression=str(exc), line=0))
                    continue
                for node, kind, expression in dependencies(tree):
                    blocked = False
                    if kind == 'import':
                        blocked = any(expression == p or expression.startswith(p + '.')
                                      for p in rule.get('forbidden_imports', []))
                        if 'allowed_external_imports' in rule:
                            allowed = sys.stdlib_module_names | set(rule['allowed_external_imports'])
                            blocked = expression.split('.')[0] not in allowed
                    elif kind == 'loader_path':
                        strings = [s.value for s in ast.walk(node)
                                   if isinstance(s, ast.Constant) and isinstance(s.value, str)]
                        parts = {p for s in strings for p in re.split(r'[/\\]+', s)}
                        blocked = rule.get('forbid_python_path_changes', False) or bool(
                            parts & set(rule.get('forbidden_path_parts', [])))
                    if blocked:
                        violations.append(dict(rule=rule['id'], path=source, kind=kind,
                                               expression=expression, line=node.lineno))
    return len(scanned), violations


def fingerprint(item):
    return tuple(item[k] for k in ('rule', 'path', 'kind', 'expression'))


def audit(root, config):
    scanned, found = scan(root, config)
    expected = Counter()
    for exception in config.get('legacy_exceptions', []):
        expected[fingerprint(exception)] += exception['count']
    actual = Counter(fingerprint(v) for v in found)
    remaining = expected.copy()
    new = []
    for violation in found:
        key = fingerprint(violation)
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            new.append(violation)
    stale = [dict(zip(('rule', 'path', 'kind', 'expression'), key), count=count - actual[key])
             for key, count in expected.items() if actual[key] < count]
    return dict(passed=not new and not stale, scanned_files=scanned,
                violations=new, stale_exceptions=stale,
                legacy_dependencies=[v for v in found if fingerprint(v) in expected])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    config = json.loads((args.root / 'config/skill_boundaries.json').read_text())
    report = audit(args.root, config)
    encoded = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded)
    print(encoded, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
