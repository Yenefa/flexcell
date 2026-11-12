# Independent review — T13-recover-clearance-margin

**Reviewer** gate-auditor · **Date** 2026-11-12 · **Verdict: ACCEPT** (with four recorded caveats)
**record_sha256** 688f0862066d582e180268c48fd58fe44adf752bdf06a1b3a91c6a7dfb3daf9f
**Constraints** read-only, no sim, no model calls. records.jsonl untouched; the only write outside
this directory is the ledger line that makes the record retrievable.

---

## 0. Verdict table

| # | check | result |
| --- | --- | --- |
| 1 | lesson faithful to what I actually found? | **YES — no drift, verified number by number** |
| 2 | numbers re-derived independently? | **YES — all seven reproduce** |
| 3 | failure_class control right? | **YES — it is the class I recommended** |
| 4a | 20 mm exclusion forced? | **YES — the guard blocks the concept, not just the word** |
| 4b | 1.4 mm exclusion forced? | **YES — no field exists; I re-ran the derivation** |
| 4c | error_code exclusion forced? | **YES — 61 and 60 both ACCEPT here, 99 rejects** |
| 5 | author's warning (gate does not check truth) | **CONFIRMED — a planning-strategy lesson is ACCEPTed** |

**ACCEPT is correct. Read caveats (i)-(iv) in section 5 before treating this as a template.**

---

## 1. Q1 — is the lesson faithful to my finding? Yes, word by word

I wrote, in setup/acceptance/evobot_lead_verified_review_20261112/REVIEW2.md:

> *'planned separation 56.0 mm ... clearance_m 50.0 mm ... planned margin +6.0 mm ... placement error
> 9.65 mm ... position_tolerance_m 20.0 mm ... actual separation 48.6 mm - 1.4 mm BELOW clearance'*

The record says:

> *'Two destinations 56 mm apart left only 6 mm over the 50 mm clearance; one object settled
> 9.65 mm off its commanded point, inside the 20 mm accepted limit, leaving the next destination
> 1.4 mm short and refused as occupied.'*

Mapping: 56 yes · 6 yes · 50 yes · 9.65 yes · 20 yes · 1.4 yes · 'refused as occupied' yes
(my words: *'destination judged occupied'*). **Every quantity and every causal claim is mine.**
Nothing was added that I did not find; nothing I found was strengthened.

The one thing dropped is my sharpest inference - that the accepted tolerance (20 mm) is **3.3x** the
margin (6 mm), so an error well inside specification is *guaranteed* to break the next stage. The
lesson states the facts that imply it without stating the ratio. That is an omission, not drift.

---

## 2. Q2 — every number re-derived from the cited artifacts, by me

Sources: plan.json (stages, clearance_m, position_tolerance_m), place.jsonl (box_after),
task_fsm.jsonl (final_position_error_m).

| quantity | my derivation | author's claim | agree |
| --- | --- | --- | --- |
| commanded separation | dist([0.092,-0.15],[0.148,-0.15]) = **56.000 mm** | 56.000 mm | yes |
| clearance | plan.clearance_m = **50.0 mm** | 50.0 mm | yes |
| nominal margin | 56.000 - 50.000 = **+6.000 mm** | +6.000 mm | yes |
| placement error | dist(commanded_xy, box_after_xy) = **9.6519 mm** | 9.652 mm | yes |
| post-error separation | dist(box_after_xy, b_destination) = **48.599 mm** | 48.599 mm | yes |
| shortfall | 48.599 - 50.000 = **-1.401 mm** | -1.401 mm | yes |
| accepted limit | plan.position_tolerance_m = **20.0 mm** | 20.0 mm | yes |

### One precision worth recording, because it explains the two error fields

place.jsonl carries **two** error figures that differ in the third decimal, and they are not the same
quantity:

   2D (xy) distance from commanded  = 9.65192 mm   == task_fsm.final_position_error_m  (9.651925)
   3D distance (incl. z)            = 9.65802 mm   == place.jsonl.place_error_m        (9.658023)

The lesson's **9.65 mm** is the 2D figure - correct, and the figure I used. The evidence dict cites
both, which is honest but slightly redundant: they are one displacement measured two ways, so the
record's three evidence facts are effectively **two** independent facts plus the clearance constant.

---

## 3. Q3 — failure_class control is right

In round 15 I wrote that planning was wrong because **the plan was correct**, and recommended
control (*'the proximate cause is a 9.65 mm placement error against a 6 mm margin'*), with tooling as
defensible. The record uses control. That is my recommendation, and the artifacts support it:
place.jsonl for target_box_a shows outcome=0, error_code=0, released=true - the first placement
**succeeded**; the failure is that its residual error consumed a geometric budget. Nothing the
planner chose was wrong. **Agreed, no change requested.**

---

## 4. Q4 — the three exclusions: I tested each. All honest, none gutting.

I re-ran each refusal against the live store and checker rather than accepting the note.

### (a) The 20 mm limit cannot be an evidence fact - CONFIRMED, concept-level block

| evidence submitted | result |
| --- | --- |
| position_tolerance_m: 0.02 | **REJECT** - store scope: touches a protected topic: tolerance |
| tolerance_m: 0.02 | **REJECT** - same |
| accepted_error_limit_m: 0.02 | **REJECT** - provenance: not found in any artifact |

So it is not a word game the author could dodge by renaming: the value has no field under any other
name, and the guard blocks every name that would carry the concept. **The exclusion is forced.**

