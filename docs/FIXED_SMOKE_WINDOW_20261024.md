# Fixed smoke windows for baseline admission

Refs #31, #8 and #12. This change is based on PR #28 at
`071fa1451d07ad2aeb300d176731f2d00d4fa910`; it retains that PR's Hybrid
source/threshold gates. PR #40's abort and deployment-metadata work is separate.

The old runner selected passing rows from the supplied smoke JSONL and checked
whether at least five remained. Eight successes among ten attempts therefore
qualified despite two failed attempts. Five copies of one successful episode
also qualified. Neither file establishes five independent passing attempts in a
fixed window.

## New batches

Before the first reset, the runner exclusively creates a uniquely named summary
and a `batch_plans/<batch_id>.json` sidecar. The plan freezes policy, stage,
protocol SHA, scenario counts/order, per-attempt seeds and expected outcomes.
Hybrid also freezes the deployment fingerprint, threshold and fast-model,
weight and calibration identities. The loop executes that stored schedule.

Every completed JSONL row records the plan SHA, batch ID, native episode SHA,
evidence ID and local episode basename. Plans live outside the root-level
episode JSON enumeration. A repeated scenario argument is rejected, closing
the `S1:3 S1:3` smoke-cap bypass. Existing output files are not appended to or
overwritten; partial rows remain available after an interrupted batch.

## Baseline admission

`--smoke-summary` requires its original basename and adjacent `batch_plans/`
sidecar. The entire declared window must have exactly five attempts per cell,
complete rows in planned order and matching seeds, policy and protocol. All
declared cells must pass, including cells outside the requested baseline subset.
No rows are discarded to obtain five successes.

Each row must exercise its scenario, have no harness error, and match its
expected task outcome and client exit. S4/S5 expected failures can pass their
functional checks; they remain task failures in reported success rates. FSM
replay must pass; model-decision counts must be positive integers. Runtime
fingerprints must be present and identical.

Admission rereads every native file, verifies schema, SHA, unique path/evidence
ID, policy, protocol, runtime and terminal result. A changed summary cannot turn
a native failure into success. Hybrid native routing is re-audited against the
frozen deployment and compared with the saved audit, followed by PR #28's whole
batch audit. Real fast calls may all escalate to the slow arm.

Copied batches retain their summary basename, plan sidecar and native episode
basenames. Verification uses those copied local files rather than silently
following stale absolute paths back to the original machine. Missing native
files remain missing and block admission.

## Evidence and limits

[Local validation and counterexamples](../setup/acceptance/fixed_smoke_window_20261024/)
contain a fresh ROS Jazzy build of interfaces/skills and **330 tests, zero
errors/failures/skips**. Forty-six new cases cover complete/failed/truncated/
pooled windows, duplicates, file changes, relocation, unknown schemas, source
drift, native terminal results and real CLI admission with synthetic transports.
The scanner reports 36 source files and zero problems.

The actual old and new CLI entrypoints were compared using synthetic files.
Both pooled and duplicated evidence reach the old transport boundary and are
rejected with exit 2 before the new boundary. A complete positive control reaches
both boundaries. Every comparison stops before transport: zero robot and model
calls. This checks admission behavior, without claiming robot qualification.

E-021 is corrected to dual-object RunDemo and **10 pooled attempts: 8 SUCCEEDED,
2 FAILED**. The three baseline files retain their original counts of 19/20,
18/20 and 17/20; raw bytes are unchanged. Their 60 native episode references are
missing from this checkout and the current laptop episode store. The exact
inventory and summary hashes are archived, without claiming global loss.

Legacy summaries remain descriptive records and cannot be retrospectively given
a predeclared plan. This repair neither supplies missing episodes nor qualifies
historical experiments. It checks one supplied window, not a campaign registry
or a tamper-proof signature. Failed windows must remain reported; choosing a new
window after a failure is not authorization to repeat until green. A repaired
deployment needs its own frozen protocol/fingerprint and qualification decision.
No robot batches or model services were started here, and n≥50/full M3 remain
frozen. The broader native recovery and model replay work in #31 stays open.
