# Agent team — 可运行、可验证的机器人（zyx）

Owner: zyx. Objective: finish the three deliverables in order, without touching the
frozen legacy baseline.

## Roster

| role | agent | owns | writes |
| --- | --- | --- | --- |
| Orchestrator | main session | sequencing, sim runs, final verification | `docs/AGENT_TEAM.md`, demo scripts, PRs |
| Builder | subagent (general) | independent acceptance CLI | `scripts/accept_run.py`, `scripts/tests/test_accept_run.py` |
| Documenter | subagent (general) | interface and demo docs | `docs/ACCEPTANCE_INTERFACE.md`, `docs/DEMO_GUIDE.md` |
| Reviewer | main session (review pass) | evidence check before PR | review notes only |

Disjoint file ownership is deliberate: no two agents write the same path.

## Sequence (1 → 2 → 3 → 4)

| step | deliverable | done when |
| --- | --- | --- |
| 1 | `accept_run.py` + interface doc | synthetic PASS/FAIL tests pass; a real run dir is accepted |
| 2 | continuous scene run | `RunDemo` completes two cycles in one session; results saved |
| 3 | demo recording | `demo.mp4` exists with duration and per-cycle results |
| 4 | detachable DUAL gap | tracked in #273; fixed after the competition |

## Rules

- No control-path change; the legacy `velocity_servo` baseline stays frozen.
- A claim needs evidence: command output, test result, file path.
- Steps run in order; step 2 starts only after step 1's tests pass.
- 100-round budget: stop and report if a step exceeds its estimate.

## Status log

| date | step | state |
| --- | --- | --- |
| 2026-11-18 | team formed | Builder and Documenter launched |
| 2026-11-18 | step 1 | `accept_run.py` + 9 tests pass; docs 360 + 281 lines |
| 2026-11-18 | step 2 | `RunDemo` 2/2 cycles passed (28.0 s / 27.8 s), zone errors 6.4-12.0 mm |
| 2026-11-18 | step 3 | `demo.mp4` 1920x1080, 120 s, 1.8 MB; captured frame verified non-black |
| 2026-11-18 | step 4 | detachable DUAL tracked in #273, fixed after the competition |
