# CORRECTION: the harness was never broken. I chose invalid ROS domain IDs.

**Date** 2026-11-12 (round 25) · **Status: RESOLVED. Root cause was my own wrapper.**

---

## The answer, in one table

```
domain 183 : NODE OK
domain 200 : NODE OK
domain 232 : NODE OK
domain 233 : RCLError: error creating node: error not set, at ./src/rcl/node.c:252
domain 241 : RCLError: error creating node: error not set, at ./src/rcl/node.c:252
```

**ROS 2 domain IDs are valid only in 0..232.** Above that the DDS port calculation overflows: FastRTPS says it
outright — *"Calculated port number is too high. Probably the domainId is over 232"* — and CycloneDDS fails
less helpfully with `error not set` at `rcl/node.c:252`.

## What I did, and what it cost

| round | action | domain used | outcome |
| --- | --- | --- | --- |
| 21 | built `run_paired.sh`, rotating domains **to avoid participant exhaustion** | **241–246** | invalid |
| 22 | launched 66 trials | 241 | 2/2 `HARNESS_ERROR`, run killed as void |
| 23 | "isolation" test, clean environment | 251 | same failure — **concluded the stack was dead** |
| 24 | three fixes: localhost-only, hostname, hosts | 260/261/262 | same failure — **concluded UNRESOLVED** |
| 24 | RMW binding, alternate middleware | 270 | FastRTPS finally said *domainId is over 232* |

**Every diagnostic in rounds 23–24 used an invalid domain.** I was testing a configuration that could not work
and reading its failure as evidence about the simulator.

## The error I made, precisely

I introduced domain rotation in round 21 because round 18 found that **domain reuse** exhausts CycloneDDS
participants — the T05 n6 batch failed with *"resulting port numbers (65660, 65661) are out of range"* at
**domain 233**. **That message was already telling me 233 was the problem** — I read it as "participants
exhausted" and not as "domain out of range", then chose 241–246, which repeats the same mistake harder.

The original script's `ROS_DOMAIN_ID=183` was **valid all along**. The rotation was unnecessary for the reason I
gave it and fatal for the reason I missed.

## Fixed

`run_paired.sh` now uses **200 + chunk** (200–205), inside the legal range. The evidence script remains
unmodified.

## What this costs the record

- **Rounds 23 and 24 reached a wrong conclusion** ("the harness is deterministically broken"), and both are now
  superseded by this file. They are left in place rather than deleted: a diagnosis that was wrong for a
  mundane reason is worth keeping.
- **Nothing about T08 was learned or lost.** The registered experiment is still unrun and still binding.
- **The lesson is the same one this project keeps teaching**: the instrument was fine, and the thing that
  needed validating was my own change to it.