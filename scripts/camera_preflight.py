#!/usr/bin/env python3
"""Check headless EGL/OpenGL before starting a camera simulation or any task."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def parse_surfaceless(report):
    sections = re.findall(r'(?m)^Surfaceless platform:\s*\n([\s\S]*?)(?=\n\s*\n|\Z)', report)
    if len(sections) != 1:
        raise ValueError('no unambiguous surfaceless EGL platform')
    section = sections[0]
    fields = {}
    for key in ('EGL vendor string', 'OpenGL core profile renderer', 'OpenGL core profile version'):
        values = re.findall(r'(?m)^' + re.escape(key) + r':\s*(.+)$', section)
        if len(values) != 1:
            raise ValueError('surfaceless ' + key + ' unavailable')
        fields[key] = values[0].strip()
    version = re.match(r'^(\d+)\.(\d+)\b', fields['OpenGL core profile version'])
    if version is None or tuple(map(int, version.groups())) < (3, 3):
        raise ValueError('surfaceless OpenGL core profile 3.3 or later required')
    return fields


def preflight_rendering(out):
    out = Path(out)
    report = dict(schema_version=1, status='FAIL', simulator_started=False,
                  method='eglinfo -B; surfaceless OpenGL core profile >= 3.3', vendor_files={})
    for directory in ('/usr/share/glvnd/egl_vendor.d', '/etc/glvnd/egl_vendor.d'):
        for path in sorted(Path(directory).glob('*.json')):
            report['vendor_files'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        probe = subprocess.run(['eglinfo', '-B'], capture_output=True, text=True, timeout=10,
                               env={**os.environ, 'EGL_PLATFORM': 'surfaceless'})
        (out / 'camera_preflight.stdout').write_text(probe.stdout)
        (out / 'camera_preflight.stderr').write_text(probe.stderr)
        report['returncode'] = probe.returncode
        # Mesa can return 3 for the unavailable GBM/Wayland/X11 platforms while
        # reporting a working surfaceless context. Validate that platform's
        # measured profile; retain the aggregate exit code without using it as
        # a claim about an individual platform.
        if probe.returncode < 0:
            raise ValueError('eglinfo terminated by signal ' + str(-probe.returncode))
        report['surfaceless'] = parse_surfaceless(probe.stdout)
        report['status'] = 'PASS'
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report['error'] = str(exc)
    (out / 'camera_preflight.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'PASS':
        raise RuntimeError('camera EGL preflight failed: ' + report['error'] +
                           '; no robot task dispatched; see camera_preflight.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        print(json.dumps(preflight_rendering(args.out), indent=2))
    except RuntimeError as exc:
        parser.exit(1, str(exc) + '\n')
