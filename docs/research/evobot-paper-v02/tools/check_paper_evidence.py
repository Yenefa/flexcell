"""Check claim identities/counts against immutable raw records; no model calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
CLAIMS = ROOT / "docs/research/evobot-paper-v02/CLAIMS_EVIDENCE_TABLE.md"


def check(claims=CLAIMS, root=ROOT):
    text = Path(claims).read_text(encoding="utf-8")
    problems = []
    for claim, name, condition in (
        ("R1", "confirmatory_f1bc.json", "B_REAL_FEEDBACK"),
        ("R2", "confirmatory_f1bc.json", "C_MISMATCHED_FEEDBACK"),
        ("R3", "real_instances_matrix.json", None),
        ("R4", "v2_matrix_n6.json", None),
    ):
        row = next((line for line in text.splitlines() if line.startswith("| %s |" % claim)), "")
        path = Path(root) / "experiments/repair_eval_v02/evidence" / name
        records = json.loads(path.read_text(encoding="utf-8"))["rows"]
        if condition:
            records = [r for r in records if r["condition"] == condition]
        sources = {r.get("source_sha") for r in records}
        if len(sources) != 1 or not all(isinstance(s, str) and len(s) == 40 for s in sources):
            problems.append(claim + ": absent or mixed source identity")
        expected = [str(s) for s in sources]
        expected += ["%d/%d" % (sum(r.get("gate_contract") == "PASS" for r in records), len(records))]
        if condition is None:
            expected += ["%d %s" % (sum(r["terminal_status"] == status for r in records), status)
                         for status in ("UNKNOWN", "BUDGET_EXHAUSTED")]
            expected += [format(sum(r["tokens_total"] for r in records), ",d")]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest not in text:
                problems.append(claim + ": raw byte digest missing or wrong")
        problems.extend(claim + ": missing or wrong " + token for token in expected if token not in row)
        if not row:
            problems.append(claim + ": missing claim row")
    return problems


def main():
    problems = check()
    print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
