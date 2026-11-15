#!/usr/bin/env python3
"""Read live Git worktrees and workstream refs without fetching or changing them."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, check=True)
    return result.stdout


def revision(root, ref):
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', ref],
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    config = json.loads((args.root / 'config/development_branches.json').read_text())
    encoded = json.dumps(collect(args.root, config), indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded)
    print(encoded, end='')


if __name__ == '__main__':
    main()
