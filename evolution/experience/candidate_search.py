#!/usr/bin/env python3
"""Search several ways to apply a lesson and pick one on MEASURED performance AND cost.

WHY A SEARCH AND NOT A CONSTANT
    Both skill parameters in this package were chosen by hand: spread_step 0.090 because
    clearance 0.050 plus a drift allowance, cluster_m 0.120 because it was above the plan
    builder's 56 mm offset. Those are reasonable, and neither was ever compared against an
    alternative. GEPA's point is that the comparison is cheap when the feedback is already
    archived, and that a parameter nobody compared is a guess wearing a number.

WHAT MAKES A CANDIDATE ADMISSIBLE
    Feasibility is a hard filter, not a term in a score:
      * every below-contract plan must end up at or above the contract
      * no plan may end up with LESS separation than it started with
      * no plan may end up closer than the clearance contract to another object
      * the consumer may refuse, but a refusal counts as a plan not fixed - never hidden
    A candidate that violates any of those is REJECTED, and the rejection is kept with its
    numbers. This matters: minimal_move is CHEAPER on the two-stage case it was written for
    (17 mm of displacement instead of 53 mm) and it is still rejected, because it puts one
    landing 46.1 mm from box_b - exactly the defect fixed on 2026-11-18. Judging that
    candidate by its cost on the case it was designed for would have shipped it.

    Its mean displacement across the whole archive is in fact WORSE (81.6 mm vs 47.5 mm),
    because on three-stage plans it only holds the pair axis and the third landing goes far.
    Both numbers are reported; neither is allowed to stand in for the other.

HOW THE WINNER IS CHOSEN
    Among admissible candidates: lowest mean displacement. Task performance is the
    CONSTRAINT, cost is the OBJECTIVE. Not a weighted sum, because a weight would let a
    cheap candidate buy its way past a violated contract.

REFUSES RATHER THAN FALLS BACK
    If no candidate is admissible the search returns no selection and says why. Falling
    back to the incumbent would make "the incumbent is the only thing that works" and "the
    search is broken" look identical from the outside.
"""
import glob
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))

SPREAD_CONTRACT_M = 0.090
CLEARANCE_M = 0.050


def _pts(stages):
    return [(float(s["place_pose"][0]), float(s["place_pose"][1])) for s in stages]


def _min_sep(stages):
    p = _pts(stages)
    if len(p) < 2:
        return None
    return min(math.hypot(a[0] - b[0], a[1] - b[1])
               for i, a in enumerate(p) for b in p[i + 1:])


def _min_clearance(stages, avoid):
    if not avoid:
        return None
    return min(math.hypot(p[0] - a[0], p[1] - a[1])
               for p in _pts(stages) for a in avoid)


def load_plans(acceptance=None):
    """Every archived plan whose same-bin separation is BELOW the contract.

    Plans already at or above the contract are excluded on purpose: they are the control
    group for the "does it fire where it need not" question, which misuse.py owns. Mixing
    them into the search would let a candidate score well by touching nothing.
    """
    root = acceptance or os.path.join(WT, "setup", "acceptance")
    out = []
    for path in glob.glob(os.path.join(root, "**", "plan*.json"), recursive=True):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        stages = [s for s in (doc.get("stages") or [])
                  if isinstance(s, dict) and isinstance(s.get("place_pose"), (list, tuple))]
        if len(stages) < 2:
            continue
        sep = _min_sep(stages)
        if sep is None or sep >= SPREAD_CONTRACT_M - 1e-9:
            continue
        avoid = [o["position"][:2] for o in (doc.get("initial_objects") or [])
                 if o.get("position")]
        out.append({"path": os.path.relpath(path, root), "plan": doc,
                    "sep": sep, "avoid": avoid})
    return out


# --- candidates ---------------------------------------------------------------

def _by_pair_axis(plan, step):
    """MINIMAL-MOVE: keep the pair's own midpoint, extend along the pair's own axis.

    Included because it is the obvious cheap answer and it must be tested rather than
    assumed. On a two-stage pair it moves each landing only (contract - current)/2, which on
    the T13 plan is 17 mm instead of 53 mm - a third of the cost. It also puts one landing
    46.1 mm from box_b, which is why it loses. On THREE-stage plans it holds only the first
    pair's axis and the remaining landing goes far, so its archive-wide mean is worse.
    """
    stages = plan["stages"]
    avoid = [o["position"][:2] for o in (plan.get("initial_objects") or [])
             if o.get("position")]
    pts = _pts(stages)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    out = [dict(s, place_pose=list(s["place_pose"])) for s in stages]
    for rank in range(len(out)):
        off = (rank - (len(out) - 1) / 2.0) * step
        out[rank]["place_pose"] = [cx + ux * off, cy + uy * off,
                                   float(stages[rank]["place_pose"][2])]
    return out


def _respread(step, cluster_m):
    def run(plan):
        import recover
        return recover.apply_respread(plan, spread_step=step, cluster_m=cluster_m,
                                      avoid=[o["position"][:2]
                                             for o in (plan.get("initial_objects") or [])
                                             if o.get("position")])["stages"]
    return run


