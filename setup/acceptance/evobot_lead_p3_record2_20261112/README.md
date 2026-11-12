# P3 record #2 — PLANNING class: **cannot be built honestly from this archive**

**Date** 2026-11-12 · **Lane** exec-mystery · request: author ONE review-grade **planning**-class record
**Answer: I could not build one, and I did not manufacture one.** The archive contains no failure
whose cause is a wrong planner choice. Reasoning and measurements below.

---

## 1. Why this is the answer and not a failure to search

Four independent checks, all read from machine-readable artifacts, all agree:

| # | check | scope | planning failures found |
| --- | --- | --- | --- |
| 1 | `evobot_failure_layer_20261111` (existing, independent) | 64 runs, 4 batches | **0** |
| 2 | my zone/leg audit vs task specs (`benchmark/tasks` train+val+t08 = 120 specs) | 41 plans | **0** |
| 3 | my zone/leg audit vs requirements reconstructed from each run's own `verdict.json` | 211 runs (incl. held-out `HO-*`) | **0** genuine (2 are the induced probe) |
| 4 | zone-identity audit of every distinct plan destination | 12 distinct destinations, all archived plans | **0** wrong zone |

---

## 2. What "a wrong planner choice" would look like, and why none exists

The planner's interface is `{moves:[{object, zone, why}], unmoved, confidence, uncertainty}`.
A genuine planning failure therefore has exactly four possible shapes, and I tested each:

| shape | test | result |
| --- | --- | --- |
| wrong final zone for an object | plan's last `place_pose` per object → nearest zone, vs required zone from the spec **or** from that run's own `verdict.json` `placement:<obj>` clause | **0** wrong (2 hits, both in the deliberately induced probe — §3) |
| omits a required intermediate leg (relay) | required `visit` legs vs the plan's zone sequence per object | **0** missing over 211 runs |
| moves an object the spec protects | `unmoved` requirement vs objects present in `moves` | **0** |
| declares a needed object `unmoved` / omits it | required placement objects vs staged objects | **0** |

Example of a plan I checked carefully because it *looked* wrong: `evobot_baseline_b_v2_20261111/plans/T05-train-seed1000` emits **one** move `target_box_b → zone_2`. Naive reading suggests it skipped the relay. It did not — the move carries `"via": ["zone_1"]` and `"stages": 2`. Reading `via` correctly removes the only apparent planning error in the planner comparison set. **This is the trap that would have produced a false record.**

---

## 3. The only wrong-zone plan in the entire archive is deliberately induced

`setup/acceptance/evobot_wrongplan_probe_20261111/run_foreign_plan` — both objects routed to `zone_1`
where `zone_2` was required. Its own README states the plan was **borrowed from a different task**
(`HO-128c6a231c34`, which does want `zone_1`) and run on `HO-0dcde4dc0f5a`. That is a probe
construct, not a planner choice. No record may be built on it.

---

## 4. The only genuine planner-side failures in the archive, and why they are not records

`evobot_failure_layer_20261111` classifies `"no JSON in reply"` as PLANNER. That classification is
defensible for attribution, but it cannot carry a planning record. The archive holds exactly **one
such event, archived twice** (byte-identical `agent_reply.json`, sha256 prefix `467862582d99fd8a`):

```
setup/acceptance/evobot_baseline_b_v2_20261111/plans/T06-train-seed1001/agent_reply.json
setup/acceptance/evobot_baseline_b_v2_20261111/failed_run_preserved/agent_reply.json
  "agent_plan": null
  "problems": ["no JSON object in reply"]
  "raw_reply": ""                       <- ZERO characters returned
  usage: 2625 tokens, 11.155 s
  result.json: "planned": false, "stage": "planning"
```

Rate: **1 failed-to-plan out of 18 plan attempts** in that archive.

Why I refuse to make this a planning record:

1. **The planner did not choose wrongly — it produced nothing.** `raw_reply` is empty while 2625
   tokens were billed. That is a generation/transport failure (`model` or `runtime`), not a decision.
   Labeling it `planning` would be the same species of error as round 15: a label that does not
   describe the mechanism.
