"""Mutation proof: the push checks are REAL, not decorative.

WHY A MUTATION TEST AND NOT ANOTHER ASSERTION
    A passing assertion proves only that the code and the test agree today. It
    does not prove the check can fail. Every check below is therefore applied
    to a DELIBERATELY BROKEN copy of the module, and the test passes only when
    the broken copy is caught. If someone later weakens a check, the
    corresponding mutant stops being detected and this file fails.

    The mutants are generated in a temp directory from the real source, so the
    tracked module is never edited (asserted at the end of the run).

MUTANTS (each must be caught):
    M1 contact detection always true   - the skill would report a push on a box
                                         that never moved. This is the single
                                         most dangerous mutation: it turns every
                                         run into a success.
    M2 overdrive removed               - the honest "could not get through"
                                         signal disappears: the arm aims exactly
                                         at the box and reaches "within
                                         tolerance" whether or not it moved.
    M3 contact-loss detection disabled - the measured 23 mm saturation would be
                                         reported as a slow push, then rounded up
                                         to success.
    M4 carry check removed             - a carried box would count as pushed.
    M5 overshoot bound removed         - shoving the box across the table would
                                         pass as a bounded push.
    M6 displacement measured from the ARM instead of the object
                                       - the classic false success: everything
                                         succeeds because the arm moved.
"""
import importlib
import shutil
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'flexcell_skills' / 'contracts' / 'push.py'


def _mutants():
    return {
        'M1_contact_always_true': (
            "contact_made = moved >= p['contact_floor_m']",
            "contact_made = True"),
        'M2_no_overdrive': (
            "    total = float(distance) + float(overdrive)",
            "    total = float(distance)"),
        'M3_no_contact_loss': (
            "        if stalled and pushed and unfinished and index > 1:",
            "        if False and stalled and pushed and unfinished and index > 1:"),
        'M4_no_carry_check': (
            "        if engaged_now:",
            "        if False and engaged_now:"),
        'M5_no_overshoot_bound': (
            "    if moved - resolved['distance_m'] > tolerance:",
            "    if False and moved - resolved['distance_m'] > tolerance:"),
        'M6_arm_instead_of_object': (
            "    moved = metrics['displacement_m']",
            "    moved = resolved['distance_m']"),
    }


def _load_mutant(tmp_path, name, old, new):
    source = SOURCE.read_text(encoding='utf-8')
    assert old in source, 'mutation target disappeared: ' + old
    mutated = source.replace(old, new, 1)
    assert mutated != source
    path = tmp_path / (name + '.py')
    path.write_text(mutated, encoding='utf-8')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _World:
    """The probe's measured shape: the box moves then stops dead."""

    def __init__(self, start, steps):
        self.position = list(start)
        self.steps = list(steps)
        self.reads = 0
        self.moves = []

    def measure(self):
        self.reads += 1
        if self.reads > 1 and self.steps:
            delta = self.steps.pop(0)
            self.position = [self.position[i] + delta[i] for i in range(3)]
        return list(self.position), None

    def move_to(self, target):
        self.moves.append(list(target))
        return True, 0.006, 'scripted'

    def carry_engaged(self):
        return False, None

    def cancelled(self):
        return False

    def phase(self, name):
        pass

    def emit(self, event, **data):
        pass


GOAL = dict(object_name='target_box_a', direction=[-1.0, 0.0, 0.0],
            distance_m=0.030, contact_height_m=0.030, overdrive_m=0.02,
            max_increments=5)


@pytest.mark.parametrize('name', sorted(_mutants()))
def test_every_mutant_is_caught(tmp_path, name):
    old, new = _mutants()[name]
    module = _load_mutant(tmp_path, name, old, new)
    caught, detail = _probe(module)
    assert caught, name + ' was NOT caught: ' + detail


