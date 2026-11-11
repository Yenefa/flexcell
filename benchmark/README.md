# benchmark/ — EvoBot Task Benchmark v0.1

Layout:

| Path                         | Contents                                                               |
| ---------------------------- | ---------------------------------------------------------------------- |
| `schemas/`                   | TaskSpec JSON schema — the contract between generator and evaluator    |
| `tasks/train/`, `tasks/val/` | instances the agent may execute                                        |
| `held_out/`                  | instances the AGENT RUNTIME MUST NOT READ                              |
| `generators/`                | `generate.py` (one instance), `build_sets.py` (materialise all splits) |
| `evaluators/`                | `evaluate.py` — independent, pure, deterministic                       |
| `tests/`                     | offline tests, no ROS and no Gazebo                                    |
| `manifest.json`              | split counts and instance ids                                          |

## Reproduce

```bash
python3 benchmark/generators/build_sets.py     # regenerate all 144 instances
python3 -m pytest benchmark/tests -q           # 12 tests, no robot needed

python3 benchmark/generators/generate.py --template T01_multi_object_sorting --seed 1000
python3 benchmark/evaluators/evaluate.py <spec.json> <final_state.json>
```

## Observation format expected by the evaluator

```json
{
  "objects": { "target_box_a": [0.22, 0.0, 0.0175, 0.0] },
  "move_sequence": ["target_box_a", "target_box_b"],
  "agent_claimed_success": false
}
```

`objects` must cover EVERY object the spec declares. A missing object is graded as
a failure, because not-observed is not did-not-move.

`agent_claimed_success` never changes the measurement; it only feeds `false_success`,
which must stay at zero.

## Hard rule — ENFORCED

The agent must not be able to read `held_out/`, `evaluators/`, or `generators/` at run time.

**This is now enforced and machine-verified**, not documented. `scripts/heldout_isolation.py`
sets those three trees to `root:ros 0750/0640`; the agent runs as uid 1001 with no groups
and is denied, while the evaluator (root, or ros in group `ros`) keeps grading. Verify with:

```bash
sudo -n python3 scripts/heldout_isolation.py verify --json   # exit 0 = enforced
```

`generators/` is in the list because sealing the answers is not sufficient: a held-out task
is a deterministic function of `(template, seed)`, so a readable generator lets the agent
reconstruct the sealed `expected_goal` from the public task. That reconstruction was
measured, not hypothesised — see `setup/acceptance/evobot_heldout_isolation_20261111/`.

The mechanism is OS permissions, **not a kernel namespace**. It does not stop a root
process, and it does not stop WSL interop (uid 1001 running a Windows binary). Both are
measured and reported by the verifier. It also does not retroactively legitimise held-out
numbers produced before it was enforced.

Runner note: the agent cannot open a path inside `held_out/` any more, so hand it a staged
copy — `heldout_isolation.py stage-public <task.json> <run_dir>`. Only public fields are
copied; the sealed answer never leaves `/etc/evobot/sealed`.
