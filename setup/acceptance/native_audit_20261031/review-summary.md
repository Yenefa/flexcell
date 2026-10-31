# Independent read-only review

Scope: `11de8251c128d1e9712834829b932445668d318f` to
`3328693107c217d291d3fe6f7d6b52812a6618da`, plus the evidence verifier and explicit
source-binding supplement. Reviewer: `native_runtime_review` (runtime debugger).
No source edits, simulator starts, ROS requests or remote writes by the reviewer.

- No remaining P1/P2 blockers. Audit helper returns a small summary, with no raw
  row/list/view/closure retained. Original gate calls and thresholds remain.
- Weak-reference red/green receipts establish row lifetime; no forced GC.
- Independent in-memory execution of actual Follower/worker AST confirmed snapshot
  reads do not consume input or modify tables. Injected snapshot `OSError` retains
  original guard failure, traceback and positive failure clock.
- Frozen worker bytes match Git at both versions; Python/launch/native hashes
  match across windows. Both recorded windows contain five passing cycles.
- One initial P2 found and closed: trailing CR in patched revision caused strict
  replay to fail. All 209 recorded source-file hashes were independently compared
  against Git blobs using `git cat-file --batch` and the original Git tar. Tar
  bytes/hash/PAX comment, exact sidecar CRLF, identity CR and source-tree digest
  match the explicit supplement. Original ZIP is unchanged; metadata defect stays
  visible, with no generic strip or replacement window.
- The performance comparison covers one diagnostic window per version. Historical
  CI pause source remains UNKNOWN; D3 remains NO_GO.

The first strict Windows replay exited 1 at the unnormalized revision equality in
`local_window`. Its stdout was empty and remains in the local artifact directory.
`receipt-before-source-binding.json` preserves the initial receipt assumption.
After the bounded source supplement, Windows and Linux replays exited 0. All raw runtime
data and the 114-member ZIP retain their original bytes.
