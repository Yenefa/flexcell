#!/usr/bin/env bash
# 70_treecheck.sh — characterize the ws repo worktree "dirty" state (read-only)
set -o pipefail
WS=/home/ros/agentic_workcell_ws
E=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
OUT="$E/70_treecheck.out"
{
  echo "=== worktree characterization | $(date -Is) ==="
  cd "$WS" || exit 3
  echo "--- porcelain ---"
  git status --porcelain | head -20
  echo "--- diff --stat (first 5) ---"
  git diff --stat | head -5
  echo "--- .gitignore raw diff (cat -A, first 8 lines) ---"
  git diff .gitignore | head -8 | cat -A
  echo "--- mode/file sample ---"
  ls -l .gitignore README.md
  git ls-files -s .gitignore README.md
  echo "--- eol related config ---"
  git config --list --show-origin | grep -iE "autocrlf|eol|safecrlf" || echo "(no eol config)"
  echo "--- gitattributes? ---"
  ls -la .gitattributes 2>&1
} > "$OUT" 2>&1
cat "$OUT"
