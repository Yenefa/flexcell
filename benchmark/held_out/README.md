# Held-out — sealed answer design

The mission requires held-out instances to be unreadable by the agent. Until now that
was a documented promise, not an enforced property. This directory now holds only the
PUBLIC tasks.

| Path | Contents | Agent may read |
| --- | --- | --- |
| `benchmark/held_out/public/*.json` | instruction, objects, zones, opaque task id, budget | **yes** |
| `/etc/evobot/sealed/*.json` (root:root 600) | `expected_goal`, template, seed, hash | **no** |

The public file contains **no** `expected_goal`, `constraints`, `template_id`,
`random_seed`, or seed-bearing task id. `assert_public_is_clean` enforces that.

The agent process is started under an unprivileged UID via
`sudo -n setpriv --reuid=1001 --regid=1001 --clear-groups`, which was verified to be
unable to read the sealed directory and unable to re-acquire sudo. The evaluator runs
separately with privilege.

**Limit, stated plainly:** this is OS permission isolation, not a kernel namespace. A
process started as root, or one that can escalate, defeats it. It also cannot undo the
fact that the *previous* (v0.1) held-out specs were committed to git with their answers
in clear text. Those are therefore **retired as contaminated** and must never be used
to support a generalisation claim. The new set uses a fresh salted id scheme and its
answers never enter the checkout.
