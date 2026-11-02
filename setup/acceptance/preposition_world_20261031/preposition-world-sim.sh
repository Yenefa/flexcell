#!/usr/bin/env bash
# Single declared window, frozen source and isolated installed artifacts.
set -eo pipefail
FC_STAGE=/home/ros/agentic_workcell_ws/build/preposition-world-stage
FC_OUT=/home/ros/agentic_workcell_ws/artifacts/preposition-world-20261031
source /opt/ros/jazzy/setup.bash
source "$FC_STAGE/upstream/install/setup.bash"
source "$FC_STAGE/install/local_setup.bash"
export FLEXCELL_REPO="$FC_STAGE" FLEXCELL_WS="$FC_STAGE" FLEXCELL_INSTALL="$FC_STAGE/install"
export FLEXCELL_SOURCE_REV=19caa0199660c6a0d9d95af14620695dde0eedcf
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=45 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_PARTITION=flexcell-preposition-world-20261031 LIBGL_ALWAYS_SOFTWARE=1 PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
test "$(cat "$FC_OUT/source-revision.txt")" = "$FLEXCELL_SOURCE_REV"
grep -Eq '^Summary: [0-9]+ tests, 0 errors, 0 failures, 0 skipped$' "$FC_OUT/test-result.log"
cd "$FC_STAGE"
cp "$0" "$FC_OUT/frozen-runtime-runner.sh"
sha256sum infra/joint-preposition-world.json > "$FC_OUT/runtime-declaration.sha256"
python3 infra/runtime_identity.py > "$FC_OUT/identity-before.json"
started=$SECONDS
code=0
python3 scripts/sim_window.py --manifest infra/joint-preposition-world.json \
  --out "$FC_OUT/joint-window" --backend detachable_joint --skill-backend mtc > "$FC_OUT/joint-window.log" 2>&1 || code=$?
printf 'stage\texit_code\twall_seconds\nworld-hold-joint\t%d\t%d\n' "$code" "$((SECONDS-started))" > "$FC_OUT/runtime-stages.tsv"
tail -n 5 "$FC_OUT/joint-window.log"
exit "$code"
