# Replay drift probe (2026-10-24)

## Why this exists

`contracts/episode.py:replay_episode` decides whether a recorded decision
"reproduces" by comparing the whole decision dict with `==`. That dict includes
`explanation`, a free-text field the policy is free to reword. So a message
change silently marks historical evidence dirty even when the decision itself is
byte-for-byte identical.

That is not hypothetical. `5462124` ("keep the typed skill code in the PLACE
abort detail", 2026-10-23 22:37) changed exactly one string:

```
before:  place failed (carried box is not retried)
after:   place failed (ERR_MOTION_FAILED, carried box is not retried)
```

Measured 2026-10-24 against the archives in this repository, that single edit
turns the archived S4 episode from `REPLAY clean` into `REPLAY-DIRTY` while
`action`, `target`, `reason_code` and `confidence` all still match exactly. The
frozen `95_metrics_report.md` says `REPORT: PASS (2 episodes, 0 replay-dirty)`;
regenerating it today yields `REPORT: FAIL (2 episodes, 1 replay-dirty)`.

## What was measured

| archive | episodes | offline-replayable | decision steps | diverging | semantic | textual |
| --- | --- | --- | --- | --- | --- | --- |
| E-021 native recovery | 60 | 20 (`policy.name == fsm`) | 163 | 0 | 0 | 0 |
| M3 online v2 S3/S4 | 2 | 2 | 14 | 1 | **0** | 1 (`explanation`) |

The 40 non-FSM E-021 records are hybrid runs: their history is a sequence of
model decisions that the frozen FSM cannot continue, so they are counted as
skipped rather than replayed. This is the same reason `model_replay` stays
`NOT_RUN` — see `docs/EXPERIMENTS.md` E-021.

**Conclusion: no decision semantics drifted.** E-021's "163 decisions replay
exactly" claim still holds on current `main`; S4's `REPORT: PASS` does not, but
only because a message was reworded.

## The invariant this probe enforces

- **Hard gate:** `action`, `target`, `reason_code`, `confidence` must match
  exactly. Exit `1` if any of them diverges — the archive no longer reproduces
  and whatever claim is attached to it must be withdrawn.
- **Reported, not gated:** every other field, `explanation` in particular. A
  reworded message is recorded here so the drift is visible, but it does not
  void an otherwise faithful replay.

## What this corrects

`setup/acceptance/issue22_readjudication_20261024/README.md` claim C3a cites the
archived batch row's `replay_ok: True`, which was true on 2026-09-30. It did not
say that the same episode no longer replays cleanly on current `main`. That
record now carries a correction pointing here.

## What is deliberately not changed here

`replay_episode` still compares the whole dict. Narrowing it to the semantic
fields is a change to the evidence standard itself — it would restate what
"reproducible" means for E-021, E-011, E-010 and every report regenerated from
those archives — so it needs an explicit decision rather than a quiet patch. This
probe measures the current behaviour without altering it.

## Running it

```bash
python3 setup/acceptance/replay_drift_20261024/probe_replay_drift.py
```

Needs the `flexcell_skills` package importable (`src/flexcell/flexcell_skills` on
`PYTHONPATH`, or `source install/setup.bash`). It reads only committed bytes: no
ROS, no Gazebo, no network, no episode store. Exit `0` = semantic replay exact,
`1` = semantic drift present, `2` = the package or an archive is missing.
