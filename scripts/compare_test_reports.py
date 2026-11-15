#!/usr/bin/env python3
"""Require identical test coverage, no added failures and no added skips."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def cases(path):
    root = ET.parse(path).getroot()
    rows = {}
    for row in root.iter('testcase'):
        identity = row.get('classname', '') + '::' + row.attrib['name']
        if identity in rows:
            raise ValueError('duplicate test identity: ' + identity)
        rows[identity] = ('failed' if row.find('failure') is not None or row.find('error') is not None
                          else 'skipped' if row.find('skipped') is not None else 'passed')
    if not rows:
        raise ValueError('empty test report: ' + str(path))
    return rows


def compare(before, after):
    missing = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())
    regressions = sorted(k for k in before.keys() & after.keys()
                         if after[k] != 'passed' and after[k] != before[k])
    return dict(passed=not missing and not added and not regressions,
                qualification='DIFFERENTIAL_COMPATIBILITY_ONLY',
                collected_before=len(before), collected_after=len(after),
                unchanged_failures=sorted(k for k in before.keys() & after.keys()
                                          if before[k] == after[k] == 'failed'),
                repaired_failures=sorted(k for k in before.keys() & after.keys()
                                         if before[k] == 'failed' and after[k] == 'passed'),
                missing_tests=missing, added_tests=added, regressions=regressions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = compare(cases(args.before), cases(args.after))
    encoded = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded)
    print(encoded, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
