#!/usr/bin/env bash
# M2 -- mutation testing. Every mutation is byte-verified BEFORE its test result is trusted.
# This is the guard that round 1 lacked (sed -i on /mnt/c silently failed there).
set -u
DS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK=/tmp/curator_r2_mut
rm -rf "$WORK"; mkdir -p "$WORK"

mutate () {
  local skill="$1" scriptrel="$2" tests="$3" label="$4" old="$5" new="$6"
  rm -rf "$WORK/m"; cp -r "$DS/$skill" "$WORK/m"
  rm -rf "$WORK/m/.pytest_cache" "$WORK/m/scripts/__pycache__" "$WORK/m/tests/__pycache__"
  python3 - "$WORK/m/$scriptrel" "$old" "$new" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
if old not in text:
    print("ANCHOR_MISSING"); raise SystemExit(3)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PY
  if [ $? -ne 0 ]; then echo "  $label -> MUTATION DID NOT APPLY (anchor)"; return 2; fi
  if cmp -s "$WORK/m/$scriptrel" "$DS/$skill/$scriptrel"; then
    echo "  $label -> MUTATION DID NOT APPLY (byte-identical)"; return 2; fi
  out=$(cd "$WORK/m" && python3 -m pytest "$tests" -q 2>&1 | tail -3)
  if echo "$out" | grep -qE '[0-9]+ (failed|error)'; then
    echo "  $label -> KILLED"
  else
    echo "  $label -> SURVIVED ($(echo "$out" | tail -1))"
  fi
}

echo "ros2-interface-preflight (registry claims 3):"
mutate ros2-interface-preflight scripts/preflight.py tests "M1 REQUIRED_FRAME" 'REQUIRED_FRAME = "world"' 'REQUIRED_FRAME = "base_link"'
mutate ros2-interface-preflight scripts/preflight.py tests "M2 identity quat" 'IDENTITY_QUAT = [0.0, 0.0, 0.0, 1.0]' 'IDENTITY_QUAT = [0.0, 0.0, 0.0, 0.999]'
mutate ros2-interface-preflight scripts/preflight.py tests "M3 object_name rule" 'if not getattr(entry, "object_name", ""):' 'if False:'
mutate ros2-interface-preflight scripts/preflight.py tests "M4 tolerance bound" 'elif not TOLERANCE_RANGE[0] < tol <= TOLERANCE_RANGE[1]:' 'elif False:'
echo "simulation-process-lifecycle (registry claims 2):"
mutate simulation-process-lifecycle scripts/safe_pattern.py tests "M1 bracket whole name" 'return "[" + name[0] + "]" + name[1:]' 'return "[" + name + "]"'
mutate simulation-process-lifecycle scripts/safe_pattern.py tests "M2 never hazardous" 'if len(match.group(1)) != 1:' 'if False:'
mutate simulation-process-lifecycle scripts/safe_pattern.py tests "M3 raise match cap" 'MAX_SAFE_MATCHES = 40' 'MAX_SAFE_MATCHES = 10**9'
echo "evidence-level-audit (registry claims none):"
mutate evidence-level-audit scripts/call_path_check.py tests "M1 always report OK" 'print("ABSENT %s: no file references %r -- it is a document, not a gate"' 'print("OK     %s: no file references %r -- it is a document, not a gate"'
echo "effect-verification (registry claims 3):"
mutate effect-verification scripts/effect_check.py tests "M1 empty is success" 'if isinstance(value, (str, list, dict, tuple)) and len(value) == 0:' 'if False:'
mutate effect-verification scripts/effect_check.py tests "M2 ignore differences" 'if now == before:' 'if False:'
mutate effect-verification scripts/effect_check.py tests "M3 accept no-tests-ran" 'if "no tests ran" in output or "collected 0 items" in output:' 'if False:'
