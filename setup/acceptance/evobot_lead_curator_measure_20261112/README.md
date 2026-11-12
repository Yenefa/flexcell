# Can any Development Skill effect be measured? — a controlled-comparison feasibility audit

**Date** 2026-11-12 · **Role** Skill Curator (permanent) · **Lane** Curator
**Repo** `project-033-flexcell/wt-comp`, branch `autonomous/flexcell-remediation`
**HEAD** `7f6de02a` at time of writing. Measurements began at `538f0460`; the key adoption result was re-run at `7f6de02a` and is unchanged (see §8).
**Inventory under audit** `development_skills/` — 4 skills, all `PROPOSED`
**Simulator** NOT started. **Model calls** NONE. **Pinned files** untouched (`git diff` on all 9 pinned files: empty).

---

## 0. The answer, first

> **No controlled comparison exists, and none can be constructed from this repository offline.**

The reason is not a shortage of data. It is that **the treatment was never administered.**
Across the entire history — **295 branches, 2,104 distinct Python files, 206 distinct shell drivers, 819 commits** —
**no agent ever invoked a single Development Skill. Not once.**

The adoption count is **0**. There is therefore no "with-skill" arm, and a comparison needs two arms.
This is a structural null, not a small sample.

I did **not** manufacture a proxy. What follows separates what I measured, what it means,
and precisely what would have to exist for a real A/B to be run.

---

## 1. What I looked for, and what I found

The brief names two shapes: (a) a task done with a skill versus without it, or
(b) a pair of comparable episodes that differ only in skill availability. I tested for both.

### 1.1 Shape A — a task done WITH a skill

Measured over the whole repository, not one round:

| Probe | Result | Method |
| --- | --- | --- |
| Commits since the skills were created (`5866de4b`, 11-12 02:10) | **105** | `git rev-list --count` |
| Commits that modified `development_skills/` | **3** — creation, round-1 revisit, and the round-2 record | `git log -- development_skills/` |
| Files authored after the skills existed | **100** (75 `.py`, 25 `.sh`) | `git log --diff-filter=A` |
| **Of those 100, external files (excluding `development_skills/` itself)** | **81** | — |
| **Of those 81, files that invoke a skill entrypoint** | **0** | full-text scan for `development_skills/`, `preflight.py`, `safe_pattern.py`, `call_path_check.py`, `effect_check.py` |
| Branches containing a file that invokes a skill | **0 of 295** | `git grep -l ... <branch> -- ':!development_skills'` per branch |
| Stashes | 0 | `git stash list` |

(A naive scan over all 100 reports 5 hits. All 5 are self-references **inside** `development_skills/`:
the skill scripts naming themselves, plus four of my own round-2 reproducers. Excluding that directory
leaves 81 files and **0** invocations. Both numbers are stated so the arithmetic can be checked.)

### 1.2 Why adoption is structurally 0: there is no load path

This is the finding that explains all the others.

| Load-path probe | Result |
| --- | --- |
| `CLAUDE.md` / `AGENTS.md` / `.cursorrules` / `GEMINI.md` / `.claude/` in repo root | **all absent** |
| Repo `README.md` mentions `development_skills` | **0** |
| Any code in the repo that reads `development_skills/` | **0 files** |
| Docs mentioning `development_skills/` | 2 files, **3 + 1 mentions**, all *status reports*, none an instruction to load or use a skill |

The three mentions in `docs/HANDOFF_20261112.md` are: a table row listing the skills as a deliverable,
and a warning *not to* count their 42 tests as an achievement. `docs/FACT_STATE_20261112.md:342`
records "Four skills registered — CONFIRMED" with a path. **None of these tells an agent to run anything.**

**Conclusion:** the skills were never on any agent's load path. An agent working in this repo had no
reason to open the directory, and the measurements show none did. This is not "the agents ignored a
good thing" — it is that nothing connected the artifact to the workflow.

### 1.3 Shape B — a pair of comparable episodes differing only in skill availability

