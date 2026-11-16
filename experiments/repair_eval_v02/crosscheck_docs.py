"""Cross-check the four document sets against the code they describe.

WHY
    The same vocabulary appears in four places: the visibility policy and its doc
    (#249), the contract and its doc (#250), the protocol package (#251) and the
    method section (#254). Each has its own tests, and each test checks its own
    file - which is exactly how the protocol came to promise condition B the
    verdict that the policy seals, and how the interface table came to list six
    denial codes when the module has nine.

    Reading the documents side by side did not catch either; comparing them
    mechanically did. So the comparison is a script.

WHAT IT CHECKS
    Numbers, enums and code names that appear in more than one place. It does not
    check prose: a sentence can still be wrong while every token matches. That is
    the reason the method section carries an explicit "what this cannot support".
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import acceptance                                        # noqa: E402
import budget as B                                       # noqa: E402
import reconcile as RC                                   # noqa: E402
import run_record as RR                                  # noqa: E402

PROTOCOL_DOCS = ROOT / "docs" / "research" / "evobot-paper-v02"
VISIBILITY_DOC = ROOT / "docs" / "repair_eval" / "VISIBILITY.md"
CONTRACT_DOC = ROOT / "docs" / "repair_eval" / "TASK_CONTRACT.md"
VISIBILITY_SRC = ROOT / "benchmark" / "repair_eval" / "visibility.py"

DENIAL_RE = re.compile(r'^([A-Z][A-Z_]+) = "([a-z_]+)"$', re.MULTILINE)


def read(path):
    return Path(path).read_text(encoding="utf-8")


def denial_codes():
    """Every denial-code constant the visibility module defines."""
    return sorted({m.group(2) for m in DENIAL_RE.finditer(read(VISIBILITY_SRC))})


def check():
    """Return a list of disagreements. An empty list means they agree."""
    problems = []
    dic = read(PROTOCOL_DOCS / "DATA_DICTIONARY.md")
    proto = read(PROTOCOL_DOCS / "PROTOCOL.md")
    manifest = read(PROTOCOL_DOCS / "RUN_MANIFEST.md")
    contract_doc = read(CONTRACT_DOC)
    visibility_doc = read(VISIBILITY_DOC)
    assumptions = read(PROTOCOL_DOCS / "ASSUMPTIONS.md")

    # 1. the budget caps must be the same number in code and in each document
    #    separately. Joining the two documents first would let a wrong number in
    #    one be covered by the right number in the other - measured: that version
    #    survived a mutation.
    tokens_text = str(B.DEFAULT_TOKENS)
    for label, text in (("PROTOCOL", proto), ("DATA_DICTIONARY", dic)):
        if tokens_text not in text.replace(",", ""):
            problems.append("budget: %s does not state %d tokens"
                            % (label, B.DEFAULT_TOKENS))
    if ("%d 次" % B.DEFAULT_INTERACTIONS) not in proto:
        problems.append("budget: PROTOCOL does not state %d interactions"
                        % B.DEFAULT_INTERACTIONS)

    # 2. the status vocabulary is one list
    for status in RC.KNOWN_STATUSES:
        if status not in manifest:
            problems.append("status %r is in reconcile.py but not in RUN_MANIFEST" % status)

    # 3. the information-supply enum is one list
    for source in RR.FEEDBACK_SOURCES:
        if source not in dic:
            problems.append("feedback_source %r is in run_record.py but not in "
                            "DATA_DICTIONARY" % source)

    # 4. every denial code the module can raise is named in both docs that claim
    #    to list them
    for code in denial_codes():
        if code not in visibility_doc:
            problems.append("denial code %r is in visibility.py but not in VISIBILITY.md"
                            % code)
        if code not in assumptions:
            problems.append("denial code %r is in visibility.py but not in the "
                            "interface table (ASSUMPTIONS.md)" % code)

    # 5. every reason code the evaluator can emit is documented, and the level the
    #    document assigns it is the level the evaluator gives it. Presence alone is
    #    not enough: a code documented as REJECT while the evaluator returns UNKNOWN
    #    is the kind of drift that reads correctly in both files.
    documented = dict(re.findall(r"^\| `([A-Z][A-Z_]{3,})` \| (REJECT|UNKNOWN) \|",
                                 contract_doc, re.MULTILINE))
    for code, (level, _description) in acceptance.REASONS.items():
        if code not in documented:
            problems.append("reason code %r is in acceptance.py but has no row in "
                            "TASK_CONTRACT.md" % code)
        elif documented[code] != level:
            problems.append("reason code %r is documented as %s but the evaluator "
                            "returns it as %s" % (code, documented[code], level))
    return problems


def main():
    problems = check()
    print("denial codes in the module: %d" % len(denial_codes()))
    print("reason codes in the evaluator: %d" % len(acceptance.REASONS))
    if problems:
        print("DISAGREEMENTS (%d):" % len(problems))
        for problem in problems:
            print("  - " + problem)
        return 1
    print("documents and code agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
