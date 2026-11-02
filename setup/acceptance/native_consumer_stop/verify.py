#!/usr/bin/env python3
"""One completed cycle is not a passing five-cycle window."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/flexcell/flexcell_skills')]


def verify():
    from native_cycle_gate import verify_cycle
    archive=Path(__file__).with_name('ci_41387963040.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=='ab09446fc9b05512c7c385aec2643bdb8abd2cfdaed93830cd627dee8dd86236'
    with tempfile.TemporaryDirectory(prefix='native-stopped-') as tmp,zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==29
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(tmp);run=Path(tmp)/'native-five-window'
        worker=json.loads((run/'worker.json').read_text());result=json.loads((run/'result.json').read_text())
        assert worker['status']==result['status']=='STOPPED' and len(worker['cycles'])==2 and worker['no_replacements']
        assert worker['error']=="ValueError('contact evidence: native stream stale; age_ns=1162552992')"
        first,second=worker['cycles'];assert 'evidence' in first and 'evidence' not in second
        events=[json.loads(l) for l in (run/'native-events.jsonl').open()]
        assert [e['label'] for e in events if e['cycle']==1]==['initial_status']
        assert not list(run.glob('reset_after*'))
        physics={v['sim_ns']:v for v in map(json.loads,(run/'physics_steps.jsonl').open())}
        contacts={v['sim_ns']:v for v in map(json.loads,(run/'contact_steps.jsonl').open())}
        declaration=json.loads((run/'declaration.json').read_text())
        assert verify_cycle(physics,contacts,first,events,declaration)==first['evidence']
        lower=events[-1]['request_mono_ns']-100_000_000
        gaps=[]
        for rows in [physics,contacts]:
            tail=[v for v in rows.values() if v['monotonic_ns']>=lower]
            gap=max(b['monotonic_ns']-a['monotonic_ns'] for a,b in zip(tail,tail[1:]));assert gap<500_000_000
            gaps.append(gap)
    return dict(status='PARTIAL_NATIVE_WINDOW_REMAINS_REJECTED',cycles_completed=1,cycles_attempted=2,
                second_cycle_engages=0,reported_consumer_age_ns=1162552992,retained_source_max_gaps_ns=gaps,
                exact_consumer_stall_cause='NOT_INSTRUMENTED',default_admission='NO_GO')


if __name__=='__main__':print(json.dumps(verify(),indent=2))
