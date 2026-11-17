"""Load a registered slot sequence; never invent order, seeds or donors."""
import hashlib
import json
from pathlib import Path
import re

FAMILIES = {"F1": "F1_OBJECT_REGISTRATION", "F2": "F2_GOAL_MAPPING"}
CONDITIONS = dict(zip("ABCD", ("A_STATIC", "B_REAL_FEEDBACK", "C_MISMATCHED_FEEDBACK", "D_GUIDED")))
SLOT = re.compile(r"^(F[12])-([ABCD])-r([1-9][0-9]*)$")
DEFAULT = Path(__file__).resolve().parents[2] / "docs/research/evobot-paper-v02/RUN_MANIFEST.md"


def load(path=DEFAULT):
    path = Path(path)
    content = path.read_bytes()
    if path.suffix == ".json":
        raw = json.loads(content)
        if raw.get("schema") != "evobot.dispatch_plan/1" or not raw.get("plan_id"):
            raise ValueError("versioned dispatch plan and plan_id required")
        slots = raw["slots"]
        plan_id = raw["plan_id"]
    else:
        slots = []
        for line in content.decode("utf-8").splitlines():
            if not re.match(r"^\|\s*\d+\s*\|", line):
                continue
            cells = [x.strip().strip("`") for x in line.strip("|").split("|")]
            slots.append({"slot_id": cells[1], "seed": int(cells[6]),
                          "donor_run_id": None if cells[7] in ("—", "-", "") else cells[7]})
        plan_id = "registered-markdown:" + path.name
    if not slots or len({s["slot_id"] for s in slots}) != len(slots):
        raise ValueError("dispatch plan requires nonempty unique slots")
    for slot in slots:
        match = SLOT.fullmatch(slot["slot_id"])
        if not match or isinstance(slot.get("seed"), bool) or not isinstance(slot.get("seed"), int):
            raise ValueError("invalid slot or seed: %r" % slot)
        family, condition, rep = match.groups()
        slot.update(family=FAMILIES[family], condition=CONDITIONS[condition], rep=int(rep))
        donor = slot.get("donor_run_id")
        if condition == "C":
            source = SLOT.fullmatch(donor or "")
            if not source or source[1] != family or source[2] != "B" or source[3] == rep:
                raise ValueError("C requires a frozen same-family B donor at another repetition")
        elif donor:
            raise ValueError("only C may borrow a donor")
    return {"schema": "evobot.dispatch_plan/1", "plan_id": plan_id,
            "source_path": str(path.resolve()), "sha256": hashlib.sha256(content).hexdigest(),
            "slots": slots}


def select(plan, families, conditions, reps):
    expected = {(f, c, r) for f in families for c in conditions for r in reps}
    slots = [dict(s) for s in plan["slots"] if (s["family"], s["condition"], s["rep"]) in expected]
    if {(s["family"], s["condition"], s["rep"]) for s in slots} != expected:
        raise ValueError("requested slots are not registered; provide a new --plan before execution")
    return slots
