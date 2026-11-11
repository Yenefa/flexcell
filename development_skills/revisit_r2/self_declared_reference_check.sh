#!/usr/bin/env bash
# N2 -- does a gate compare a value to a reference supplied by the SAME producer?
#
# The pattern: "a check that compares a number to another number supplied by the same
# untrusted producer is not a check". This answers it mechanically for a verifier.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
VERIFY="$WT/benchmark/evidence/verify.py"

python3 - "$VERIFY" <<'PY'
import re, sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines()

cur = None; owner = {}
for i, l in enumerate(lines, 1):
    s = l.lstrip()
    if s.startswith("def ") and "(" in s:
        name = s[4:s.index("(")]
        if name.startswith("_gate_") or name == "verify":
            cur = name
    owner[i] = cur

pat = re.compile(r'bundle.*?\.get\("([a-z_]+)"\)')
readers = {}
for i, l in enumerate(lines, 1):
    for field in pat.findall(l):
        readers.setdefault(field, []).append((i, owner.get(i), l.strip()))

print("=== fields read from the bundle (supplied by the producer) ===")
for field in sorted(readers):
    hits = readers[field]
    gates = sorted({g for _i, g, _l in hits if g})
    print("  %-20s %d site(s)  gates: %s" % (field, len(hits), ", ".join(gates) or "-"))
    for i, g, l in hits[:3]:
        print("        %-4d %-26s %s" % (i, g or "-", l[:76]))
print()
print("=== REVIEW QUESTION ===")
print("  For each gate above: is the operand it is COMPARED AGAINST also from this")
print("  bundle? If yes, the gate is satisfiable by editing the reference, and needs")
print("  a second independent channel. Gates resting on a producer-declared reference")
print("  are listed above by name.")
PY

echo
echo "=== measured answer for the T08 verifier (see revisit_r2/forge_test.sh) ==="
echo "  rest_height_m -> table_support AND no_lift both compare against it"
echo "  pusher_links  -> pusher_contact compares against it"
echo "  => 3 of 9 gates rest on a producer-declared reference."
echo
echo "  MITIGATION, measured: table_support is TWO-SIDED (every sample within tolerance),"
echo "  so re-declaring rest_height_m to hide a carry trips table_support instead."
echo "  Recorded as mitigation, not as a pass: one channel is still producer-controlled."
