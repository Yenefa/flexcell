# Agent instructions

## Development Skills (optional, UNMEASURED)

`development_skills/registry.json` lists skills that are meant to help **you, the agent, develop software** — not
skills the robot performs. Its `development_skills/README` and `REVISIT_R2_20261112.md` carry the detail.

**Read that registry if you are about to do development work and want to check whether a relevant practice is
recorded there.** That is all this section is for: a pointer. Nothing here is mandatory.

### Status: do not overstate it

Every entry is `PROPOSED` with `effect: NOT_MEASURED`, and a measurement across the whole repository history
found **adoption is zero** — 295 branches, 819 commits, 2,104 `.py` and 206 `.sh`, **0 invocations** of any skill
entrypoint. See `setup/acceptance/evobot_lead_curator_measure_20261112/`.

**So: this directory has never been tried.** That is not evidence it does not work, and it is certainly not
evidence that it does. If you use a skill, record that you did — an unrecorded use is indistinguishable from no
use, which is exactly how the adoption count came out zero.

**The 42 unit tests in `development_skills/` are not an achievement.** They test that the skills are well-formed;
they say nothing about whether using them helps. Do not cite the test count as a result.

### It must never displace the main line

These skills are subordinate to the repository's actual objective. If consulting them competes with real work,
**the real work wins.** They are a development aid, not a task, and not a deliverable.

---

## For this repository's own goal

The authoritative objective is `docs/EVOBOT_MASTER_GOAL_20261112.md`, with `docs/EVOBOT_NORTH_STAR_MISSION.md` as
the higher authority. Start with `docs/FACT_STATE_20261112.md` — it is append-only and records what is CITED,
what was WITHDRAWN, and which numbers may not be quoted. It contains retractions; read them before citing a
figure.