CANDIDATES = {
    # name: (callable(plan) -> stages, declared intent)
    "respread/step=0.090": (_respread(0.090, 0.120), "the incumbent"),
    "respread/step=0.095": (_respread(0.095, 0.120), "slightly wider"),
    "respread/step=0.100": (_respread(0.100, 0.120), "wider still"),
    "respread/step=0.110": (_respread(0.110, 0.120), "widest tested"),
    "respread/step=0.090/cm=0.060": (_respread(0.090, 0.060), "tighter clustering"),
    "minimal_move/step=0.090": (lambda p: _by_pair_axis(p, 0.090),
                                "move each landing the shortest distance"),
}


def evaluate(name, run, plans):
    """Measure one candidate on the archive. Returns a board row; never raises."""
    fixed = worse = refused = clearance_bad = untouched = 0
    devs = []
    for row in plans:
        plan = row["plan"]
        before = row["sep"]
        try:
            after_stages = run(plan)
        except (ValueError, KeyError):
            refused += 1
            continue
        after = _min_sep(after_stages)
        before_pts = _pts(plan["stages"])
        after_pts = _pts(after_stages)
        dev = max(math.hypot(a[0] - b[0], a[1] - b[1])
                  for a, b in zip(before_pts, after_pts))
        devs.append(dev)
        if dev < 1e-9:
            untouched += 1
        if after is not None and after >= SPREAD_CONTRACT_M - 1e-9:
            fixed += 1
        if after is not None and after < before - 1e-9:
            worse += 1
        if row["avoid"]:
            clr = _min_clearance(after_stages, row["avoid"])
            if clr is not None and clr < CLEARANCE_M - 1e-9:
                clearance_bad += 1
    return {"candidate": name, "plans": len(plans), "fixed": fixed,
            "worse": worse, "refused": refused, "clearance_violations": clearance_bad,
            "untouched": untouched,
            "mean_displacement_m": round(sum(devs) / len(devs), 4) if devs else None}


def admissible(row):
    """Return (ok, reason). Feasibility first; cost is only compared among the feasible."""
    if row["plans"] == 0:
        return False, "no plans to evaluate"
    if row["fixed"] < row["plans"]:
        return False, ("fixes %d of %d below-contract plans"
                       % (row["fixed"], row["plans"]))
    if row["worse"]:
        return False, "%d plan(s) end up with LESS separation" % row["worse"]
    if row["clearance_violations"]:
        return False, ("%d plan(s) end up inside the clearance contract"
                       % row["clearance_violations"])
    return True, "admissible"


def search(acceptance=None, plans=None):
    """Run the board and select. Returns (selected, board). Never falls back."""
    plans = plans if plans is not None else load_plans(acceptance)
    board = []
    for name, (run, intent) in CANDIDATES.items():
        row = evaluate(name, run, plans)
        row["intent"] = intent
        ok, why = admissible(row)
        row["admissible"] = ok
        row["why"] = why
        board.append(row)
    board.sort(key=lambda r: (not r["admissible"],
                              r["mean_displacement_m"] if r["mean_displacement_m"] is not None
                              else 9e9))
    chosen = board[0] if board and board[0]["admissible"] else None
    selected = chosen
    # Execute the tie-break, don't just describe it: among admissible candidates at the
    # LOWEST cost, prefer the incumbent. Sort stability alone would pick whichever happens
    # to be first in CANDIDATES -- an implementation accident, not a decision. Making it
    # explicit means reordering the dict cannot silently change the chosen parameter.
    if chosen is not None:
        best = chosen.get("mean_displacement_m")
        at_best = [r for r in board
                   if r.get("admissible") and r.get("mean_displacement_m") == best]
        incumbent = next((r for r in at_best
                          if str(r.get("intent", "")).startswith("the incumbent")), None)
        if incumbent is not None and incumbent is not chosen:
            selected = incumbent
    # A "cost-minimising search" that silently resolves a tie by dict insertion order is
    # not a selection -- it is an accident of how CANDIDATES was written. On this board the
    # incumbent and the tighter-clustering candidate tie exactly (both 0.0475 m, 33 fixed).
    # Record the tie and the TIE-BREAK PRINCIPLE explicitly: when feasible candidates cost
    # the same, keep the incumbent, because a CHANGE needs a reason whereas staying does not.
    # This makes the decision auditable instead of hiding it behind sort stability.
    if selected is not None:
        best_cost = selected.get("mean_displacement_m")
        ties = [r["candidate"] for r in board
                if r.get("admissible") and r.get("mean_displacement_m") == best_cost]
        selected["cost_ties"] = ties
        selected["tie_break"] = (
            "keep the incumbent among equal-cost feasible candidates; a change needs a "
            "reason, staying does not" if len(ties) > 1 else "unique lowest cost")
    return selected, board


if __name__ == "__main__":
    sel, board = search()
    print(json.dumps({"selected": sel, "board": board}, indent=2))
    sys.exit(0 if sel else 1)
