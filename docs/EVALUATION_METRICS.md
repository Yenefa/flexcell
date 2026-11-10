# EvoBot Evaluation Metrics

## Core metrics

| # | Metric | Definition | Current value |
| --- | --- | --- | --- |
| 1 | Task Success Rate | independent PASS / attempts, per template | 1/1 (Baseline A, one instance) |
| 2 | Subtask Completion Rate | completed stages / planned stages | 2/2 |
| 3 | Long-Horizon Success Rate | success on tasks with >= 4 stages | NOT MEASURED (no such task run) |
| 4 | Recovery Success Rate | recovered / recoverable failures | NOT MEASURED |
| 5 | **False Success Rate** | claimed PASS but graded FAIL / claimed PASS | **0.0** (must stay 0) |
| 6 | Regression Rate | previously passing val instances that broke | NOT MEASURED |
| 7 | Generalization Success Rate | success on held_out | **NOT MEASURED — seal not enforced** |
| 8 | Skill Reuse Rate | stages using an existing skill / total stages | 2/2 (both reused) |
| 9 | Experience Transfer Rate | tasks improved by retrieved experience | NOT MEASURED |
| 10 | Human Intervention Rate | runs needing a human to unblock | 0 (this round, but the human wrote the plan logic) |
| 11 | Task Completion Time | wall clock per instance | 28.9 s (composite run) |
| 12 | Token and API cost | per instance | 0 (Baseline A uses no model) |

## The one hard constraint

**False Success Rate must be 0.**

It is measured, not assumed: the evaluator compares the agent's claim against its own
verdict and reports `false_success`. An arm that claims nothing cannot produce a
false success — silence is not a false claim — but it also cannot pass on its word.

A run that fails the evaluator is a failure even if every skill returned success.
That is the difference between `outcome=0` from the robot and `passed=true` from the
evaluator, and the first does not imply the second.

## Reporting rules

- always report n;
- never report a confidence interval on n=1;
- report the failure distribution, not only the successes;
- report resource consumption per arm so a budget advantage cannot masquerade as a
  capability advantage;
- state which rung of the evidence ladder each claim rests on.
