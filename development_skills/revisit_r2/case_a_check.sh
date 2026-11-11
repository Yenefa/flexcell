#!/usr/bin/env bash
# M6 + M7 -- does call_path_check.py catch its OWN cited case A, and does it catch round 2's real bug?
# --- Windows git helper -------------------------------------------------------
# This worktree's .git is a POINTER FILE holding a Windows absolute path, so the
# WSL git binary reports "not a git repository". A failed git call here returns an
# EMPTY file list, which reads as "zero interface errors" -- the exact round-1
# failure class (silence read as success). So: use the Windows binary, and REFUSE
# to emit a number if it did not actually produce one.
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
WWT=$(wslpath -w "$WT")
GITBIN=""
for cand in "/mnt/c/Program Files/Git/cmd/git.exe" "/mnt/c/Program Files/Git/bin/git.exe" "/mnt/c/Program Files (x86)/Git/cmd/git.exe"; do
  if [ -x "$cand" ]; then GITBIN="$cand"; break; fi
done
if [ -z "$GITBIN" ]; then
  echo "REFUSED: no Windows git.exe found. WSL git cannot read this worktree's .git"
  echo "          pointer file, and an empty result must not be reported as zero."
  exit 2
fi
wgit () { "$GITBIN" -C "$WWT" "$@"; }

DS="$WT/development_skills"
TMP=/tmp/curator_r2_caseA
rm -rf "$TMP"; mkdir -p "$TMP/caseA/benchmark/evaluators" "$TMP/fix/benchmark/evaluators"

wgit show '879d8d82^:benchmark/evaluators/evaluate.py' > "$TMP/caseA/benchmark/evaluators/evaluate.py" || { echo "REFUSED: case A extraction failed"; exit 2; }
wgit show '4fd36cd6:benchmark/evaluators/evaluate.py'  > "$TMP/fix/benchmark/evaluators/evaluate.py"  || { echo "REFUSED: fix extraction failed";  exit 2; }
wgit show '4fd36cd6^:benchmark/evaluators/evaluate.py' > "$TMP/prefix_evaluate.py"                   || { echo "REFUSED: prefix extraction failed"; exit 2; }

for f in "$TMP/caseA/benchmark/evaluators/evaluate.py" "$TMP/fix/benchmark/evaluators/evaluate.py" "$TMP/prefix_evaluate.py"; do
  [ -s "$f" ] || { echo "REFUSED: $f is empty"; exit 2; }
done

echo "=== CASE A (v0.4.0, commit 879d8d82^): verify.py exists and is tested, evaluate.py never references it ==="
echo "    lines=$(wc -l < "$TMP/caseA/benchmark/evaluators/evaluate.py")  'verify' occurrences=$(grep -c verify "$TMP/caseA/benchmark/evaluators/evaluate.py" || echo 0)"
python3 "$DS/evidence-level-audit/scripts/call_path_check.py" --symbol verify \
        --expect-caller "$TMP/caseA/benchmark/evaluators/"
echo "    exit=$?  (1 = CAUGHT, 0 = MISSED)"
echo
echo "=== CONTROL: post-fix tree (4fd36cd6), evaluate.py DOES reference verify ==="
echo "    'verify' occurrences=$(grep -c verify "$TMP/fix/benchmark/evaluators/evaluate.py" || echo 0)"
python3 "$DS/evidence-level-audit/scripts/call_path_check.py" --symbol verify \
        --expect-caller "$TMP/fix/benchmark/evaluators/"
echo "    exit=$?  (0 = correctly reports a caller present)"
echo
echo "=== ROUND-2 REAL BUG: evaluate.py CALLS verify but omits the limits argument ==="
echo "    'verify' occurrences=$(grep -c verify "$TMP/prefix_evaluate.py" || echo 0)  <- the string IS present"
python3 "$DS/evidence-level-audit/scripts/call_path_check.py" --symbol verify \
        --expect-caller "$TMP/prefix_evaluate.py"
echo "    exit=$?  (0 = MISSED -- string presence is not call correctness)"
