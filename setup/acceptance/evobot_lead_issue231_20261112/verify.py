#!/usr/bin/env python3
"""Missing-item check for a run's log set. Exits non-zero when anything is missing.

WHY THIS EXISTS (GitHub issue #231)
    A run directory is only reusable evidence if the logs it claims to have are
    actually there. The failure this guards against is not a crash - it is a run
    that finishes, leaves a directory that LOOKS complete, and is then analysed as
    if a log that was never written had been read. Concretely: the Lead's own push
    runs produced no push.jsonl at all, and several analyses silently treated the
    absent file as "nothing to report" instead of "no data". The cost of that is a
    conclusion drawn from a file that does not exist, which is unrecoverable once
    it has been written down.

THE ROOT CAUSE THIS IS BUILT TO CATCH, AND IT IS STILL LIVE
    push_server declares log_dir = '~/.ros/flexcell' as a DEFAULT and gets its
    log_dir overwritten per run only if the node appears in the params file. It
    does not: week1.yaml has blocks for observe/pick/place/verify/carry/task_fsm
    and move_to_pose.yaml for move_to_pose, but NO push_server block. sim_profile
    rewrites log_dir for every node that is present in that config, so push_server
    keeps its default and every run appends to ONE GLOBAL ~/.ros/flexcell/push.jsonl.
    Measured on this checkout: 351 records from 21 distinct request_ids, including
    request ids from several different runs, all in one file.

    So "the log is missing from the run directory" has two very different causes:
      - it was never written at all, or
      - it was written, but to a shared location, mixing runs together.
    A checker that only tests os.path.exists() cannot tell these apart, and the
    second one is the dangerous one: the data exists, so a human who goes looking
    finds something and reasonably assumes it belongs to the run in hand. This
    script distinguishes them and names both.

HOW IT DECIDES WHAT IS REQUIRED
    In priority order:
      1. an explicit --required list (most specific, wins),
      2. a manifest committed next to the run at logs/expected_logs.txt
         (one filename per line, '#' comments allowed),
      3. a --profile preset describing which skills that kind of run invokes.

    Nothing is inferred from what happens to be on disk. A checker that derives
    its expectations from the files it is checking always passes, which is the
    exact defect class of a vacuous acceptance clause.

OUTCOMES IT MUST HANDLE
    A run can end three ways and all three must be reported, never as a bare
    success:
      normal     the run completed; the full required set must be present.
      failed     the run failed mid-way. A partial log set is legitimate, but ONLY
                 if the run left an explicit failure record. Partial logs with no
                 failure record are UNATTRIBUTABLE and are reported as a failure,
                 because nobody can later tell a failure from a truncated archive.
      startup    the platform never came up. Zero skill logs is expected. The run
                 must still carry an explicit startup-failure marker; without one
                 it is indistinguishable from a run whose logs were deleted.

EXIT CODES
    0  complete     every required item present and non-empty
    1  missing      at least one required item absent, empty, or misfiled
    2  usage error  the checker itself was misused (never a pass)

READ-ONLY BY CONSTRUCTION
    This script opens files for reading only. It creates no directories, writes no
    files, and needs no ROS, no simulator and no network: it is a pure filesystem
    check, which is the third acceptance criterion of #231.
"""
import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Skill log names, each taken from the server that declares it:
#   push_server.py        log_file push.jsonl
#   observe_server.py     log_file observe.jsonl
#   pick_server.py        log_file pick.jsonl
#   place_server.py       log_file place.jsonl
#   carry_server.py       log_file carry.jsonl
#   verify_server.py      log_file verify.jsonl
#   task_fsm_server.py    log_file task_fsm.jsonl, decisions.jsonl
#   move_to_pose_server.py log_file move_to_pose.jsonl
# These are the declared names, not a guess from disk contents.
# ---------------------------------------------------------------------------
LOG_PUSH = 'push.jsonl'
LOG_MOVE = 'move_to_pose.jsonl'
LOG_OBSERVE = 'observe.jsonl'
LOG_PICK = 'pick.jsonl'
LOG_PLACE = 'place.jsonl'
LOG_CARRY = 'carry.jsonl'
LOG_VERIFY = 'verify.jsonl'
LOG_FSM = 'task_fsm.jsonl'
LOG_DECISIONS = 'decisions.jsonl'

