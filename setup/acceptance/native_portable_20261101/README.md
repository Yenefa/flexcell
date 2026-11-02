# Portable native source binding correction

This supplements #85 after #87 correctly reproduced the LF-checkout failure.
It preserves the original capsule, receipt, source binding and raw ZIP byte for
byte; it neither reruns nor replaces a physical window.

The old checker compared four raw checkout SHA-256 values. Two came from LF and
two from CRLF files on Windows. The previous Linux run used the Windows mount;
it proved interpreter compatibility, not an independent Git LF checkout.

The fixed checker only changes CRLF pairs to LF for the four explicitly listed
Python gate sources. Their resulting SHA must equal the sealed runtime/Git 3328693
source map. The historical raw checkout SHA must independently match that same
content as LF or its exact CRLF transport form. No decoding, whitespace stripping,
BOM removal, lone-CR removal or source-code tolerance is added. Both observations
are returned by the replay. Original `INVALID_TRAILING_CR` metadata remains.

```bash
python3 setup/acceptance/native_audit_20261031/verify.py
python3 setup/acceptance/native_portable_20261101/reproduce-old-lf.py
```

The first command must pass from a real Git LF checkout. The second reproduces the
old pre-replay failure on that LF checkout. Both are read-only and stdlib-only.

Evidence:

- source freeze `009b5af029a0d0ff178a9e3a2aa420b68c9ad753`, Git LF archive SHA
  `8eb3d17da603af08742f969c9afcdbe98cc625e19bc7352edc4f2c8e6243d465`;
- 35 byte-transport/integrity cases, calling the real verifier; red 25 failed /
  10 passed, then green, plus existing native tests: 50 passed;
- complete Python suite: 742 passed, three existing fork warnings; static scan:
  40 files, zero findings;
- Windows and Linux independently replayed the same Git LF archive in `-I -S -B`
  mode, with no site packages/ROS/Gazebo; both passed all preserved raw gates;
- the first Windows wrapper invocation failed from a relative-path/cwd mistake,
  before opening the verifier. Its empty stdout and original stderr are retained;
  the corrected invocation used absolute paths. This is a runner failure, not a
  failed physical window or gate result;
- `legacy-review.json` independently recomputes #86's four cells from the submitted
  verify rows, and reproduces the host/container relocation false-PASS. Its 389,120
  byte Git source archive is retained. Repair of that reporter remains junior #82.

Raw historical ZIP SHA remains:
`eed67b533957848cdc64dda090a4911a66344e81d7a7655269da6edc45591446`.
Historical CI remains STOPPED/UNKNOWN, source revision metadata remains visibly
INVALID_TRAILING_CR, and D3 remains NO_GO. Robot actions this correction: zero.
