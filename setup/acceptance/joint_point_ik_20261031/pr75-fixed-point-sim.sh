#!/usr/bin/env bash
# Frozen, single local window per declaration; stop on any gate failure.
set -eo pipefail
FC_WS=/home/ros/agentic_workcell_ws
FC_ROOT="$FC_WS/artifacts/joint-point-runtime-20261031"
source /opt/ros/jazzy/setup.bash
source "$FC_WS/install/pr75-locked-upstream/setup.bash"
source "$FC_WS/install/pr75/local_setup.bash"
export FLEXCELL_REPO="$FC_WS" FLEXCELL_WS="$FC_WS" FLEXCELL_INSTALL="$FC_WS/install/pr75"
export FLEXCELL_SOURCE_REV=e30bd8b717884791b5900f369df83f9368db65ed
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=45 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_PARTITION=flexcell-fixed-point-local-20261031 LIBGL_ALWAYS_SOFTWARE=1 PYTHONUNBUFFERED=1
cd "$FC_WS"
test "$(git rev-parse HEAD)" = "$FLEXCELL_SOURCE_REV"
git diff --quiet -- src/flexcell scripts infra worlds setup/flexcell_admin.py plan_execute.py
test -f artifacts/joint-point-fix-20261031/verification-v2/test-result-all.log
! grep -Eq '([1-9][0-9]*) (error|failure)' artifacts/joint-point-fix-20261031/verification-v2/test-result-all.log
mkdir "$FC_ROOT"
cp "$0" "$FC_ROOT/frozen-runner.sh"
git diff c2583aec1e507386f5733285fe5399003709b4d0 HEAD -- src/flexcell scripts infra > "$FC_ROOT/source-change.patch"
sha256sum infra/core-window.json infra/joint-point-ik-local.json > "$FC_ROOT/declarations.sha256"
printf 'stage\texit_code\twall_seconds\n' > "$FC_ROOT/stages.tsv"
python3 infra/runtime_identity.py > "$FC_ROOT/identity-before.json"
fc_stage() {
  local name="$1" began="$SECONDS" code=0
  shift
  printf 'START %s\n' "$name"
  "$@" > "$FC_ROOT/$name.log" 2>&1 || code=$?
  printf '%s\t%d\t%d\n' "$name" "$code" "$((SECONDS-began))" | tee -a "$FC_ROOT/stages.tsv"
  tail -n 4 "$FC_ROOT/$name.log"
  return "$code"
}
fc_stage core-five python3 scripts/sim_window.py --manifest infra/core-window.json \
  --out "$FC_ROOT/core-window" --backend velocity_servo --skill-backend mtc
fc_stage joint-fixed-point python3 scripts/sim_window.py --manifest infra/joint-point-ik-local.json \
  --out "$FC_ROOT/joint-window" --backend detachable_joint --skill-backend mtc
