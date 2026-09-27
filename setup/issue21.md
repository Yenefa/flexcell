**M2.2 Recovery Abstraction** (chief verdict: extract as a pure function — NOT a replacement for FSMPolicy)

Extract the recovery logic currently embedded in `FSMPolicy.decide()` replay semantics into a named, unit-testable component:

- **`recovery_eligible(...)` as a pure predicate** — the frozen rule (pick error ∈ {22,23,30} with typed outcome ⇒ REOBSERVE+RETRY; else ABORT) moved verbatim. FSMPolicy **delegates** to it; decisions must be bit-identical (the existing 15/15 policy tests passing unchanged is the proof).
- **Budget stays bounded and policy-owned**: the per-leg attempt math (1 + recovery_budget) remains in the FSMPolicy replay; the predicate only classifies eligibility, it does not count.
- **Recovery audit**: structured `recovery` block in the decision log (skill_error_code, attempt, budget_used, budget_cap, verdict). Recovery trajectories enter the audit log but never the policy context (B1 holds — policies see only HistoryRecord).
- Unit tests: predicate truth table + FSMPolicy regression (all existing tests untouched).

**Non-goals**: no BehaviorTree, no Open-RMF task system, no distributed recovery, no RoundRobin across recovery actions (single recovery recipe is the frozen Week-1.5 semantics).

**AC**: predicate tests green; FSMPolicy 15/15 green unchanged; Week-1.5 battery green; happy fsm_trace parity holds.