**But note where the concept went.** The lesson says *'inside the 20 mm accepted limit'* - the same
fact, in prose, where _check_scope cannot see it. The guard blocks the concept in the evidence dict
and permits the identical concept in the lesson string it is also supposed to govern. That is a real
hole, and it is the same hole I flagged in round 15 when a downstream lesson passed by saying
*'landing spots'* instead of *'placement'*. **This record does not create the hole and does not hide
it - the author documented it - but it does use it.**

I judge that acceptable here for one specific reason: the 20 mm is position_tolerance_m, an
**executor** field the planner itself emits into plan.json, not an evaluator threshold. The
evaluator's thresholds (30/150 mm, 20 mm vertical, cos 0.9, 60 mm radius) appear nowhere in this
record. **No grading knowledge is smuggled.** Had the same paraphrase carried an evaluator threshold,
I would reject.

### (b) The 1.4 mm margin cannot be a fact - CONFIRMED, and it does not gut the record

| derived value submitted | result |
| --- | --- |
| margin_m: 0.0014 | **REJECT** - provenance |
| shortfall_m: -0.001401189 | **REJECT** - provenance |
| separation_mm: 56.0 | **REJECT** - provenance |

Correct: those are computed, not recorded, and inventing a field to hold a computed number is exactly
the failure mode the store exists to prevent. **It does not gut the record** because the derivation is
fully reproducible from the three cited files - I reproduced all seven quantities above from
plan.json, place.jsonl and task_fsm.jsonl without consulting the lesson.

### (c) error_code dropped because 61 and 60 are both present - CONFIRMED, exactly as described

| claim | result |
| --- | --- |
| error_code: 61 (the original failure) | **ACCEPT** |
| error_code: 60 (the retry's failure) | **ACCEPT** |
| error_code: 99 (invented) | **REJECT** |

This is the checker proving it can only answer *'some file in this run says 61'*, not *'this run
failed with 61'*. The run genuinely contains both - failure_evidence.json has 61, the retry composite
log has 60 - so an error_code in the evidence dict would be **unfalsifiable within this run**.
Dropping it was the honest call. The alternative was a field a tamper test cannot distinguish, which
is the exact defect I spent round 14 on.

---

## 5. What I still do not like - recorded so ACCEPT is not read as endorsement of everything

**(i) The record is not really a planner-level lesson, and it passes that gate by a lexical accident.**

The store docstring: *'a record may describe a PLANNER-level lesson only.'* This lesson is a
control-budget fact. It passes audit_actionability because the string *'one object settled'* contains
'object' - not because a planner can act on it. The planner emits {object, zone, why}; it cannot widen
the 56 mm spread, cannot reduce a 9.65 mm actuator error, and cannot change a 50 mm clearance.
**The classifier and I disagree about this lesson, and the classifier is wrong.**

**(ii) That has a concrete cost in the retrieval path.** baseline_c.retrieve() scores a lesson on
_REQUIRED_FIELDS = ('unmoved','object','zone','declare') with a universal +1, so a lesson containing
'object' scores at least 1 **for every instruction** and consumes one of limit = 3 slots on every
plan. A fact the planner cannot act on will therefore displace a lesson it could act on. Not this
record's fault - but the consequence of ACCEPTing it, and it should be fixed in baseline_c.py rather
than in the record.

**(iii) The evidence dict omits the load-bearing number.** The lesson's punchline is the -1.401 mm,
which appears in no evidence field - by design, and correctly - but it means a reader of
records.jsonl alone cannot check the claim; they must follow evidence_files and compute. That is an
acceptable price for not fabricating fields, and I paid it and got the same answer.

**(iv) task_id is a descriptive label, not an identifier in the artifacts.**
T13-recover-clearance-margin appears nowhere in the run; the run is HO-90899d657e68, template
T13_geometric_conditional. Much weaker than the round-14 defect (which pointed at a whole batch
directory) because source_run pins one exact run, but the label should not be mistaken for a
traceable id.

---

## 6. The author's warning: CONFIRMED, and it is the most important sentence in their note

I re-ran the exact mutation. Take this record's evidence and replace the lesson with a planning
strategy - *'Choose a free destination for each object before sending the second one, and order the
moves so a later stage is not blocked by an earlier one.'*

    planning-strategy lesson -> ACCEPT
    classifier REAL lesson   -> ('PLANNER_ACTIONABLE', 'maps onto a field the planner controls')
    classifier PLANNING      -> ('PLANNER_ACTIONABLE', 'maps onto a field the planner controls')

**Identical verdict, identical label.** That planning-strategy lesson is, in substance, the false
lesson I rejected twice in round 15. The gate cannot tell the difference because it only reads
vocabulary. ACCEPT from the checker is necessary and nowhere near sufficient - the only reason this
particular lesson is true is that **it is my finding and I re-derived it**, not that a machine agreed.

The author was right to write that down instead of letting the green check speak for itself. It is the
difference between this record and the six before it.

---

## 7. Verdict

**ACCEPT.**

Reason: every factual claim in the lesson is true, is mine, and reproduces from the three cited
artifacts; the evidence values are genuine typed fields; the class is the one I recommended; and all
three exclusions are forced by the store's own rules, verified by me, and documented rather than
hidden. It is the first record in this store to survive an independent review on its content.

The acceptance is of **this record**, not of the pipeline that produced it. Caveats (i)-(iii) should
be fixed in audit_actionability / baseline_c.retrieve, not by weakening the record. Caveat (iv) -
the tolerance paraphrase - should be closed by giving the scope guard a concept test, or by deciding
explicitly that executor tolerances are not protected. Right now the guard forbids the word and
permits the fact.

Ledger entry appended, so this record becomes retrievable.
