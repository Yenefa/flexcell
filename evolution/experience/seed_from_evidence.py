#!/usr/bin/env python3
"""Seed the experience store from REAL archived failures, not invented ones.

WHAT WAS WRONG, AND IS NOW FIXED
    The previous version claimed "The evidence is copied from what the run actually logged. Nothing here
    is a recollection." It checked only that the source DIRECTORY existed (line 26) and never opened it.
    An independent review of the four records it produced found 3 of 4 cite evidence their own cited
    source cannot contain, because the archive holds the POST-FIX run while the evidence describes the
    PRE-FIX failure. It also set validated=True on every record, which readers take to mean a second
    party checked - it only meant this function ran.

WHAT IT DOES NOW
    1. verify_provenance: every evidence string must appear in a MACHINE-READABLE file under source_run.
       A README does not count. Fail-closed: a missing source or a missing value REJECTS.
    2. check_actionability: a lesson the planner cannot act on is refused at WRITE time, using the
       existing audit_actionability classifier rather than a new and possibly more permissive one.
    3. Records carry provenance_verified, evidence_files and reviewer fields, so the schema states what
       was actually checked instead of overloading a field named 'validated'.

    validated stays False. It is not this function's to set - a second party sets that.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / 'evolution' / 'experience'))
import store
import verify_provenance as vp

STORE = WT / 'evolution' / 'experience' / 'records.jsonl'
SEEDS = WT / 'evolution' / 'experience' / 'seed_evidence.json'


def review_seed(s, store_path):
    """Return (accepted, reason, record_or_None). Pure: writes nothing."""
    source_root = WT / s['source_run']
    prov_ok, files, prov_why = vp.verify_provenance(str(source_root), s.get('evidence') or {})
    if not prov_ok:
        return False, 'PROVENANCE: ' + prov_why, None
    act_ok, act_why = vp.check_actionability(s.get('lesson') or '', str(WT))
    if not act_ok:
        return False, 'ACTIONABILITY: ' + act_why, None
    try:
        rec = store.make_record(s['task_id'], s['failure_class'], s['evidence'],
                                s['lesson'], s['source_run'], s['outcome'])
    except ValueError as exc:
        return False, 'STORE REFUSED: ' + str(exc), None
    rec['provenance_verified'] = True
    rec['evidence_files'] = [str(Path(f).relative_to(WT)) for f in files]
    rec['reviewed_by'] = None
    rec['review_verdict'] = None
    rec['review_ref'] = None
    rec['record_sha256'] = store._hash({k: v for k, v in rec.items() if k != 'record_sha256'})
    return True, 'provenance + actionability ok', rec


def main(argv=None):
    argv = argv or sys.argv[1:]
    dry = '--dry-run' in argv
    append_mode = '--append' in argv
    seeds_path = SEEDS
    for i, a in enumerate(argv):
        if a == '--seeds' and i + 1 < len(argv):
            seeds_path = Path(argv[i + 1])
    store_path = Path(STORE)
    # Refuse a full reseed, but ALLOW appending: append is inherently safe (dedup by
    # record_sha256, never rewrites, never deletes). Without this the store could never
    # gain a record after the first run of the old seeder.
    if store_path.exists() and not (dry or append_mode):
        print('store already exists; append-only, refusing to reseed (use --append)')
        return 1
    seeds = json.loads(seeds_path.read_text(encoding='utf-8'))
    accepted = rejected = 0
    for s in seeds:
        ok, why, rec = review_seed(s, store_path)
        if not ok:
            rejected += 1
            print('REJECT %-24s %s' % (s['task_id'], why))
            continue
        accepted += 1
        print('ACCEPT %-24s %s' % (s['task_id'], why))
        if not dry:
            store.append(store_path, rec)
    print()
    print('accepted: %d   rejected: %d   (dry_run=%s)' % (accepted, rejected, dry))
    if dry:
        print('nothing written - dry run')
        return 0
    ok, msg = store.verify_chain(store_path)
    print(msg)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