PROFILES = {
    # A T08 push run invokes PushObject, and the push server always moves the arm
    # with MoveToPose, so both logs must exist or the run is not reusable.
    'push': [LOG_MOVE, LOG_PUSH],
    # A pick/place run exercises the full week-1 skill chain.
    'pick_place': [LOG_MOVE, LOG_OBSERVE, LOG_PICK, LOG_PLACE, LOG_CARRY,
                   LOG_VERIFY, LOG_FSM, LOG_DECISIONS],
    # Minimal: only the transport log. Useful for a smoke run.
    'smoke': [LOG_MOVE],
}

# Markers that let a run state its outcome explicitly instead of leaving a reader
# to infer it from whatever files exist.
MARKER_FAILED = ('invalid_infra.txt', 'failure.json', 'error.json')
MARKER_STARTUP = ('startup_failure.json', 'startup_failure.txt')

# Artefacts that prove a run reached a result. The names differ by layout: the
# current profiles write trial_record.json / verdict.json / evidence_bundle.json,
# older acceptance runs write result.json. Accepting only the modern names would
# report every legacy run as incomplete for a reason that is not a missing log.
RESULT_ARTEFACTS = ('trial_record.json', 'verdict.json', 'evidence_bundle.json',
                    'result.json')


class Finding(object):
    """One missing or misfiled item, with the reason it matters."""

    def __init__(self, kind, name, detail, where=None):
        self.kind = kind          # MISSING | EMPTY | MISFILED | UNMARKED
        self.name = name
        self.detail = detail
        self.where = where

    def as_dict(self):
        out = {'kind': self.kind, 'item': self.name, 'detail': self.detail}
        if self.where:
            out['found_at'] = self.where
        return out

    def __str__(self):
        if self.where:
            return '%-8s %-22s %s (found at %s)' % (
                self.kind, self.name, self.detail, self.where)
        return '%-8s %-22s %s' % (self.kind, self.name, self.detail)


def skill_dir(run_dir):
    """The directory the servers actually write into.

    TWO LAYOUTS EXIST IN THIS REPOSITORY and both are real, so neither may be
    assumed: the current profile layouts write <run>/sim/skills (257 dirs on this
    checkout), and the older acceptance layouts write <run>/skills (13 dirs).
    A checker that knows only one of them silently inspects nothing in the other,
    which is worse than failing: it reports success because it found no file to
    complain about. Returns the first that exists, else the modern path.
    """
    modern = os.path.join(run_dir, 'sim', 'skills')
    if os.path.isdir(modern):
        return modern
    legacy = os.path.join(run_dir, 'skills')
    if os.path.isdir(legacy):
        return legacy
    return modern


