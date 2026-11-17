# Current status index (navigation only)

This page is a navigation layer: it links the authoritative goal, the existing evidence,
the withdrawn judgments, the current mainline and the open verifications. It re-decides
nothing and re-audits nothing. The frozen 2026-10-27 D3 decision (recorded as `NO_GO`), the
default carry backend and the n >= 50 model-batch freeze stay exactly as recorded in
[DETACHABLE_ADMISSION_20261027.md](DETACHABLE_ADMISSION_20261027.md).

Evidence grades, in the repo's wording (the ladder itself is defined in
[AGENT_HANDOFF.md](AGENT_HANDOFF.md) section 2): `代码实现` present in source;
`合成测试` offline or synthetic tests; `仿真执行` executed in Gazebo; `独立验收`
independently re-graded or independent CI; `未执行` not run - document and authority
lookups are graded here too, because reading a file is not an execution; `UNKNOWN`
cannot be confirmed from repository evidence. Any statement without a confirmable source
must say UNKNOWN; there is no such unmarked row below.

## 1. Authoritative objective

| Item | What it fixes | Grade | Source |
| --- | --- | --- | --- |
| Mission issued by the user, to be kept verbatim | The repository copy is truncated at section 8; sections 8-14 are `SOURCE_MISSING` in that copy | UNKNOWN | [MISSION_TEXT_STATUS_20261112.md](MISSION_TEXT_STATUS_20261112.md) |
| Sections 8-14 body | Supplied verbatim by the mission author on 2026-11-12, after the truncation was reported; the author does not assert it matches the repository file word for word | 未执行 | [EVOBOT_NORTH_STAR_MISSION_S8_S14_AUTHORITATIVE.md](EVOBOT_NORTH_STAR_MISSION_S8_S14_AUTHORITATIVE.md) |
| Execution layer | `EVOBOT_MASTER_GOAL_20261112.md` is a supplement; it may not override or redefine the Mission | 未执行 | [EVOBOT_MASTER_GOAL_20261112.md](EVOBOT_MASTER_GOAL_20261112.md) |
| Baseline `D` | No definition in the available sources: P4 waits on a definition decision, not on a missing document | UNKNOWN | [MISSION_TEXT_STATUS_20261112.md](MISSION_TEXT_STATUS_20261112.md) |
| Agent entry point | `AGENTS.md` sends development work to the Master Goal and to the append-only fact state | 未执行 | [AGENTS.md](../AGENTS.md) |

## 2. Existing evidence

| Layer | What it may be cited for | Grade | Source |
| --- | --- | --- | --- |
| Append-only fact register | What is CITED, what was WITHDRAWN, and which numbers may not be quoted; supersedes any conflicting older row | 独立验收 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| Capability ladder | Recomputed counts read from the archive: 60 valid batches, 0 verifier failures, 352 offline tests | 独立验收 | [CAPABILITY_LADDER.md](CAPABILITY_LADDER.md) |
| T08 push | `Simulation Tested` - 2 clean held-out instances (n=2), zero false success; not a generalization study | 仿真执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| Public Runtime task execution | Two stages, 24/40 actuator goals, final signed-x 60.9318 mm, full 9/9, on execution source `22f873ba` | 独立验收 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| Architecture checkpoint 2026-11-15 | Worktree isolation and module decoupling at implementation `18473aa8`, off physical checkpoint `81eed33c` | 独立验收 | [docs/architecture/20261115/README.md](architecture/20261115/README.md) |
| Reachable-contact repair | `LONG_1`/`LONG_2` full 9/9 at source `31a002f6`, net 91.3890225/91.4078218 mm, no sample replacement | 仿真执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| Differential benchmark comparison | 352 collected, `339 passed` and the same 13 failed on both sides; no new failure and no lost test | 合成测试 | [docs/architecture/20261115/README.md](architecture/20261115/README.md) |
| D3 admission evidence | Six #57 criteria, their window IDs, observed values, evidence boundaries and gaps | 未执行 | [D3_STATUS_CURRENT.md](D3_STATUS_CURRENT.md) |
| Evidence-archive boundary | `setup/acceptance/` is immutable and is not part of this sparse checkout, so those receipts cannot be opened here | UNKNOWN | [EVIDENCE_ARCHIVE.md](EVIDENCE_ARCHIVE.md) |

## 3. Withdrawn or corrected judgments (kept, never deleted)

| Withdrawn or corrected claim | Current state | Grade | Source |
| --- | --- | --- | --- |
| A-v0's 44/72 as a capability measure | INVALID - process leak, 136 orphans | UNKNOWN | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| A-v2's 72 verdicts under one evaluator | INVALID as one measurement - the archive mixes evaluator 0.2.0/0.3.0/0.4.0; re-grading all 72 with v0.5.0 reproduces 72/72 | 独立验收 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| The A-prime versus B "paired comparison" | MISLABELLED - the A-prime column is the ORACLE; a genuine A-prime paired execution is NOT_RUN | 未执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| `evobot_p0_paired.sh` as the paired-execution producer | BROKEN - has never run; no `paired.tsv` exists anywhere | 未执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| "This arm cannot perform T08" (goal round 17) | WITHDRAWN - the harness withheld the trajectory the frozen evaluator requires | 仿真执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| The paired 0/26 result | VOID - every state file lacked a `trajectory` key, so the clause failed closed for every trial | 未执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| "T08 Generalization Tested", widths 9 then 5 then 3 | Label overturned by independent review; the surviving statement is `Simulation Tested`, n=2 | 仿真执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| "The evaluator was modified outside review" | STALE PIN, not an unauthorised change; the bookkeeping defect is still open | 代码实现 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| "Six assertions all OK" in the static-parent probe | Five assertions plus one observation; exit 0 means the probe's own assertions held | 仿真执行 | [BACKEND_ADMISSION_20261027.md](BACKEND_ADMISSION_20261027.md) |
| "contact_made=false means no physical contact" | Withdrawn - B1's first stroke reports false while carrying 140 native pusher-contact steps | 仿真执行 | [ARCHITECTURE_REVIEW_20261112.md](ARCHITECTURE_REVIEW_20261112.md) |
| "The experience channel contains no actionable lesson" (symptom) | Root cause recorded: the planner is never wrong in the archive - 0 of 64 runs planning-attributable | 独立验收 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |

