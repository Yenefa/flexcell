# CLEF-RECORDED-001 — receipt from the household RX 6800 Vulkan service

This is the missing half of `PR #39`: the recorded-input regression was
executed on the machine that actually hosts the Clef GGUF service, and the
result is archived here as bytes rather than reported as a conclusion.

Everything below was produced on the same machine in one session on
2026-10-24. The receipt keeps the distinction the task asked for — **what was
measured** versus **what merely follows from the files**.

## What was run

```
commit     6fe61914a64a84dfe0a860ad15e9b6bc93bc42cb
branch     research/smolvla-gpu-handoff
python     3.13.14 (MSC v.1944 64 bit (AMD64))
command    python setup/model_validation/run_clef_replay.py \
             --weights "F:\flexcell-models\Clef-Flash-Q8_0.gguf" \
             --out "setup/model_validation/reports/clef_20261024T131429Z.json"
exit       0
```

Twenty recorded decisions taken from three archived episodes, sent to the
production `ClefBackend` / `JevPolicy` path at `http://127.0.0.1:11435/v1/systemone`.

| | run 1 (`…T131246Z`) | run 2 (`…T131429Z`, archived) |
| --- | --- | --- |
| status | `MODEL_API_PASS` | `MODEL_API_PASS` |
| decisions | 20 / 20 pass | 20 / 20 pass |
| measured tokens | 28 688 | 28 688 |
| p50 latency | 1 953 ms | 1 929 ms |
| p95 latency | 2 335 ms | 2 314 ms |
| recorded-action agreement | 17 / 20 | 17 / 20 |

Run 2 is the archived one because it was executed against the instance whose
log is preserved next to it. Agreement is descriptive; it is not a success rate
and not a closed-loop measurement (`closed_loop_success_measured: false`).

## Judge criteria, as the task defined them

| criterion | result |
| --- | --- |
| real `source=jev`, `fallback=false` on all 20 | met — every response carries the model's own payload, none is an FSM fallback |
| positive measured tokens | met — 28 688 total, per-row values in `rows[].response_json` |
| legal actions, finite and normalised probabilities | met — every `next_action.probabilities` sums to 1.0 within 1e-6 |
| canonical state references match | met — row state hashes match the prescribed source steps; input manifest and source files are independently hashed |
| local weight is the documented Q8 | met — `8754b06f…b05593d9`, matches `docs/MODEL_IDENTITY.md` |

## GPU evidence: three independent facts, one missing line

| fact | value |
| --- | --- |
| process | PID 21464, `F:\flexcell-models\llama-b11389-vulkan\llama-server.exe` |
| modules loaded | `ggml-vulkan.dll` **and** `vulkan-1.dll` (plus `ggml-cpu-haswell.dll`) |
| adapter | AMD Radeon RX 6800, driver 32.0.21043.19003 |
| dedicated memory in use | **9 921 011 712 B = 9.24 GiB** |
| adapter name / command line | `-ngl 99 -ub 32768 -c 16384`, same Q8 path, port 11435 |

The snapshot lists Vulkan modules and 9.24 GiB of adapter-wide memory usage.
This supports GPU use, but does not attribute memory to this process or prove
the number of resident layers.

**The captured instance log has no per-layer offload line.** It contains 73
lines and zero occurrences of `offload`. This absence cannot establish what
the build can emit or whether another stream was captured. The separate
[home regression stderr](https://github.com/Yenefa/flexcell/blob/36486780f5bf46add81124aa334400c71be4ae72/setup/acceptance/home_gpu_abort_20261024/server_stderr.log) does
contain `offloaded 33/33 layers to GPU`; that proves a fact about its own
instance, not this receipt's instance. Preserve both archives and keep this
receipt's GPU layer residency UNKNOWN.

Therefore:

```
model interface        PASS
GPU layer residency    UNKNOWN  (no per-layer line in this captured log)
served weight identity PARTIAL  (server reports F:\flexcell-models\Clef-Flash-Q8_0.gguf;
                                that path's sha is the documented Q8 sha;
                                the server does not report a sha of its own)
routing qualification  NOT_TESTED
```

`-ngl 99` is a request, not proof. The task said not to let it stand in for
evidence, and it does not stand in for evidence here.

## Two honest gaps

1. **`calibration_sha256` is `null`.** The production calibration file was not
   located under the paths this checkout knows about, and the task forbids
   generating or deploying a new one. So calibration identity is `UNKNOWN`, not
   "unchanged".
2. **Host name deliberately omitted** from `gpu_evidence.json`. It is not needed
   to reproduce anything and does not belong in a committed artifact.

## Verifying this archive

```
verify_clef_receipt.py           39 checks  CONFIRMED
selftest_verify_clef_receipt.py  40/40      cases behave as declared
```

Both are pure stdlib, need no ROS and no network. The verifier pins the original
manifest and hashes its three source episodes, selecting the same first 20
non-bootstrap inputs in order. Every row must match its prescribed episode,
step, state SHA and original decision. Source/fallback, identities, finite
probabilities and positive usage are recomputed per row; token totals, call
counts, action agreements and latency summaries are reconciled with the rows.
The log is checked separately. GPU execution and served-weight identity remain
incomplete; client and archive checks do not inspect the current server.

### Checker hardening (2026-10-25)

At `cf4acd3`, four independent counterexamples passed despite keeping the
prewritten PASS: a fallback decision, NaN probability, one zero-token row
hidden by a positive total, and a forged state SHA. All four now exit 1.
The 40 self-test cases include an unchanged positive control and 39 negative
cases, covering malformed probabilities, input duplication/reordering, usage,
identity and summary tampering. The original receipt still passes all 39
checks, totaling 28,688 tokens. No receipt, log, GPU snapshot, source episode or
manifest was rewritten; no GPU inference or robot task was rerun for this repair.

The self-test caught a real defect while being written: the first version of the
verifier de-duplicated episode shas by path, so forging the sha on one row was
masked by a correct copy of the same episode on a later row. Case K failed, the
verifier was fixed to compare per `(episode, sha)` pair, and it now rejects that
tamper.

## What this does not change

Hybrid routing eligibility stays frozen, `n≥50` stays unevaluated, no paid slow
model was called, no Gazebo run and no robot command happened
(`robot_commands_sent: 0`). A passing model interface is not a closed-loop
success and not a physical acceptance result.