2. **There is no plan to learn from.** The lesson could only be "emit a JSON object" — a wire-format
   instruction, not a fact about `moves`/`zone`/`order`. The Lead's requirement 2 asks the lesson to
   map onto one of `{moves, unmoved, confidence, uncertainty}`; this maps onto the reply envelope,
   not onto those fields' content.
3. **n=1, and the artifact is empty.** No measured quantity distinguishes it.

---

## 5. The one archive case *labelled* `planning` was overturned by review

`setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/` — `recovery_decision.json` says
`"failure_class": "planning"`, `"measured_reason": "plan declared an occupied destination"` (error 61).
Round-14 independent review found that label **false**: the plan was correct, the two destinations
were 56 mm apart, and a 9.65 mm actuator error inside the accepted 20 mm limit broke the next stage
by 1.4 mm. That case is now record #6 in the store, correctly classed **control**.

So the archive's single most planning-shaped label is a **known mislabel**. Re-deriving a planning
record from it would reproduce the exact failure the Lead is guarding against.

---

## 6. NEGATIVE CONTROL — proof the gate cannot stop me manufacturing one

I built the plausible false record and ran it. File (clearly named, **do not append**):

```
setup/acceptance/evobot_lead_p3_record2_20261112/NEGATIVE_CONTROL_false_planning_lesson.json
```

It takes the *same* run as §5, classes it `planning`, and asserts the round-14 **false** lesson —
"send each object to a distinct destination and keep the second move clear of the first one; when two
moves are close together the later one is refused as occupied". That lesson is false: the plan was
correct and no ordering conflict existed.

Dry run printed:

```
ACCEPT NEGATIVE-CONTROL-do-not-append provenance + actionability ok

accepted: 1   rejected: 0   (dry_run=True)
nothing written - dry run
```

**So ACCEPT is necessary and not sufficient — confirmed for the planning class specifically.** And the
consequence is worse than for the control record: `experiments/baselines/baseline_c.py:126` gates
retrieval on `failure_class in {planning, state}` plus an independent review ACCEPT. A manufactured
planning record would therefore become **the first retrievable lesson in the store's history**, and it
would be false — a false lesson entering plans, not merely a useless one in the store. That is exactly
why refusing is the right answer here.

---

## 7. What this means for P4 (C vs D)

C's channel is empty for a **structural** reason, not a plumbing reason: **there is no planning error
in the archive for it to retrieve.** This independently reproduces
`evobot_failure_layer_20261111`'s conclusion ("规划层没有可修的错", 0/64) and extends it — that round
counted first-attempt failures; this one audits the *plans themselves* across 211 runs and finds them
correct, not merely unblamed.

Consequence for the Lead's question: on this archive, C-vs-D cannot be posed as "does a planning
lesson improve plans", because no true planning lesson exists to inject. What C *can* retrieve today
is only record #6 (control), which `b0af91ee` correctly blocks from steering a plan — so C's
retrievable set is, correctly, **empty**.

If the intent is to make C functional, the prerequisite is **evidence of a planning error**, not a
record. That means generating instances where the planner's own choice can be wrong and measuring it —
candidates: conditional/ordering templates where the correct zone is not stated directly
(`T13_geometric_conditional`, `T05_relay`, `T06_revisit`), scored on **plan correctness before
execution**, so an actuator error cannot masquerade as a planning error. Until such a measurement
exists, any planning-class record in this store is either mislabeled or invented.

---

## 8. Scope compliance

- No positive seed written; **nothing appended** to `records.jsonl` (still 7 records).
- `store.py`, `verify_provenance.py`, `seed_from_evidence.py`, `audit_actionability.py` untouched.
- No simulator, no model calls, no commit.
- Wrote only inside `setup/acceptance/evobot_lead_p3_record2_20261112/`.
- The negative-control file is named to prevent accidental append and is documented here as false.
