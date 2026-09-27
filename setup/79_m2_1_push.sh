#!/usr/bin/env bash
# 79_m2_1_push.sh — push WSL repo main to Yenefa/flexcell via code-clone (Windows creds)
# Usage: bash 79_m2_1_push.sh <expected-full-sha>
set -o pipefail
CC="C:/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone"
WS_UNC="//wsl.localhost/Ubuntu-24.04/home/ros/agentic_workcell_ws"
EXPECT="$1"

echo "expected HEAD: $EXPECT"
git -C "$CC" fetch "$WS_UNC" refs/heads/main 2>&1 || exit 3
FETCHED=$(git -C "$CC" rev-parse FETCH_HEAD)
echo "fetched: $FETCHED"
if [ "$FETCHED" != "$EXPECT" ]; then
  echo "ABORT: fetched SHA != expected"; exit 4
fi
git -C "$CC" push origin "$FETCHED:refs/heads/main" 2>&1 || exit 5
echo "--- remote main after push ---"
git -C "$CC" ls-remote origin refs/heads/main
