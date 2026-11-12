"""Safety refusals at the new adapter boundary; no simulated physics claims."""
import pytest

from flexcell_skills.reposition import (
    RepositionCanceled, RepositionFailed, execute_reposition)


class Rig:
    def __init__(self):
        self.pose = [.19, -.01, .02]
        self.moves = []
        self.events = []
        self.cancel = False
        self.engaged = False
        self.pose_error = None

    def read(self):
        return list(self.pose), self.pose_error

    def move(self, target):
        self.moves.append(list(target))
        self.pose = list(target)
        return True, .006, 'measured success'

    def run(self, target=(.27, 0., .02), move=None):
        return execute_reposition(
            target, read_pose=self.read, move=move or self.move,
            canceled=lambda: self.cancel,
            emit=lambda name, **data: self.events.append((name, data)),
            minimum_height_m=.18, tracking_margin_m=.02,
            carry_state=lambda: (self.engaged, 'test state'))


@pytest.mark.parametrize('xy', [(.27, 0.), (-.27, 0.), (0., .27), (0., -.27)])
def test_lift_precedes_lateral_transfer_in_every_direction(xy):
    rig = Rig()
    rig.run((*xy, .02))
    assert rig.moves[0] == pytest.approx([.19, -.01, .20])
    assert rig.moves[1] == pytest.approx([*xy, .20])
    assert rig.moves[2] == pytest.approx([*xy, .02])


def test_unsuccessful_lift_sends_no_horizontal_motion():
    rig = Rig()
    def blocked(target):
        rig.moves.append(target)
        return False, .05, 'lift blocked'
    with pytest.raises(RepositionFailed, match='LIFT failed'):
        rig.run(move=blocked)
    assert len(rig.moves) == 1


def test_success_flag_cannot_replace_measured_lift_clearance():
    rig = Rig()
    def false_endpoint(target):
        rig.moves.append(target)
        rig.pose[2] = .03
        return True, .001, 'server says success'
    with pytest.raises(RepositionFailed, match='below measured clearance'):
        rig.run(move=false_endpoint)
    assert len(rig.moves) == 1


def test_missing_or_stale_pose_prevents_dispatch():
    rig = Rig()
    rig.pose_error = 'stale TF'
    with pytest.raises(RepositionFailed, match='stale TF'):
        rig.run()
    assert rig.moves == []


def test_pose_becoming_stale_after_lift_prevents_transfer():
    rig = Rig()
    def stale_after_lift(target):
        result = rig.move(target)
        rig.pose_error = 'stale after lift'
        return result
    with pytest.raises(RepositionFailed, match='stale after lift'):
        rig.run(move=stale_after_lift)
    assert len(rig.moves) == 1


def test_cancellation_after_lift_prevents_transfer_or_lowering():
    rig = Rig()
    def cancel_after_lift(target):
        result = rig.move(target)
        rig.cancel = True
        return result
    with pytest.raises(RepositionCanceled):
        rig.run(move=cancel_after_lift)
    assert len(rig.moves) == 1


def test_failed_transfer_prevents_lowering():
    rig = Rig()
    def blocked_transfer(target):
        if rig.moves:
            rig.moves.append(target)
            return False, .04, 'transfer blocked'
        return rig.move(target)
    with pytest.raises(RepositionFailed, match='TRANSFER failed'):
        rig.run(move=blocked_transfer)
    assert len(rig.moves) == 2


@pytest.mark.parametrize('engaged', [True, None])
def test_unconfirmed_carry_state_refuses_every_motion(engaged):
    rig = Rig()
    rig.engaged = engaged
    with pytest.raises(RepositionFailed, match='carry not confirmed'):
        rig.run()
    assert rig.moves == []


def test_nonfinite_goal_refuses_motion():
    rig = Rig()
    with pytest.raises(RepositionFailed, match='nonfinite'):
        rig.run((float('nan'), 0., .02))
    assert rig.moves == []
