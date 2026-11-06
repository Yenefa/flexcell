# Provenance — binding these windows to a commit

The two windows were captured from a **working tree** (identity `source_revision: WORKTREE`)
immediately before commit `a7c49ef`. The records therefore bind by content, and the binding is
checkable.

## Two digests, two scopes — do not conflate them

`infra/runtime_identity.py` hashes the *working tree* under `src/flexcell`, `infra`, `scripts`,
`worlds` plus `setup/flexcell_admin.py` and `plan_execute.py`, excluding only `__pycache__` and
`.git`. That walk also picks up local pytest state, so it is **not** a source digest:

| scope | files | digest |
| --- | --- | --- |
| working-tree walk as recorded in `identity.stdout` | 261 | `3b41f5a1e8cb4e91…` (full value in the file) |
| the same walk restricted to **git-tracked** files | **255** | **`e91eda9b146f233cb004a93e53be0ff096e06c0ccaaa29d539a46e27975891f3`** |

The six-file difference is exactly the local pytest cache:

```
src/flexcell/flexcell_skills/.pytest_cache/{.gitignore,CACHEDIR.TAG,README.md}
src/flexcell/flexcell_skills/.pytest_cache/v/cache/{lastfailed,nodeids,stepwise}
```

So when this evidence says "the window ran this source", the source claim rests on the
**tracked-only** digest `e91eda9b…`; `3b41f5a1…` is the run-time fingerprint the harness recorded
and is reproducible only on a machine that still has those pytest-cache files.

## Recorded at run time (in each window's `identity.stdout`)

| field | value |
| --- | --- |
| `source_tree_sha256` | `3b41f5a1e8cb4e91…` (working-tree walk, see scope note above) |
| `lib/flexcell_mtc/mtc_planner` | `dec1d4505515b167…` |
| `lib/libflexcell_physics_trace.so` | `4fb2f1f2cad09f89…` |
| `lib/libflexcell_contact_trace.so` | `51088e5517d4f02a…` |
| `lib/libflexcell_detachable_carry.so` | `387fc1d43b525585…` |
| `mismatches` | `[]` |

Both windows report the same tree walk and the same library digests.

## Reconciled against the commit (re-run after `a7c49ef`)

On a clean checkout of `a7c49ef46a192641ed11881139007028b4366aa5` (`git status --porcelain`
empty) the identity tool reproduces `3b41f5a1e8cb4e91…` and the same library digests, and all
**255** git-tracked files in scope hash to `e91eda9b146f233c…`. So the source that ran the
windows is the source in the commit.

Reproduce both digests:

```
git -C <repo> rev-parse HEAD            # a7c49ef...
git -C <repo> status --porcelain        # empty
# tracked-only source digest (scopes as in infra/runtime_identity.py)
python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
repo = Path.cwd()
scope = ('src/flexcell', 'infra', 'scripts', 'worlds')
extra = ('setup/flexcell_admin.py', 'plan_execute.py')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
tracked = {p.decode() for p in subprocess.run(['git', 'ls-files', '-z'],
           capture_output=True, check=True).stdout.split(b'\0') if p}
files = {str(p.relative_to(repo)): sha(p)
         for d in scope for p in (repo / d).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts}
files.update({r: sha(repo / r) for r in extra})
print(hashlib.sha256(json.dumps({k: v for k, v in files.items() if k in tracked},
                                sort_keys=True).encode()).hexdigest())
PY
```

`FLEXCELL_INSTALL` for the identity tool must be the merged view (`/home/ros/r4merged/install`):
the tool hashes `share/flexcell_skills/launch` **and** `lib/libflexcell*.so` from one prefix,
while this machine's colcon install is isolated. The view is symlinks only, so the digests are the
real artifact digests.

## What this does and does not establish

- Establishes: the recorded windows ran a source tree whose **tracked** content is exactly the
  content of `a7c49ef`, and the harness recorded these native-artifact digests at run time.
- Does **not** establish, and this evidence does **not** claim:
  - that the native binaries were independently rebuilt or that the loaded mappings were verified
    in the review round (only their digests were recorded and compared across the two windows);
  - that the machine state (DDS, load, GPU) matched between runs;
  - that other commits on the branch were exercised;
  - that any CI job passed — all five check jobs on this branch still have **zero execution
    steps** and are not recorded as passing here.
