# Portable native source binding

**Goal:** Fix #85's LF-checkout replay rejection without rewriting historical
evidence or allowing a changed gate. This unblocks the native half of junior #84;
the one-line workflow integration remains owned by #87.

**Observed cause:** At b042f9b a clean Git archive fails before raw replay on
`scripts/contact_gate.py`. Two historical `verification_sources` digests bind CRLF
working-tree files, two bind LF files. All four canonical LF digests already match
the sealed 209-file runtime source map and Git 3328693. The previous Linux replay
used the Windows mount, so it verified a Linux interpreter, not an independent LF
checkout. Preserve and qualify that historical result explicitly.

**Design:** Treat the original digests as historical checkout observations. For
exactly the four gate files, convert CRLF pairs to LF and require the resulting
SHA-256 to equal the already sealed runtime-source digest. Independently require
the original recorded checkout digest to match either that exact LF content or
its exact LF-to-CRLF conversion. Preserve BOM, lone CR, whitespace, code and all
other bytes; any such difference fails. Record the observed byte digest and line
ending form in the new replay output. Keep original receipt/binding/ZIP bytes.

Simply replacing historical receipt digests would erase the original observation;
accepting arbitrary edits or decoding/stripping whitespace would weaken source
identity. Git subprocesses at replay time would add an unnecessary dependency.
The existing sealed runtime map supplies the canonical content identity offline.

## Implementation and checks

- [ ] Add behavior tests against the actual verifier before changing it: all 16
  per-file LF/CRLF combinations and within-file mixtures must reach raw extraction;
  non-EOL changes, missing/extra identities and a corrupted historical digest must
  fail before extraction. Mock only the expensive raw extraction boundary.
- [ ] Save the expected red result plus the unmodified CLI LF failure.
- [ ] Implement a small `verify_sources(repo, receipt, binding)` helper and call it
  before loading gate modules. Return exact observed/canonical digest observations.
- [ ] Run the new tests and existing native-window tests, then the complete offline
  Python suite and existing static scan. Gate/controller/physics code stays unchanged.
- [ ] Export a new immutable Git LF snapshot. Replay all original raw gates from
  that snapshot on Windows and Linux, using isolated stdlib-only interpreters.
- [ ] Independently review source identity boundaries. Preserve old receipts and
  both historical defects, update #85 and notify #87/#84 with exact commands/results.
- [ ] Archive reproducible tests, source bindings, old failure and new replay
  results; refresh HANDOFF/diary and provide a portable delivery bundle.

The 500 ms/native physical thresholds, first eligible candidate, admission and
historical CI STOPPED verdict remain unchanged. Robot/simulator dispatches: zero.
#59 still lacks CI execution; #86 local measurements do not close that criterion.
