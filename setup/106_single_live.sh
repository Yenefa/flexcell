#!/usr/bin/env bash
# One feasible RunPickPlace through the currently deployed policy fleet.
# This is API smoke evidence, outside the S1-S7 statistical benchmark cells.
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo/setup/104_mainline_env.sh"
out=${1:-/tmp/flexcell_mainline_20260930/smoke}
mkdir -p "$out"
export PYTHONFAULTHANDLER=1
python3 "$repo/setup/flexcell_admin.py" reset >"$out/llm_single_reset.json" 2>&1
python3 "$repo/src/flexcell/flexcell_skills/test/w1_client.py" \
    --action task --object target_box_a --pose 0.12 -0.15 0.0175 \
    >"$out/llm_single.out" 2>&1
