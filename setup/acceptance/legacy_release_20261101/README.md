# One stopped legacy/joint diagnostic

Read `docs/LEGACY_RELEASE_GEOMETRY_20261101.md` for measurements and limits.
The full 69-member `raw-window.zip` preserves the one local run at Git source
`66cff2e650c7489aa59f8cce4ab8685dad59ae6e`.

```bash
python -I -S -B setup/acceptance/legacy_release_20261101/verify.py
```

Python 3.12+ and its standard library suffice. Exit 0 replays the diagnostic;
the result explicitly retains the **STOPPED** qualification window, its 24 ms
sampled release tail, the rejected raw 100 ms hold and D3 **NO_GO**. It never
dispatches a robot. `tf-static-1.cdr` is copied from the sealed original rosbag,
not a synthesized transform. The current analysis source is separately SHA-bound.
