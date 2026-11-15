# Evidence archive boundary

## Why this exists

`setup/acceptance/` is immutable evidence: it records what a run produced and is
never edited afterwards. It is also **662 MB of the repository's 678 MB** (97.7%),
while `src/` - all the source code - is 1.7 MB (0.24%). Seven frozen copies of
`flexcell_skills` live under `experiments/pilot-001/runs/`, and package discovery
only stays correct because of a hand-written `COLCON_IGNORE`.

That is a repository boundary problem, not a code-coupling problem: the archive,
the current source, the experiment snapshots and the CI criteria share one
working tree and one set of relative paths.

## The contract

| Part | Lives in | Why |
| --- | --- | --- |
| Current source | `src/` | changes every day |
| Evidence bytes | **outside the repository**, resolved via `FLEXCELL_EVIDENCE_ROOT` | immutable, 662 MB, read rarely |
| Evidence manifest | `config/evidence_manifest.json` | lets a reader prove the bytes it was given are the bytes that were frozen |
| Readers | tests and tools | resolve through the evidence root instead of a bare relative path |

`FLEXCELL_EVIDENCE_ROOT` defaults to the repository root, so a full in-tree
checkout keeps working unchanged - the indirection is not a behaviour change.

## Commands

```bash
# freeze the archive's current content
python3 scripts/evidence_manifest.py generate

# prove an archive (in-tree or relocated) still matches the frozen content
python3 scripts/evidence_manifest.py verify
FLEXCELL_EVIDENCE_ROOT=/mnt/evidence python3 scripts/evidence_manifest.py verify
```

`verify` exits non-zero on missing, extra or changed files. CI runs it only once
`config/evidence_manifest.json` exists, so the step is inert until the archive is
actually moved.

## Readers that already resolve through the evidence root

- `src/flexcell/flexcell_skills/test/test_carry_loop_observation.py`
- `src/flexcell/flexcell_skills/test/test_native_portable_sources.py`
- `src/flexcell/flexcell_skills/test/test_parity_report.py`
- `src/flexcell/flexcell_skills/test/test_public_contact_runtime.py`
- `benchmark/tests/test_ground_truth.py`
- `benchmark/tests/test_observation_bridge.py`

## Readers that still hard-code the archive path

Deliberately left alone for now - each needs a decision, not a mechanical edit:

- `benchmark/tools/compare_plans.py` (`B_DIR`) - operator tool, not CI.
- `benchmark/tests/test_baseline_c.py`, `test_bc_pair.py`, `test_unseen_tasks.py`,
  `test_runner_hygiene.py` - these only assert that *strings appear in a path
  list*; no archive is read.
- `evolution/validation/regress.py`, `gate_differential.py` - scan every verifier
  under `setup/acceptance/` by design; relocating requires a verifier index.

## Migration order

1. Write the manifest (`generate`), commit it. Nothing moves; `verify` must pass.
2. Land the reader indirection (this document's six readers) - already done.
3. Add the `COLCON_IGNORE` replacement: CI asserts the discovered package set
   instead of trusting a file. Already added to `ci.yml`.
4. Move the bytes out of the tree and keep only the manifest. Re-check with
   `verify` and `colcon list`.

Steps 1-3 change nothing about what the evidence says, in line with the standing
rule that frozen evidence is never rewritten.
