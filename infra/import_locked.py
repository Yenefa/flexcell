#!/usr/bin/env python3
"""Fetch exact public upstream commits; fail instead of following a branch."""
import argparse
from pathlib import Path
import re
import subprocess
import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    repositories = yaml.safe_load(args.manifest.read_text())['repositories']
    for name, entry in repositories.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or not re.fullmatch(r'[a-f0-9]{40}', entry['version']):
            raise ValueError('only named repositories pinned to full commits are allowed')
        if not entry['url'].startswith('https://github.com/ROBOTIS-GIT/'):
            raise ValueError('unexpected upstream source')
        target = args.destination / name
        target.mkdir(parents=True, exist_ok=False)
        for command in (['git', 'init', '-q'], ['git', 'remote', 'add', 'origin', entry['url']],
                        ['git', 'fetch', '--depth=1', 'origin', entry['version']],
                        ['git', 'checkout', '--detach', 'FETCH_HEAD']):
            subprocess.run(command, cwd=target, check=True)
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
        if actual != entry['version']:
            raise RuntimeError('upstream commit mismatch')
    # Deliberately exclude GUI/teleop packages from this server-only closure.
    for name in ('open_manipulator', 'open_manipulator_gui', 'open_manipulator_playground',
                 'open_manipulator_teleop', 'open_manipulator_collision', 'ros2_controller'):
        package = args.destination / 'open_manipulator' / name
        if package.is_dir():
            (package / 'COLCON_IGNORE').touch()


if __name__ == '__main__':
    main()
