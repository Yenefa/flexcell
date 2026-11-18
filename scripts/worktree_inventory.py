#!/usr/bin/env python3
"""Read live Git worktrees and workstream refs without fetching or changing them."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


class UsageError(Exception):
    """Bad input or bad configuration: exit 2, never a partial report."""


def load_config(path):
    try:
        raw = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError('cannot read config %s: %s' % (path, exc))
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError('config %s is not valid JSON: %s' % (path, exc))
    if not isinstance(config, dict):
        raise UsageError('config %s must be a JSON object' % path)
    streams = config.get('workstreams')
    if not isinstance(streams, list) or not streams:
        raise UsageError('config %s needs a non-empty workstreams list' % path)
    for index, stream in enumerate(streams):
        if not isinstance(stream, dict):
            raise UsageError('workstreams[%d] must be an object' % index)
        for key in ('id', 'branch', 'status'):
            if not isinstance(stream.get(key), str) or not stream[key]:
                raise UsageError('workstreams[%d].%s must be a non-empty string'
                                 % (index, key))
    roles = config.get('worktree_roles', [])
    if not isinstance(roles, list):
        raise UsageError('worktree_roles must be a list')
    for index, role in enumerate(roles):
        if not isinstance(role, dict):
            raise UsageError('worktree_roles[%d] must be an object' % index)
        for key in ('branch', 'role'):
            if not isinstance(role.get(key), str) or not role[key]:
                raise UsageError('worktree_roles[%d].%s must be a non-empty string'
                                 % (index, key))
    return config


def git(root, *args):
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(Path(root).resolve()),
                             '-C', str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('git read failed: ' + result.stderr.strip())
    return result.stdout


def revision(root, ref):
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(Path(root).resolve()),
                             '-C', str(root), 'rev-parse', '--verify', ref],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def collect(root, config):
    trees = []
    roles = {r['branch']: r for r in config.get('worktree_roles', [])}
    for block in git(root, 'worktree', 'list', '--porcelain', '-z').split('\0\0'):
        fields = dict(line.split(' ', 1) if ' ' in line else (line, True)
                      for line in block.strip('\0').split('\0') if line)
        if not fields:
            continue
        path = Path(fields['worktree'])
        branch = str(fields.get('branch', '')).removeprefix('refs/heads/') or None
        row = dict(path=str(path), branch=branch, head=fields.get('HEAD'),
                   role=roles.get(branch, {}).get('role', 'UNASSIGNED'),
                   locked=fields.get('locked', False), prunable=fields.get('prunable', False),
                   exists=path.is_dir(), dirty=None)
        if row['exists'] and not fields.get('bare') and not row['prunable']:
            row['dirty'] = bool(git(path, 'status', '--porcelain=v1', '-z',
                                   '--untracked-files=normal'))
        trees.append(row)
    streams = []
    for stream in config['workstreams']:
        branch = stream['branch']
        streams.append(dict(id=stream['id'], declared_status=stream['status'], branch=branch,
                            local_head=revision(root, 'refs/heads/' + branch),
                            observed_origin_head=revision(root, 'refs/remotes/origin/' + branch),
                            worktrees=[t['path'] for t in trees if t['branch'] == branch]))
    return dict(schema_version=1, read_only=True, fetched=False,
                activity='Branch status and worktrees do not establish running agents.',
                worktrees=trees, workstreams=streams)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 if any worktree is missing, dirty or prunable')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.root / 'config/development_branches.json')
        report = collect(args.root, config)
    except (UsageError, RuntimeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2
    encoded = json.dumps(report, indent=2) + '\n'
    if args.out:
        try:
            args.out.write_text(encoded)
        except OSError as exc:
            print('ERROR: cannot write %s: %s' % (args.out, exc), file=sys.stderr)
            return 2
    print(encoded, end='')
    if args.strict:
        bad = [row for row in report['worktrees']
               if not row['exists'] or row['dirty'] or row['prunable']]
        if bad:
            print('ERROR: strict inventory found %d missing/dirty/prunable '
                  'worktree(s): %s' % (len(bad), ', '.join(row['path'] for row in bad)),
                  file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
