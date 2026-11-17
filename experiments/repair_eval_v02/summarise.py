"""Report a batch so that censored observations cannot masquerade as stable ones.

WHY THIS EXISTS
    The first real matrix reported F2 condition A as "6.0 interactions, sd 0.00".
    That reads like a stable measurement and is the opposite: every slot in the
    cell hit the interaction cap, so the number describes the cap, not the
    repair. Comparing condition means under censoring compares who reached the
    ceiling first.

    The harness cap is 6, and half the matrix reached it. Any summary that prints
    a mean without saying how many observations were cut off is therefore
    misleading for this data - and the fix is not a caveat in prose, it is a
    number in the table.

WHAT IT REPORTS
    Primary: how many slots satisfied the sealed gate. That is a binary outcome
    and censoring does not distort it.

    Secondary: interactions and tokens, with the censored count printed next to
    them. A cell whose every observation is censored is flagged as describing the
    cap rather than the work.
"""
import json
import statistics as st
import sys
from pathlib import Path


def load(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return doc.get("rows", [])


def is_censored(row, cap=None):
    """A slot that stopped because the harness stopped it, not because it finished.

    Terminal status alone undercounts: a slot can sit exactly on the cap and
    still be recorded as UNKNOWN because the gate happened to pass. F2 condition A
    did that in all three repetitions, which is why its mean is a clean 6.00 with
    sd 0.00 - the ceiling, not the work. Both counts are reported.
    """
    used = row.get("interactions_used")
    at_cap = (cap is not None and used == cap)
    if str(row.get("terminal_status") or "") == "BUDGET_EXHAUSTED":
        return True
    return at_cap


def summarise(rows, cap=6):
    cells = {}
    for row in rows:
        family = str(row.get("slot_id", "")).split("-")[0]
        key = (family, str(row.get("condition", "")))
        cell = cells.setdefault(key, {"n": 0, "gate_pass": 0, "censored": 0,
                                      "at_cap": 0, "interactions": [], "tokens": []})
        cell["n"] += 1
        if not (row.get("gate_contract_codes") or []):
            cell["gate_pass"] += 1
        if is_censored(row, cap):
            cell["censored"] += 1
        if cap is not None and (row.get("interactions_used") or 0) == cap:
            cell["at_cap"] += 1
        cell["interactions"].append(row.get("interactions_used") or 0)
        cell["tokens"].append(row.get("tokens_total") or 0)
    for key, cell in cells.items():
        values = cell["interactions"]
        cell["mean_interactions"] = round(st.mean(values), 2)
        cell["sd_interactions"] = round(st.stdev(values), 2) if len(values) > 1 else 0.0
        cell["mean_tokens"] = int(st.mean(cell["tokens"]))
        # the honest label: a cell whose observations are all censored has no
        # distribution to summarise
        cell["all_censored"] = cell["at_cap"] == cell["n"]
    return cells


def render(cells):
    lines = ["%-3s %-22s %3s %6s %6s %8s %8s %8s" %
             ("fam", "condition", "n", "PASS", "cen/cap", "mean_int", "sd_int", "mean_tok")]
    for (family, condition) in sorted(cells):
        cell = cells[(family, condition)]
        flag = ""
        if cell["all_censored"]:
            flag = "  <- every slot stopped (or sat) at the cap: this describes the cap"
        else:
            if cell["at_cap"]:
                flag = "  <- %d of %d sat at the cap" % (cell["at_cap"], cell["n"])
        lines.append("%-3s %-22s %3d %6d %6s %8.2f %8.2f %8d%s" % (
            family, condition, cell["n"], cell["gate_pass"],
            "%d/%d" % (cell["censored"], cell["at_cap"]),
            cell["mean_interactions"], cell["sd_interactions"],
            cell["mean_tokens"], flag))
    lines.append("")
    lines.append("PASS counts slots the sealed gate accepted. No success rate is printed:")
    lines.append("every terminal state here is UNKNOWN, which the denominator rules exclude.")
    return chr(10).join(lines)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: summarise.py <evidence.json> [...]")
        return 2
    rows = []
    for path in argv:
        rows.extend(load(path))
    cells = summarise(rows)
    print(render(cells))
    print(json.dumps({"%s|%s" % k: v for k, v in cells.items()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
