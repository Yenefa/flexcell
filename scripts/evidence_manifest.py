#!/usr/bin/env python3
"""Content manifest for the acceptance archive.

The archive under setup/acceptance/ is immutable evidence, it is never edited
after the run that produced it, and it is about 97% of this repository by size
(662 MB of 678 MB). Keeping it in the source tree means every clone, worktree
and CI job pays for bytes nobody edits, and the only thing preventing the seven
frozen copies of flexcell_skills from breaking package discovery is a
hand-written COLCON_IGNORE.

This tool makes the archive relocatable without giving up verifiability:

    python3 scripts/evidence_manifest.py generate
    python3 scripts/evidence_manifest.py verify

verify exits non-zero when a file is missing, added or changed, so the manifest
- not the bytes - can live in the repository. See docs/EVIDENCE_ARCHIVE.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_ROOT = 'setup/acceptance'
DEFAULT_MANIFEST = 'config/evidence_manifest.json'
CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def walk(root: Path) -> list[Path]:
    """Every regular file below root, in a stable order."""
    return sorted(p for p in root.rglob('*') if p.is_file())


def build(root: Path) -> dict:
    files = {}
    total = 0
    for path in walk(root):
        size = path.stat().st_size
        total += size
        files[path.relative_to(root).as_posix()] = {
            'sha256': sha256_file(path),
            'size': size,
        }
    return {
        'schema_version': SCHEMA_VERSION,
        'root': root.as_posix(),
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'totals': {'files': len(files), 'bytes': total},
        'files': files,
    }


def cmd_generate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        print(f'archive root not found: {root}', file=sys.stderr)
        return 2
    manifest = build(root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    totals = manifest['totals']
    print(f'wrote {out}: {totals["files"]} files, {totals["bytes"]} bytes')
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root)
    path = Path(args.manifest)
    if not path.is_file():
        print(f'manifest not found: {path}', file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f'archive root not found: {root} (set FLEXCELL_EVIDENCE_ROOT)', file=sys.stderr)
        return 2
    expected = json.loads(path.read_text(encoding='utf-8'))
    if expected.get('schema_version') != SCHEMA_VERSION:
        print(f'unsupported schema_version: {expected.get("schema_version")}', file=sys.stderr)
        return 2
    actual = build(root)

    want, have = expected['files'], actual['files']
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    changed = sorted(name for name in set(want) & set(have)
                     if want[name]['sha256'] != have[name]['sha256'])

    for label, names in (('missing', missing), ('extra', extra), ('changed', changed)):
        for name in names[:20]:
            print(f'{label}: {name}', file=sys.stderr)
        if len(names) > 20:
            print(f'{label}: ... and {len(names) - 20} more', file=sys.stderr)

    if missing or extra or changed:
        print(f'FAIL {len(missing)} missing / {len(extra)} extra / {len(changed)} changed',
              file=sys.stderr)
        return 1
    totals = actual['totals']
    print(f'OK {totals["files"]} files, {totals["bytes"]} bytes match the manifest')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)

    gen = sub.add_parser('generate', help='write the manifest for the archive')
    gen.add_argument('--root', default=DEFAULT_ROOT)
    gen.add_argument('--out', default=DEFAULT_MANIFEST)
    gen.set_defaults(func=cmd_generate)

    ver = sub.add_parser('verify', help='check the archive against the manifest')
    ver.add_argument('--root', default=DEFAULT_ROOT)
    ver.add_argument('--manifest', default=DEFAULT_MANIFEST)
    ver.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