def read_manifest(run_dir):
    """Optional committed expectation list. Returns None when absent."""
    for candidate in (os.path.join(run_dir, 'logs', 'expected_logs.txt'),
                      os.path.join(run_dir, 'expected_logs.txt')):
        if os.path.isfile(candidate):
            names = []
            with open(candidate, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    line = line.split('#', 1)[0].strip()
                    if line:
                        names.append(line)
            return names
    return None


def detect_outcome(run_dir):
    """Infer how the run ended from explicit markers, never from log presence."""
    for marker in MARKER_STARTUP:
        if os.path.exists(os.path.join(run_dir, marker)):
            return 'startup'
    for marker in MARKER_FAILED:
        if os.path.exists(os.path.join(run_dir, marker)):
            return 'failed'
    # A run that got as far as producing any artefact is a completed attempt.
    for artefact in RESULT_ARTEFACTS:
        if os.path.exists(os.path.join(run_dir, artefact)):
            return 'normal'
    skills = skill_dir(run_dir)
    if os.path.isdir(skills) and os.listdir(skills):
        return 'normal'
    # No artefacts and no logs at all. This is either a startup failure nobody
    # recorded or a deleted archive - both must be surfaced, not passed.
    return 'unknown'


def global_fallback_path(name):
    """Where a log ends up when its server keeps the default log_dir.

    push_server's declared default is '~/.ros/flexcell'. A log found here instead
    of in the run directory is the shared-file defect: the data exists, but it is
    not this run's data.
    """
    return os.path.join(os.path.expanduser('~'), '.ros', 'flexcell', name)


def earliest_log_mtime(skills_dir):
    """When this run's own logging was happening, as a lower bound.

    Used to decide whether a file in the shared log_dir can possibly belong to
    this run. Returns None when the run wrote no logs to time against.
    """
    newest = None
    try:
        for name in os.listdir(skills_dir):
            path = os.path.join(skills_dir, name)
            if not os.path.isfile(path):
                continue
            mtime = os.path.getmtime(path)
            if newest is None or mtime < newest:
                newest = mtime
    except OSError:
        return None
    return newest


def shared_file_could_belong(shared_path, skills_dir):
    """Is the shared file plausibly this run's, or is it stale from another era?

    WHY THIS CHECK EXISTS - it was added because the first version of this tool
    got it wrong on real data. A run from 2026-11-10 was reported "MISFILED:
    task_fsm.jsonl found at ~/.ros/flexcell/task_fsm.jsonl", but that global file
    was last written 2026-10-05 - five weeks BEFORE the run existed. It cannot
    contain that run's records. Calling it a misfiling would send a reader to a
    file that does hold task_fsm data, just not this run's, and they would very
    reasonably analyse it. That is the exact defect #231 is about, produced by the
    checker meant to catch it.

    A file last written before this run's own logging began cannot be this run's
    output. Anything newer is only a CANDIDATE - the caller must still say so
    without asserting ownership.
    """
    try:
        shared_mtime = os.path.getmtime(shared_path)
    except OSError:
        return False
    reference = earliest_log_mtime(skills_dir)
    if reference is None:
        # no logs of its own to compare against; the safest reading is "cannot
        # establish that this is the run's data", so do not claim it is.
        return False
    return shared_mtime >= reference


def check_run(run_dir, required, check_global=True):
    """Return (findings, outcome, present) for one run directory.

    Pure function of the filesystem: no writes, no side effects.
    """
    findings = []
    outcome = detect_outcome(run_dir)
    skills = skill_dir(run_dir)

    if not os.path.isdir(run_dir):
        findings.append(Finding('MISSING', 'run directory',
                                'the run directory itself does not exist',
                                where=run_dir))
        return findings, outcome, []

    # ---- outcome must be explicitly recorded, whatever else is present -----
    if outcome == 'startup':
        # Zero skill logs is expected here; the marker is what must exist.
        pass
    elif outcome == 'failed':
        pass
    elif outcome == 'unknown':
        findings.append(Finding(
            'UNMARKED', 'outcome record',
            'no logs, no artefacts and no failure marker: a startup failure that '
            'was never recorded is indistinguishable from a deleted archive'))
    elif outcome == 'normal':
        # A completed run must carry at least one result artefact.
        if not any(os.path.exists(os.path.join(run_dir, a))
                   for a in RESULT_ARTEFACTS):
            findings.append(Finding(
                'MISSING', 'result artefact',
                'run inferred complete from logs but none of %s was written'
                % ', '.join(RESULT_ARTEFACTS)))

    # ---- the required log set ---------------------------------------------
    present = []
    for name in required:
        path = os.path.join(skills, name)
        if os.path.isfile(path):
            if os.path.getsize(path) == 0:
                findings.append(Finding(
                    'EMPTY', name,
                    'file exists but is zero bytes: a log that never recorded '
                    'anything is not evidence that nothing happened'))
            else:
                present.append(name)
            continue

        # Not in the run directory. Say whether it exists somewhere shared, which
        # is a different defect with a different fix.
        shared = global_fallback_path(name) if check_global else None
        if (shared and os.path.isfile(shared) and os.path.getsize(shared) > 0
                and shared_file_could_belong(shared, skills)):
            findings.append(Finding(
                'MISFILED', name,
                'written to the shared default log_dir instead of this run; the '
                'server was never given a per-run log_dir (see module docstring). '
                'The shared file is newer than this run, so it MAY contain this '
                "run's records mixed with other runs' - it cannot be used as "
                "this run's log",
                where=shared))
        elif shared and os.path.isfile(shared):
            findings.append(Finding(
                'MISSING', name,
                "not written by this run. A %s exists in the shared log_dir "
                "but predates this run, so it belongs to another era and must "
                "not be used as evidence about this run" % name,
                where=shared))
        else:
            findings.append(Finding(
                'MISSING', name,
                'not written by this run and not found in the shared log_dir'))

    return findings, outcome, present


def scan(root, required, profile, require_all_profiles=False):
    """Check every run directory under a tree. Returns (rows, failures)."""
    rows = []
    failures = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # A run directory is one that owns a skills/ dir (either layout), a sim/
        # dir, or a logs/ dir. 'skills' at this level is the older layout; it must
        # be recognised here or those runs are never checked.
        is_run = ('skills' in dirnames or 'sim' in dirnames or 'logs' in dirnames)
        if not is_run:
            continue
        # do not descend into a run's own subdirectories as if they were runs
        dirnames[:] = [d for d in dirnames if d not in ('sim', 'logs', 'skills',
                                                        'episodes', 'composites')]
        findings, outcome, present = check_run(dirpath, required)
        ok = not findings
        if not ok:
            failures += 1
        rows.append({'run': dirpath, 'outcome': outcome, 'ok': ok,
                     'present': present,
                     'findings': [f.as_dict() for f in findings]})
    return rows, failures


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Check that a run wrote every log it is required to write. '
                    'Exits non-zero when any required item is missing.')
    parser.add_argument('run', nargs='?',
                        help='a single run directory to check')
    parser.add_argument('--scan', metavar='ROOT',
                        help='check every run directory under ROOT')
    parser.add_argument('--profile', default='push', choices=sorted(PROFILES),
                        help='which required-log preset to use (default: push)')
    parser.add_argument('--required', metavar='A,B,C',
                        help='explicit comma-separated list; overrides --profile')
    parser.add_argument('--json', action='store_true',
                        help='machine-readable output')
    parser.add_argument('--no-global-check', action='store_true',
                        help='do not look in the shared default log_dir')
    parser.add_argument('--allow-unmarked-failure', action='store_true',
                        help='downgrade UNMARKED to a warning (not recommended; '
                             'it re-opens the silent-failure hole this guards)')
    args = parser.parse_args(argv)
    if not args.run and not args.scan:
        parser.error('give a run directory or --scan ROOT')
    if args.run and args.scan:
        parser.error('give either a run directory or --scan, not both')
    return args


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.required:
        required = [n.strip() for n in args.required.split(',') if n.strip()]
        if not required:
            print('usage error: --required listed no filenames', file=sys.stderr)
            return 2
    else:
        required = list(PROFILES[args.profile])

    if args.scan:
        rows, failures = scan(args.scan, required, args.profile)
        if not rows:
            # A scan that inspected no run has proven nothing. Reporting "0 of 0
            # incomplete" as success is the vacuous-pass defect this tool exists
            # to catch, so it is a failure of the CHECK, not a clean bill.
            msg = ('no run directories found under %s - nothing was checked, '
                   'which is not the same as everything being present' % args.scan)
            if args.json:
                print(json.dumps({'root': args.scan, 'profile': args.profile,
                                  'required': required, 'runs': [],
                                  'failed_runs': 0, 'error': msg}, indent=2))
            else:
                print('scan root : %s' % args.scan)
                print('required  : %s' % ', '.join(required))
                print()
                print('ERROR: ' + msg)
            return 2
        if args.json:
            print(json.dumps({'root': args.scan, 'profile': args.profile,
                              'required': required, 'runs': rows,
                              'failed_runs': failures}, indent=2))
        else:
            print('scan root : %s' % args.scan)
            print('required  : %s' % ', '.join(required))
            print('runs found: %d' % len(rows))
            print()
            for row in rows:
                status = 'OK  ' if row['ok'] else 'FAIL'
                print('%s %-8s %s' % (status, row['outcome'], row['run']))
                for f in row['findings']:
                    text = Finding(f['kind'], f['item'], f['detail'],
                                   f.get('found_at'))
                    print('       %s' % text)
            print()
            print('%d of %d run(s) incomplete' % (failures, len(rows)))
        return 1 if failures else 0

    findings, outcome, present = check_run(
        args.run, required, check_global=not args.no_global_check)

    if args.allow_unmarked_failure:
        findings = [f for f in findings if f.kind != 'UNMARKED']

    if args.json:
        print(json.dumps({'run': args.run, 'outcome': outcome,
                          'required': required, 'present': present,
                          'complete': not findings,
                          'findings': [f.as_dict() for f in findings]}, indent=2))
    else:
        print('run       : %s' % args.run)
        print('outcome   : %s' % outcome)
        print('required  : %s' % ', '.join(required))
        print('present   : %s' % (', '.join(present) if present else '(none)'))
        print()
        if findings:
            print('MISSING ITEMS (%d):' % len(findings))
            for f in findings:
                print('  %s' % f)
            print()
            print('RESULT: INCOMPLETE - this run may not be analysed as if it '
                  'were complete')
        else:
            print('RESULT: COMPLETE - every required log is present and non-empty')

    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
