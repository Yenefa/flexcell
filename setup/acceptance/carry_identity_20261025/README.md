# carry-identity-20261025 — making a stop record name what it stopped

**Scope: instrumentation only.** No control-flow change, no new branch, no new
default. The carry backend stays frozen; what changes is what it writes down.

## The gap being closed

From [#48](../grasp_sequence_20261025/README.md), the one measurable that could
attribute a failing PICK to the carry servo was unrecoverable:

```
stop events 1432, of which 0 name a session, 0 name an object
start events 449  ->  983 stops are re-engages or no-ops
```

`_on_stop` already had the identity in hand — line 247 added `self._session` to
`_retired_sessions` — and then dropped it: `_object_id` was cleared on line 248
and the record on line 252 was `{'event': 'stop', 'backend': ...}`. Three
callers were also indistinguishable: replacing a session, honouring a release
request, and a servo thread that died all produced the same bytes.

## What is recorded now

| event | added fields | why |
| --- | --- | --- |
| `stop` | `session`, `object`, `engaged`, `cause` | which PICK this release belongs to |
| `release_unconfirmed` | `session`, `object`, `cause` | which PICK failed to release |
| `worker_ended` | `session` | which PICK's servant died |
| `set_pose_fail` | `session` | keeps a pin failure with its PICK |
| `servo_abort` (new) | `object`, `session`, `consecutive` | the servo self-stop used to be invisible |

`cause` is one of `release`, `replace`, `worker_ended`, `shutdown`, `topic`,
`unspecified`. The stop topic gets its own entry point (`_on_stop_topic`) so a
remote stop is distinguishable from a release the server issues to itself.

`start` already carried `session` (317 of 449 rows; the rest predate the field),
so after this change every record that matters can be joined on `session`.

## The proof that it is log-only

```bash
python3 setup/acceptance/carry_identity_20261025/prove_no_control_flow_change.py
```

It compiles `carry_server_before.txt` — the pre-change file, vendored here with
its sha256 pinned — and the working tree file, then runs both `_on_stop`
implementations over a 96-state matrix (thread absent/alive/dead × backend ×
physics-release confirmed/not × session present/absent × object present/absent ×
offset set/unset) and requires agreement on everything the server does:

    return value, _object_id, _offset, _session, _retired_sessions,
    _publish_state call count, _guard_release call count

Measured on this branch:

```
reference : carry_server_before.txt
sha256    : 15f9f1b9...a834d55db MATCHES the pinned value
state matrix: 96 combinations
compared 96 states
behavioural differences: 0
log differences other than the declared added keys: 0

EQUIVALENT: the only change is what the record contains
```

The reference digest is pinned in the script, so a silent edit to the vendored
file is refused rather than compared against.

**This is deliberately not a CI gate.** It compares live source against a frozen
reference, so any later legitimate change to `_on_stop` would turn it red and
require re-pinning. Unit coverage for the new behaviour does run in CI, through
`test/test_carry_stop_identity.py` in the colcon test ladder.

## Unit coverage

`test/test_carry_stop_identity.py`, 10 cases:

- the record names the session and object it stopped, and `engaged`
- each of the five causes is recorded as itself
- the stop topic is recorded as `topic`
- an idle stop says it released nothing
- identity is captured **before** the state is cleared (a record that read the
  attributes back would be empty, and this would catch it)
- a session stays retired after a recorded stop
- **a worker that will not join still blocks the stop** — record keeping must
  not soften the safety outcome
- an unconfirmed physics release names itself too
- `worker_ended` records the session it was serving

One pre-existing double in `test_carry_release.py` bound `_on_stop` through a
one-argument lambda and had to accept the new keyword; the production call sites
go through the bound method, which always could.

Measured locally (WSL, ROS Jazzy, from `/tmp` so pytest does not scan a 9p
mount):

```
18 passed in 0.48s        # the two carry modules
432 passed                # whole test/test_*.py ladder
```

## What this does and does not buy

It buys: the next window can finally say *which* PICK a pin failure belonged to,
and can separate "released by a PICK" from "replaced by the next engage" from
"servo gave up". That is the measurement #32 is missing.

It does not buy: any explanation of the 20.4 % failure rate. Nothing in this
change touches grasping, `box_follow_min_m`, the 2.0 s settle, or the teleport
pin path. A run after this change is comparable to a run before it, because the
mechanism is identical — the proof above is what licenses that comparability
claim, and it would stop licensing it the moment the proof fails.
