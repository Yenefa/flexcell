#!/usr/bin/env bash
# M4 -- interface-class error count across round-2 authored scripts.
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

cd "$WT" || exit 2

files=$(wgit diff --name-only 0af86823^..HEAD -- '*.sh' '*.py' | grep -vE 'test|__init__')
if [ -z "$files" ]; then
  echo "REFUSED: git returned no files -- do not report this as zero errors"
  exit 2
fi

echo "scripts authored in the round-2 window (0af86823^..HEAD), excluding tests:"
echo "$files" | sed 's/^/  /'
echo "  count = $(echo "$files" | wc -l)"
echo
echo "interface-class error signatures (AttributeError | has no attribute | result.success | place_pose = Point):"
hits=0
for f in $files; do
  [ -f "$f" ] || continue
  m=$(grep -nE 'AttributeError|has no attribute|result[.]success|place_pose = Point' "$f" 2>/dev/null)
  if [ -n "$m" ]; then echo "  HIT $f"; echo "$m" | sed 's/^/      /'; hits=$((hits+1)); fi
done
echo "  files with interface-class errors: $hits"
