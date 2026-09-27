#!/usr/bin/env bash
# 73_week2_push.sh — push ws repo main to Yenefa/flexcell via Windows-side F: mirror
# (WSL has no github credentials and github.com:443 blackholes from WSL NAT)
# Usage (Git Bash, Windows): bash 73_week2_push.sh <expected-full-sha>
set -o pipefail
MIRROR="F:/flexcell-stage/agentic_workcell_ws"
WS_UNC="//wsl.localhost/Ubuntu-24.04/home/ros/agentic_workcell_ws"
EXPECT="$1"

echo "expected HEAD: $EXPECT"
git -C "$MIRROR" fetch "$WS_UNC" refs/heads/main 2>&1 || exit 3
FETCHED=$(git -C "$MIRROR" rev-parse FETCH_HEAD)
echo "fetched: $FETCHED"
if [ "$FETCHED" != "$EXPECT" ]; then
  echo "ABORT: fetched SHA != expected"; exit 4
fi
git -C "$MIRROR" push origin "$FETCHED:refs/heads/main" 2>&1 || exit 5
echo "--- remote main after push ---"
git -C "$MIRROR" ls-remote origin refs/heads/main
