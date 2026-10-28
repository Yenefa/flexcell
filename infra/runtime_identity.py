#!/usr/bin/env python3
"""Verify the imported first-party Python files and report installed artifacts."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(repo, install):
    repo, install = Path(repo), Path(install)
    actual = Path(importlib.util.find_spec('flexcell_skills').origin).resolve().parent
    expected = repo / 'src/flexcell/flexcell_skills/flexcell_skills'
    files, mismatches = {}, []
    for source in expected.rglob('*.py'):
        relative = source.relative_to(expected)
        imported = actual / relative
        files[str(relative)] = dict(source_sha256=sha(source),
                                    installed_sha256=sha(imported) if imported.is_file() else None)
        if files[str(relative)]['source_sha256'] != files[str(relative)]['installed_sha256']:
            mismatches.append(str(relative))
    libraries = {str(p.relative_to(install)): sha(p) for p in install.glob('lib/libflexcell*.so')}
    planner = install / 'lib/flexcell_mtc/mtc_planner'
    if planner.is_file():
        libraries[str(planner.relative_to(install))] = sha(planner)
    sources = {}
    for directory in ('src/flexcell', 'infra', 'scripts', 'worlds'):
        for source in (repo / directory).rglob('*'):
            if source.is_file() and '__pycache__' not in source.parts and '.git' not in source.parts:
                sources[str(source.relative_to(repo))] = sha(source)
    for relative in ('setup/flexcell_admin.py', 'plan_execute.py'):
        sources[relative] = sha(repo / relative)
    source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    return dict(schema_version=1, source_revision=os.environ.get('FLEXCELL_SOURCE_REV', 'WORKTREE'),
                imported_package=str(actual), install=str(install), python_files=files,
                native_libraries=libraries, mismatches=mismatches,
                source_files=sources, source_tree_sha256=source_digest,
                packages_sha256=sha(Path('/opt/dependency-packages.tsv'))
                if Path('/opt/dependency-packages.tsv').exists() else None)


if __name__ == '__main__':
    data = snapshot(os.environ['FLEXCELL_REPO'], os.environ['FLEXCELL_INSTALL'])
    print(json.dumps(data, indent=2))
    raise SystemExit(1 if data['mismatches'] else 0)
