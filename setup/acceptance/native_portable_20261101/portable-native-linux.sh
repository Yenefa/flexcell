#!/usr/bin/env bash
set -eo pipefail
FC_WORK=/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https/work
FC_OUT="$FC_WORK/portable-native-20261101"
FC_STAGE=/home/ros/agentic_workcell_ws/build/portable-native-source-20261101
mkdir "$FC_STAGE"
tar -xf "$FC_OUT/fixed-lf-source.tar" -C "$FC_STAGE"
python3 -I -S -B "$FC_WORK/portable-native-run.py" --repo "$FC_STAGE" --out "$FC_OUT/replay-linux-lf.json"
