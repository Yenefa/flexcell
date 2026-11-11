# Held-out isolation — ENFORCED, and it can fail

**Rung: Independently Verified (isolation mechanism only).**
This is not a benchmark result and not a generalisation claim. It closes the blocker that
made every earlier held-out number unusable: *"until isolation is enforced, held-out
numbers are not evidence of generalisation."*

## What was actually broken

Round 11 sealed the answers into `/etc/evobot/sealed` (root:root 700) and ran the agent as
uid 1001. That closed the answer *files*. It did **not** close the answer *function*:
`benchmark/generators/` stayed world-readable, and a held-out public task is a deterministic
function of `(template, seed)`. Measured, as uid 1001, with no privilege:

```
RECOVERED template=T12_triple_revisit seed=7009
expected_goal = {"placement": {"target_box_b": "zone_1"}, "unmoved": ["target_box_a"],
                 "visit": {"target_box_b": ["zone_2"]},
                 "visit_sequence": {"target_box_b": ["zone_1","zone_2","zone_1"]}}
attack_exit=0
```

That is the sealed answer for `HO-fd5737f932db`, reconstructed in under a second. A sealed
answer plus a readable oracle is an open book. Sealing alone was insufficient, and the
previous round's "BLOCKED_GOOD" checks did not test for this.

## The mechanism

`scripts/heldout_isolation.py`, owner **root:ros**, dirs **0750**, files **0640**:

| Path | Why it must be locked |
| --- | --- |
| `benchmark/held_out/` | enumerating it leaks the instance set |
| `benchmark/evaluators/` | the grading logic |
| `benchmark/generators/` | **the oracle** — the reconstruction path above |

uid 1001 has no passwd entry and no supplementary groups, so it matches neither owner nor
group and falls to "other" = no bits. `ros` is a real group (gid 1000), so the evaluator and
the offline suite keep working unchanged.

**Why not 0700 root:root** — that also locks out the evaluator and the test suite. The
requirement is bidirectional, so the group bit has to stay.

## Bidirectional verification (this is the point)

```bash
sudo -n python3 scripts/heldout_isolation.py apply
sudo -n python3 scripts/heldout_isolation.py verify    # exit 0
```

| Direction | Probe | Enforced state |
| --- | --- | --- |
| agent **cannot** read | `ls`/`cat` each locked prefix as uid 1001 | exit 2 / exit 1 (denied) |
| agent **cannot** reconstruct | import `unseen_tasks`, brute-force the seed | exit 1, `recovered_answer=false` |
| agent **cannot** read sealed | `cat /etc/evobot/sealed/*.json` | exit 1 |
| agent **still can** read train | `cat benchmark/tasks/train/T01-train-seed1000.json` | exit 0 (control) |
| evaluator **still grades** | full `sealed_evaluate.py` on a passing observation | `passed=true`, 4 clauses |
| evaluator **still rejects** | same evaluator on a failing observation | `passed=false` |

The last two matter as much as the first four: a lock that also locks out the evaluator
would "pass" an agent-side-only check while destroying the ability to grade at all.

## Mutation proof

```
$ sudo -n python3 scripts/heldout_isolation.py restore      # chmod back to 755
$ sudo -n python3 scripts/heldout_isolation.py verify
exit code: 1
verdict: HELDOUT_ISOLATION_NOT_ENFORCED
  static violations: 167
  FAILED PROBE: agent_blocked list:benchmark/held_out        exit=0
  FAILED PROBE: agent_blocked read:benchmark/held_out/...    exit=0
  FAILED PROBE: reconstruction:HO-42109d30fa00.json          exit=0
```

Recorded in `01_verify_MUTATED_755.json` / `.exit` (**exit 1**) versus
`03_verify_ENFORCED.json` / `.exit` (**exit 0**). `restore` is a supported command, not a
one-off chmod, so the mutation is reproducible.

Three further mutations were applied to the enforcement code itself and all were caught by
`benchmark/tests/test_heldout_isolation.py`:

| Mutation | Result |
| --- | --- |
| `DIR_MODE 0o750 -> 0o755` | **3 failed**, pytest exit 1 |
| drop `benchmark/generators` from `LOCKED_PREFIXES` | **1 failed**, pytest exit 1 |
| gate stops checking evaluator-side probes | **1 failed**, pytest exit 1 |

The third mutation initially **survived** — the test passed for the wrong reason (it failed
on the ownership check instead of the evaluator probe). The test was tightened until the
mutation was caught. That is recorded here because a test that cannot fail is the defect
this whole batch exists to remove.

## Runner integration (a break I had to fix)

`evobot_unified_runner_20261111/run_batch.sh` passed `$PUB` — a path *inside*
`benchmark/held_out/` — to the agent-side planner and self-assessor. Locking the directory
therefore broke the runner: the agent could not open its own input file.

Fix: `heldout_isolation.py stage-public <task.json> <run_dir>` copies **only public fields**
into the run directory (refusing any task carrying `expected_goal`/`constraints`/`template_id`/
`random_seed`), and the runner hands the agent that copy. The privileged side keeps using
the original path for grading. Verified end-to-end: agent reads its staged input (exit 0),
agent cannot read the original (exit 1), privileged side reads the original (exit 0).

## Residual risks — measured, not assumed

| Risk | Closed? | Measured |
| --- | --- | --- |
| Process running as **root** | **no** | yes — root reads the locked tree |
| **WSL interop**: uid 1001 runs `cmd.exe` and reads via the Win32 API | **no** | yes — `type` returned the file contents |
| Historical v0.1 held-out specs committed with answers in clear text | **no** | remain in git history; retired as contaminated |
| WSL `/mnt/c` permission semantics | holds here | 9p drvfs with `metadata`, so POSIX bits are enforced — verified, not assumed |

This is **OS permission isolation, not a kernel namespace.** It is not absolute safety. The
agent must be launched as uid 1001 with no sudo and no WSL interop; if it can reach a Windows
shell, it can read the same bytes through a path these bits do not govern. Closing that needs
`[interop] enabled=false` plus a distro restart, which would break the rest of this host, so
it is disclosed rather than silently claimed.

## Files

| File | Contents |
| --- | --- |
| `verify.py` | 9 checks, exit 0 only if enforced **and** mutation-detected |
| `00_restore_mutation.json` | the tree put back to 755 |
| `01_verify_MUTATED_755.json` / `.exit` | **exit 1** — mutation detected |
| `02_apply.json` | 167 paths locked |
| `03_verify_ENFORCED.json` / `.exit` | **exit 0** — enforced |
| `04_acceptance.json` / `.exit` | **exit 0** — 9/9 checks |
| `05_unit_tests.txt` / `.exit` | **exit 0** — 15 tests |
| `verdict.json` | the verifier's verdict record |

## Reproduce

```bash
cd /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
sudo -n python3 scripts/heldout_isolation.py apply
sudo -n python3 scripts/heldout_isolation.py verify --json
sudo -n python3 setup/acceptance/evobot_heldout_isolation_20261111/verify.py
python3 -m pytest benchmark/tests/test_heldout_isolation.py -q
```

## What this does and does not license

- **Does**: make it true that the agent process cannot read `benchmark/held_out/`,
  `benchmark/evaluators/`, or `benchmark/generators/`, and prove both directions.
- **Does not**: make any held-out *number* valid on its own. Numbers produced before this
  batch are still not generalisation evidence. This removes the blocker; it does not
  retroactively legitimise earlier runs.
- **Does not**: claim absolute safety. See residual risks.