## 4. Current mainline

| Line | State | Grade | Source |
| --- | --- | --- | --- |
| Architecture workstream `refactor/modular-workspace-20261115` | ACTIVE - this branch; implementation `18473aa8` off physical checkpoint `81eed33c`; 13 runtime-to-research dependency exceptions at 0 across 85 scanned files | 代码实现 | [DEVELOPMENT_BRANCHES.md](DEVELOPMENT_BRANCHES.md) |
| Independent CI for that checkpoint | skill-boundaries `43721840130` all four jobs and repository-layout `43722188657` | 独立验收 | [docs/architecture/20261115/README.md](architecture/20261115/README.md) |
| Physical workstream `develop/physical-capabilities-20261113` | CHECKPOINTED at `81eed33c`, not merged forward into the architecture line | 仿真执行 | [DEVELOPMENT_BRANCHES.md](DEVELOPMENT_BRANCHES.md) |
| Formal status of the capability claims | T08 stays `CALIBRATION_UNSUPPORTED`, formal baseline NOT_PROMOTED, L4 not acquired, main goal active | 未执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| D3 admission | Default decision of 2026-10-27 unchanged, default carry backend unchanged, n >= 50 frozen | 未执行 | [DETACHABLE_ADMISSION_20261027.md](DETACHABLE_ADMISSION_20261027.md) |
| Public Runtime integration | Execution confirmed on `22f873ba`; later refactor phases extract modules without repeating the physical trial | 仿真执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |

## 5. Open verifications

| Open item | Why it is still open | Grade | Source |
| --- | --- | --- | --- |
| Genuine A-prime versus B paired execution | Assigned and never run; every existing table compares the oracle against B | 未执行 | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| #59 CI execution of the legacy skill matrix | The job exists in `.github/workflows/sim.yml` but is gated on `workflow_dispatch` plus `legacy_parity`; the latest dispatch run `42401973181` records it `skipped` with 0 steps | 未执行 | [run 42401973181](https://github.com/Yenefa/flexcell/actions/runs/42401973181) |
| Historical native-five-cycle stream-stale failure | Run `41116653853` at `c2583ae` was 787.690270 ms stale; the consumer-pause source is UNKNOWN and was never reproduced | UNKNOWN | [NATIVE_AUDIT_LIFETIME_20261031.md](NATIVE_AUDIT_LIFETIME_20261031.md) |
| Actions jobs that never started | Runs `41202950948`/`41202950949` at `9a923e7` show 0 steps; the annotation names failed payments or a spending limit without saying which | 未执行 | [NATIVE_AUDIT_LIFETIME_20261031.md](NATIVE_AUDIT_LIFETIME_20261031.md) |
| D3 criterion 4, the 500 Hz step | World step is 5 ms; `real_time_update_rate=500` is not a 2 ms step, and contact forces were not collected | UNKNOWN | [D3_STATUS_CURRENT.md](D3_STATUS_CURRENT.md) |
| D3 criteria 1, 3 and 5 residues | No contact measurement before attach, no saved per-frame free-fall fit input, and the joint-by-legacy window sits at 45.007 mm against a 60 mm tolerance | UNKNOWN | [D3_STATUS_CURRENT.md](D3_STATUS_CURRENT.md) |
| #237 scheduling stall, #238 old fixtures, #239 invalid CI_L0 control | Open tracking issues; none is closed by a documentation change | 未执行 | [#237](https://github.com/Yenefa/flexcell/issues/237), [#238](https://github.com/Yenefa/flexcell/issues/238), [#239](https://github.com/Yenefa/flexcell/issues/239) |
| Development Skill effect | Adoption is 0 across 295 branches and 819 commits; there is no load path, so the effect is unmeasured rather than absent | UNKNOWN | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| P4 transfer and baseline D | `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`, and D is undefined in the available sources | UNKNOWN | [FACT_STATE_20261112.md](FACT_STATE_20261112.md) |
| Real hardware and standing budgets | M0 has never run; model batches stay at n >= 50 and no hardware or paid-call step is approved here | 未执行 | [CAPABILITY_LADDER.md](CAPABILITY_LADDER.md) |

## Self-check

The checker is read-only and lives outside the repository. Run it from the workspace root:

```powershell
& "C:\Users\fuker\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" _coup\_check_docs.py
```

It enforces the 110-line cap of this file, the per-row link-or-UNKNOWN rule, and the
absence of any new admission wording in either page; it prints counts and ends with
`_CHECK_DOCS_OK`. It encodes the boundaries of both pages, so it must be re-run after
any edit to this file or to [D3_STATUS_CURRENT.md](D3_STATUS_CURRENT.md).
