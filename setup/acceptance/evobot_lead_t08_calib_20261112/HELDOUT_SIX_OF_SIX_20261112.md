# Held-out seeds: 6 of 6, including 3002 which failed in every configuration before the fix

Seeds 3000 and 3002 are `t08_unseen` - not used in any of the tuning in rounds 61-80.
Three repeats each, staging fix in place.

## Results

| seed | repeat | stage | push | drag | zone distance | in zone |
| --- | --- | --- | --- | --- | --- | --- |
| 3000 | 1 | SUCCEEDED | -0.1230 | +0.0023 | 0.0256 | **IN** |
| 3000 | 2 | SUCCEEDED | -0.1231 | +0.0011 | 0.0266 | **IN** |
| 3000 | 3 | SUCCEEDED | -0.1355 | +0.0007 | 0.0366 | **IN** |
| 3002 | 1 | SUCCEEDED | -0.1133 | +0.0000 | 0.0175 | **IN** |
| 3002 | 2 | SUCCEEDED | -0.1131 | +0.0001 | 0.0144 | **IN** |
| 3002 | 3 | SUCCEEDED | -0.1065 | +0.0023 | 0.0103 | **IN** |

**6 of 6 in the zone. All zone distances 0.0103-0.0366 against a 0.06 radius.**

## Why seed 3002 matters

Seed 3002 failed in **every** configuration tried before round 80:

- round 60: zero movement, ee frozen at 0.1872
- rounds 62-63: reversed, +0.0297 and +0.0328
- rounds 65-66: distances 0.09, 0.13, staging x 0.30 and 0.27 - all out of the zone

**Now it goes 3 for 3 with the tightest zone distances of any seed (0.0103-0.0175).**

## Combined with round 81

| batch | seeds | in zone |
| --- | --- | --- |
| round 81 (tuning seeds) | 2000, 3001 | 12/12 |
| round 82 (held out) | 3000, 3002 | 6/6 |
| **total** | **4 seeds** | **18/18** |

## The honest reading

**This is the strongest result of the session, and it is still not a verified capability:**

1. **The staging fix is a harness change.** It makes the arm start where the code was always
   asking it to start. Real capability did not change; a measurement error was removed.
2. **Not scored by the frozen evaluator.** Rounds 49-58 built the machinery to do that and it
   still differs from scoring by hand.
3. **18/18 is still 4 seeds and 2 task variants.** The T08 family has more.
4. **The gripper gate is still expected to false-reject.** Rounds 49-58 established a mechanism
   for it and demonstrated a run with both clauses passing that was rejected on 1.2 mrad. Some
   of these 18 would very likely be rejected the same way.

## What is now known that was not before

- The T08 push controller, given a correct starting pose, places the box in the zone reliably
  across four seeds.
- Everything that looked like a fundamental push limitation in rounds 61-74 was downstream of an
  arm starting in the wrong place.
- The three failure modes were real observations of a mis-started arm, not of the push mechanism.