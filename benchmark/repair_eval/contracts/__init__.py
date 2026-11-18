"""Versioned task contract and acceptance corpus for repair experiments (#250).

The package answers one question - "did this repair actually satisfy the user's
task?" - without reading the candidate's opinion of itself.

    task_contract  the frozen ruler: goal, objects, tolerances, editable fields,
                   protected digests, required evidence, run-id pattern
    acceptance     evaluate(contract, candidate_state) -> ACCEPT | REJECT | UNKNOWN
    casefile       the seven-case corpus and the false-accept / false-reject count
    cases/         one self-contained JSON per defect class, plus a valid repair

Import forms: the package works as a package (import
benchmark.repair_eval.contracts.acceptance), as a pytest target, and as a script
run by path. Each module puts its own directory on sys.path and then prefers a
relative import, so a package import sees ONE task_contract rather than two - two
copies would make the isinstance check in evaluate() reject a caller's contract.

Scope note: this is an offline policy layer over synthetic fixtures. It is not a
simulator run and it is not evidence that a robot performed the task.
"""