def _probe(module):
    """Return (caught, detail) for one mutated module.

    The probe is the same shape as the real acceptance question: "the box moved
    23 mm of the 30 mm asked and then stopped - is that a success?"
    """
    observed = []

    def run(steps, goal=None):
        world = _World([0.220, 0.0, 0.0175], steps)
        return module.execute_push(world, dict(goal or GOAL), {}), world

    # (a) THE MEASURED SATURATION: 10 + 10 + 3 mm = 23 mm of the 30 mm asked,
    #     then the box stops dead while the arm keeps advancing. This is the
    #     exact shape of the archived run3. A correct module must fail.
    result, world = run([[-0.010, 0, 0], [-0.010, 0, 0], [-0.003, 0, 0]]
                        + [[0, 0, 0]] * 6)
    observed.append(('saturation', result))
    if result['outcome'] == 0:
        return True, 'reported a saturated push as SUCCEEDED'
    if result['error_code'] != module.ERR_CONTACT_LOST:
        return True, 'saturation diagnosed as %d instead of CONTACT_LOST' % result['error_code']

    # (b) the never-touched case: the arm walks through, the box never moves.
    result, world = run([[0, 0, 0]] * 9)
    if result['outcome'] == 0:
        return True, 'reported a zero-displacement push as SUCCEEDED'
    if result['error_code'] != module.ERR_CONTACT_NOT_MADE:
        return True, 'zero displacement diagnosed as %d' % result['error_code']

    # (c) the honest failure signal: a blocked arm must not look like a push.
    class Blocked(_World):
        def move_to(self, target):
            self.moves.append(list(target))
            return False, 0.045, 'blocked'

    world = Blocked([0.220, 0.0, 0.0175], [[0, 0, 0]] * 9)
    result = module.execute_push(world, dict(GOAL), {})
    if result['outcome'] == 0:
        return True, 'reported a blocked arm as SUCCEEDED'

    # (d) the overdrive must actually place the last target past the request.
    result, world = run([[-0.010, 0, 0], [-0.010, 0, 0], [-0.003, 0, 0]]
                        + [[0, 0, 0]] * 6)
    expected_total = GOAL['distance_m'] + GOAL['overdrive_m']
    span = abs(world.moves[-2][0] - world.moves[0][0]) if len(world.moves) > 1 else 0.0
    if span < expected_total - 1e-6:
        return True, 'last target only %.4fm past the approach (needs %.4fm)' % (span, expected_total)

    # (e) a shove far past the request must not pass.
    result, _ = run([[-0.060, 0, 0]] * 5)
    if result['outcome'] == 0:
        return True, 'reported a 300 mm shove as a bounded 30 mm push'

    # (f) CONTACT LOSS MUST STOP THE ARM, not merely be reported at the end.
    #     Once the box stops following, every further increment drives the
    #     gripper deeper into the space the box occupies. A module that keeps
    #     commanding increments until the budget runs out is doing damage and
    #     only narrating it. Detectable as: it used fewer increments than the
    #     full budget.
    result, _ = run([[-0.010, 0, 0], [-0.010, 0, 0], [-0.003, 0, 0]]
                    + [[0, 0, 0]] * 6)
    if result.get('increments_executed', 0) >= GOAL['max_increments']:
        return True, ('ran all %d increments after contact was lost at %s'
                      % (result.get('increments_executed', -1),
                         result.get('contact_lost_at_increment')))

    # (g) A CARRIED OBJECT IS NOT A PUSHED OBJECT.
    class Carrying(_World):
        def carry_engaged(self):
            return len(self.moves) >= 2, None

    world = Carrying([0.220, 0.0, 0.0175], [[-0.010, 0, 0]] * 9)
    result = module.execute_push(world, dict(GOAL), {})
    if result['outcome'] == 0:
        return True, 'reported a carried object as a pushed one'
    if not result.get('carry_engaged_during'):
        return True, 'did not record that carry engaged during the push'

    return False, ''


def test_the_unmutated_module_passes_the_same_probe():
    """Control: without a mutation the probe finds nothing wrong.

    Without this, a probe that always reports "caught" would look like a
    perfect mutation detector.
    """
    caught, detail = _probe(push_module())
    assert not caught, detail


def push_module():
    from flexcell_skills.contracts import push
    return push


def test_the_tracked_module_was_never_edited(tmp_path):
    """Mutants are copies on disk. Prove the real file is untouched.

    A mutation test that edits the tracked source and restores it afterwards is
    one crash away from committing a mutant. So no mutant is ever written over
    the real path: this asserts the file's digest is unchanged across a full
    mutation run, and that all mutants landed outside the source tree.
    """
    import hashlib
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    old, new = _mutants()['M2_no_overdrive']
    mutant = _load_mutant(tmp_path, 'digest_probe', old, new)
    assert mutant is not None
    after = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert before == after, 'a mutation wrote over the tracked contract'
    assert Path(mutant.__file__).resolve().parent == tmp_path.resolve(), (
        'the mutant was not isolated to a temp directory')
