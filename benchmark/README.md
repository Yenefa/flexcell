# benchmark/ — EvoBot Task Benchmark v0.1

Layout:

| Path | Contents |
| --- | --- |
| `schemas/` | TaskSpec JSON schema — the contract between generator and evaluator |
| `tasks/train/`, `tasks/val/` | instances the agent may execute |
| `held_out/` | instances the AGENT RUNTIME MUST NOT READ |
| `generators/` | `generate.py` (one instance), `build_sets.py` (materialise all splits) |
| `evaluators/` | `evaluate.py` — independent, pure, deterministic |
| `tests/` | offline tests, no ROS and no Gazebo |
| `manifest.json` | split counts and instance ids |

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
  "objects": {"target_box_a": [0.22, 0.0, 0.0175, 0.0]},
  "move_sequence": ["target_box_a", "target_box_b"],
  "agent_claimed_success": false
}
```

`objects` must cover EVERY object the spec declares. A missing object is graded as
a failure, because not-observed is not did-not-move.

`agent_claimed_success` never changes the measurement; it only feeds `false_success`,
which must stay at zero.

## Hard rule

The agent must not be able to read `held_out/` or `evaluators/` at run time.
That isolation is specified but NOT yet enforced — see `docs/TASK_BENCHMARK.md`
section 4. Until it is enforced, held-out numbers are not evidence of generalisation.
