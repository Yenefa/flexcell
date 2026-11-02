#!/usr/bin/env python3
"""Keep a first-attempt PLACE miss rejected, even though all motion succeeded."""
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/flexcell/flexcell_skills'))
from flexcell_skills.joint_follow import relative_pose


def verify():
    archive = Path(__file__).with_name('ci_40953343176.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'a13c191acce9b3774c30a7c094bca71d4262a78b86ad8efdd1bfd82f08ea0d8c'
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 35
        def read(suffix):
            names = [n for n in z.namelist() if n.endswith(suffix)]
            assert len(names) == 1, suffix
            return z.read(names[0]).decode()
        def rows(suffix):
            return [json.loads(l) for l in read(suffix).splitlines() if l.strip()]
        window = json.loads(read('/window.json'))
        assert window['status'] == 'STOPPED' and window['no_replacements'] is True
        assert len(window['episodes']) == 1
        result = window['episodes'][0]['result']
        assert result['status'] == 'ROBOT_FAILURE' and result['physical_tasks_dispatched'] == 1
        assert result['task']['fsm_trace'] == ['PICK_A(attempt=1):OK', 'PLACE_A:FAIL']
        pick, = rows('/skills/pick.jsonl')
        place, = rows('/skills/place.jsonl')
        assert str(pick['outcome']) == '0' and pick['error_code'] == 0
        assert str(place['outcome']) == '1' and place['error_code'] == 25
        assert place['carry_release_confirmed'] is True and place['released'] is True
        assert place['motion_error_code'] == 0
        assert place['detail'] == 'box settled 0.113m from place pose (tol 0.060)'
        miss = math.dist(place['box_after'], result['goal_pose'])
        assert math.isclose(miss, place['place_error_m'], abs_tol=1e-12) and miss > .11
        assert len(place['mtc_stages']) == 3
        motion = {row['request_id']: row for row in rows('/skills/move_to_pose.jsonl')}
        for stage in place['mtc_stages']:
            value = motion[stage['request_id']]
            assert value['outcome'] == 'SUCCEEDED' and value['error_code'] == 0
            assert value['position_error_m'] < .001
        descend = place['mtc_stages'][1]
        assert descend['target'] == [.12, -.15, .2275]
        follow = rows('/skills/carry.jsonl')
        final, = [v for v in follow if v.get('event') == 'follow_final']
        monitor = final['follow']
        assert monitor['fault'] == '' and monitor['max_translation_m'] < .002
        lo, hi = monitor['first_sim_ns'], monitor['last_sim_ns']
        raw = [v for v in rows('/physics_steps.jsonl') if lo <= v['sim_ns'] <= hi]
        assert len(raw) == (hi-lo)//2_000_000 + 1
        reference = monitor['first_relative_pose']
        peak = 0.
        for value in raw:
            assert value['objects']['target_box_a']['joint_component'] is True
            p, q = relative_pose(value['parent_pose'], value['objects']['target_box_a']['pose'])
            peak = max(peak, math.dist(p, reference[:3]))
            assert 2*math.acos(min(1., abs(sum(a*b for a,b in zip(q, reference[3:]))))) < math.pi/180
        assert peak < .002
        # Joint-frame geometry was stable; the physical box center was far from
        # the nominal EE-minus-160mm point just before intentional release.
        nominal_box = [.12, -.15, .0675]
        before_release = raw[-1]['objects']['target_box_a']['pose'][:3]
        assert math.dist(before_release, nominal_box) > .13
        identity = json.loads(read('/identity.stdout'))
        assert identity['source_revision'] == '01f7fc0a3ac9fb7e1f556fe4b64b1e12e35042b6'
        assert identity['mismatches'] == []
    return dict(status='PLACE_MISS_REMAINS_REJECTED', workflow_run=40953343176,
                source_revision=identity['source_revision'], physical_tasks=1, pick_attempts=1,
                successful_place_motion_stages=3, settled_error_m=miss,
                stable_relative_translation_peak_m=peak, default_admission='NO_GO',
                original_grasp_b001_mechanism='UNKNOWN')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