Requires two arms that differ in skill availability **and nothing else**. The repo's A/B culture is real
but has never been pointed at a development practice:

| A/B experiments found (`setup/acceptance`) | 12 |
| --- | --- |
| Of those, comparing two **robot** configurations | **12** (`fsm_vs_hybrid`, `fsm_vs_mtc`, `paired_n53`, `goal_check_ab`, …) |
| Of those, comparing two **development practices** | **0** |

There is no episode of the form "the same dev task was attempted with the skill loaded and without it".

**Verdict on Shape B: absent, and not recoverable by reading.** No amount of archival re-analysis can
create an arm that was never run.

---

## 2. What I could still measure — and its correct status

Two quantities are measurable offline. **Neither is an effect measurement.** I state their status
explicitly so they cannot be quoted as if they were.

### 2.1 Detector coverage: would the skills have fired on the bugs that actually occurred?

This is a *maximum possible* effect, not a measured effect. A checker that cannot detect a bug cannot
have prevented it; a checker that can detect it still prevents nothing unless somebody runs it.

Measured at HEAD `538f0460` (numbers reproduce round 2's at `a6fe30af`; the evidence layer is unchanged):

| Skill | Coverage of its own cited cases | Provenance |
| --- | --- | --- |
| `ros2-interface-preflight` | **2 of 6** — cases 1,2,3 missed (never inspects `PushObject.Result` or the `sample_gz_pose` signature), case 5 crashes, cases 4 and 6 caught | round-2 `revisit_r2/coverage_of_own_cases.sh` |
| `evidence-level-audit` | **2/2 on its own case A**, but **0/1 on the bug that actually recurred** — round 2's failure was a *call with a missing argument*, which a string-presence check reports as OK | round-2 `revisit_r2/case_a_check.sh` |
| `effect-verification` | **0/2 on the two real errors** it was meant to catch | round-2 `revisit_r2/coverage_of_own_cases.sh` |
| `simulation-process-lifecycle` | Never invoked; see §2.2 | — |

**Even with 100% adoption, the ceiling implied by these numbers is low.** No effect size can exceed what
the detectors can detect.

### 2.2 Practice drift: did behaviour change even without invocation?

A skill can in principle change behaviour through its *lesson* rather than its script. I tested this on
the clearest countable marker — the `pkill -f` bracket trick vs a bare pattern:

| Drivers containing `pkill` | n | uses bracket trick | bare only |
| --- | --- | --- | --- |
| **BEFORE** the skills existed | 20 | 5 | 11 |
| **AFTER** the skills existed | 12 | 3 | 6 |

**This is not an effect, and I will not report it as one.** Reason, stated plainly: the bracket trick
**predates the skill** — `evobot_t08_evidence_run.sh` (00:56, before the skills at 02:10) already uses
`[g]z sim`. So bracket use after 02:10 is not attributable to the skill. And the after-skill drivers
that still use a bare pattern are the majority:

```
02:21  bare=4  evobot_push_recover_20261112/scripts/evobot_t08_recovery_run.sh
06:17  bare=8  evobot_lead_t08_centre_height_20261112/run_centre_height.sh
06:24  bare=8  evobot_lead_t08_fresh_unseen_20261112/run_fresh_batch.sh
06:30  bare=8  evobot_lead_t08_overdrive_20261112/run_overdrive_batch.sh
06:35  bare=8  evobot_lead_t08_height_offset_20261112/run_height_offset_batch.sh
07:35  bare=2  evobot_lead_paired_n53_20261112/run_paired.sh
```

If anything this is mild evidence *against* propagation, which is exactly what a 0-adoption finding predicts.

### 2.3 One genuine improvement in provenance (not an effect)

Round 2 measured **0** archived `interface_check.log` files. Now there are **20**, all committed:

| `interface_check.log` | count |
| --- | --- |
| `INTERFACE_CHECK_OK` | **20** |
| `INTERFACE_CHECK_FAILED` | **0** |

Scanning all 51 acceptance dirs created after the gate existed for `AttributeError`/`has no attribute`
in any log: **0 hits**.

**Why this is still not evidence of skill effect:** the gate that produced these logs is
`benchmark/tools/check_ros_interfaces.py`, authored **01:46**, *before* the skills (**02:10**). It is a
pre-existing tool, not the skill. The skill merely described it afterwards. Round 2's registry entry
records this exact confound; it is unchanged. What the 20 logs *do* show is that the **gate is now
observable** — 20 runs, 20 passes, 0 failures — so a future audit can compute a real rate instead of
having no data at all.

---

## 3. What is missing to make a controlled comparison possible

Four things, in dependency order. All four are absences, not difficulties.

| # | Missing | Why it blocks measurement | Cheap workaround |
| --- | --- | --- | --- |
| 1 | **A load path** | Nothing puts a skill in front of the agent. With no load path, adoption is 0 by construction and every arm is "without". | Add one line to an agent-read instruction file pointing at `development_skills/registry.json`. **~5 minutes.** |
| 2 | **A recurring task class** | An A/B needs the same task repeatedly. The closest class — "write a driver that launches the sim and grades with `evaluate.py`" — has **9 instances ever, 4 after the skills existed**. | Define the class explicitly and generate instances. |
| 3 | **A per-episode outcome variable** | Nothing records, per development episode, whether the first run failed and why. Commit messages are prose, not a measured variable. | Have drivers emit `first_run_ok` + `failure_class` into their evidence dir. |
| 4 | **Two-arm assignment** | No mechanism assigns the same task to with/without arms. | Interleave the arms on the same instances. |

### 3.1 Power: how big would the experiment have to be?

Two-proportion Fisher exact, two-sided α=0.05, power ≥0.80, outcome = "this authored driver hit ≥1
interface-class error on first run":

| baseline (no skill) | with skill | **n per arm** | example split |
| --- | --- | --- | --- |
| 50% | 10% | **14** | 7/14 vs 1/14, p=0.033 |
| 40% | 10% | **22** | 9/22 vs 2/22, p=0.034 |
| 30% | 5% | **22** | 7/22 vs 1/22, p=0.046 |
| 25% | 5% | **35** | 9/35 vs 2/35, p=0.045 |
| 20% | 5% | **43** | 9/43 vs 2/43, p=0.049 |

**Against a substrate of 9 total episodes, the smallest credible experiment (n=14/arm) is ~28 episodes
— roughly 3× the entire history of that task class.** The experiment cannot be run by waiting for
natural work; it must be generated deliberately.

### 3.2 The falsifiability clause (already project standard)

> **An A/B test where arm A shows zero errors is UNINFORMATIVE, not a success.**
> A=0 means the task did not elicit the error, and MUST NOT be recorded as a skill success.

This matters here because the naive experiment is very likely to land on A=0: the current error rate
for interface-class failures is 0/24 authored scripts (§2.3 shows 0 across 51 dirs). A task must be
chosen that *would* produce the error with decent probability, or the experiment returns "no signal"
and cannot distinguish "skill works" from "task too easy".

---

## 4. What I did NOT do, and why

| Tempting proxy | Why I rejected it |
| --- | --- |
| "Interface errors fell to 0 after the skill existed" | Confounded twice: the gate predates the skill, and the error rate was already 0 before it. Round 2 established this; unchanged. |
| "The skills' 42 tests pass, 11/11 mutants killed" | File counts and test counts. The brief forbids it and it measures the code, not the agent. |
| "Practice drift shows the lesson propagated" | §2.2: the trick predates the skill; the majority of after-skill drivers still use the bare pattern. |
| "n=20 gate runs, 0 failures, so the gate works" | The gate is a pre-existing tool, not the skill, and 0 failures is an uninformative arm by the clause above. |
| "Detector coverage 2/6 means the skill is 33% effective" | Coverage is a **ceiling on possible** effect, not a measured effect. Nobody ran the detector on the job. |
| Treating the 105 post-skill commits as a "with" arm | They are a "without" arm: 0 of 100 files invoke a skill. |

---

## 5. The permanent role, stated operationally

Given the above, the Curator's job cannot currently be "measure effect". It is, until §3 item 1 exists:

1. **Report the adoption count every round.** It is currently 0 and it is the number that gates everything.
2. **Keep the ceiling current.** Re-run detector coverage on real bugs each round; that bounds what any
   future effect could be, and it is cheap and offline.
3. **Refuse to convert ceilings into effects.** The `PROPOSED` status is correct and no test count
   changes it.
4. **Name the missing experiment precisely** so it can be run the moment a load path exists (§3, §3.1).

**This round's honest result: a measured "cannot be measured yet", with the three reasons and the exact
experiment that would change it.**

---

## 6. Reproduce every number

| Number | Command |
| --- | --- |
| 0 invocations / 100 files / 295 branches | `git log --diff-filter=A --pretty=format:'@@%ad' --name-only -- '*.py' '*.sh'` then full-text scan for the five entrypoint strings |
| 0 of 295 branches | `for b in $(git branch -a --format='%(refname:short)'); do git grep -l -E 'development_skills/.*(preflight\|safe_pattern\|call_path_check\|effect_check)\.py' $b -- ':!development_skills'; done` |
| No load path | `ls CLAUDE.md AGENTS.md .cursorrules GEMINI.md .claude` (all absent); `grep -r development_skills --include=*.py` (0 files) |
| 12 robot A/Bs, 0 dev-practice A/Bs | `ls setup/acceptance \| grep -E '_ab_\|paired\|_vs_\|control'` then inspect each README's subject |
| 20 gate logs, all OK | `find . -name interface_check.log` then grep for `INTERFACE_CHECK_OK`/`FAILED` |
| 0 AttributeError in 51 dirs | `grep -rl -E 'has no attribute\|AttributeError' setup/acceptance/*2026111[2-]*/*.log` |
| pkill drift 5/20 → 3/12 | parse `git log --diff-filter=A -- '*.sh'` dates, classify each with `pkill.*\[[A-Za-z]\][A-Za-z_]+` (bracket) vs single-quoted literal (bare) |
| Power table | two-sided Fisher exact grid search, α=0.05, power 0.80 |

**Windows git is required** for every git command above: this worktree's `.git` is a pointer file
holding a Windows absolute path, so the WSL git binary returns an empty list — which would silently read
as "zero", the exact defect class this round's predecessor (R2-e) documented.

---

## 7. Staleness check on this audit's own numbers

The measurements below were taken while HEAD advanced from `538f0460` to `7f6de02a` (the repo is
active — 27 commits landed during the audit). Two numbers in my first draft were **wrong** and are
corrected here rather than quietly edited:

| Draft said | Actually | Cause |
| --- | --- | --- |
| 3,809 commits | **819** reachable commits (`git rev-list --all --count`) | I typed an estimate instead of running the command |
| 2,118 Python files | **2,104** distinct `.py` ever added | off-by-count from a non-deduplicated list |
| 0 of 100 files invoke a skill | 0 of **81 external** files (5 of the 100 are self-references inside the library) | the scan surface needed separating |

**Re-verification at `7f6de02a`, after those commits landed:**

```
branches with a skill invocation: 0            (all 295 branches re-scanned)
files authored after skills:      100
excluding development_skills/:     81
EXTERNAL files invoking a skill:    0
```

**The headline result is unchanged: adoption is 0.** The corrected counts do not move it, because the
result is a zero that survives re-measurement, not an estimate that could drift.

This is the same discipline as round 2's R2-e: a number claimed to be reproducible must be reproducible,
and when it is not, the discrepancy is recorded rather than smoothed over.

---

## 8. Boundary

Development Skills make the **agent** better at developing software. They are **not** robot capabilities.
Nothing in this document claims any robot capability, and nothing in it is evidence that the robot got
better or worse. The four skills remain `PROPOSED`; this audit does not change their status, and
"0 adoption" is a reason to fix the pipeline, not a reason to delete the library.