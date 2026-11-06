# Provenance — binding these windows to a commit

The two windows were captured from a **working tree** (identity `source_revision: WORKTREE`)
immediately before commit `a7c49ef`. The records therefore bind by content, and the binding is
checkable:

## Recorded at run time (in each window's `identity.stdout`)

| field | value |
| --- | --- |
| `source_tree_sha256` | `3b41f5a1e8cb4e91…` (full value in the file) |
| `lib/flexcell_mtc/mtc_planner` | `dec1d4505515b167…` |
| `lib/libflexcell_physics_trace.so` | `4fb2f1f2cad09f89…` |
| `lib/libflexcell_contact_trace.so` | `51088e5517d4f02a…` |
| `lib/libflexcell_detachable_carry.so` | `387fc1d43b525585…` |
| `mismatches` | `[]` |

Both windows report the same tree and library digests.

## Reconciled against the commit (re-run after `a7c49ef`)

On a clean tree at `a7c49ef46a192641ed11881139007028b4366aa5` (`git status --porcelain` empty),
`infra/runtime_identity.py` reports the **same** `source_tree_sha256` (`3b41f5a1e8cb4e91…`),
`mismatches: []`, and the **same** planner and plugin digests listed above. So the code that ran
the windows is byte-identical to the committed tree.

Reproduce the reconciliation:

```
git -C <repo> rev-parse HEAD           # a7c49ef...
git -C <repo> status --porcelain       # empty
source /opt/ros/jazzy/setup.bash && source /home/ros/r4check/install/setup.bash
PYTHONPATH=/home/ros/r4check/build/flexcell_skills:/opt/ros/jazzy/lib/python3.12/site-packages \
FLEXCELL_REPO=<repo> FLEXCELL_INSTALL=/home/ros/r4merged/install \
python3 infra/runtime_identity.py | grep source_tree_sha256
```

`FLEXCELL_INSTALL` must be the merged view: the identity tool hashes
`share/flexcell_skills/launch` **and** `lib/libflexcell*.so` from one prefix, while this machine's
colcon install is isolated (per-package prefixes). The merged view is symlinks only; the hashes
are read through them, so the digests are the real artifact digests.

## What this does and does not establish

- Establishes: the recorded windows ran exactly this source tree and these native artifacts, and
  that tree is the one in `a7c49ef`.
- Does not establish: that the committed files were reviewed in the same order, that the machine
  state (GPU, DDS, load) matched, or that other commits on the branch were exercised.
