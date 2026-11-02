#!/usr/bin/env bash
set -eo pipefail
cd /home/ros/agentic_workcell_ws
git diff --quiet
git fetch --no-tags /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone refs/heads/fix/joint-point-ik
git merge --ff-only FETCH_HEAD
source /opt/ros/jazzy/setup.bash
source install/pr75-locked-upstream/setup.bash
source install/pr75/local_setup.bash
export CMAKE_BUILD_PARALLEL_LEVEL=2 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PYTHONDONTWRITEBYTECODE=1
FC_OUT=artifacts/joint-point-fix-20261031/dependency-check
mkdir "$FC_OUT"
colcon list --packages-up-to flexcell_mtc > "$FC_OUT/package-graph.tsv"
grep -q '^flexcell_skills' "$FC_OUT/package-graph.tsv"
test "$(git diff e30bd8b HEAD --name-only)" = src/flexcell/flexcell_mtc/package.xml
colcon --log-base log/joint-point-dependency-build build --merge-install --build-base build/pr75 --install-base install/pr75 \
  --packages-select flexcell_mtc --cmake-args -DCMAKE_BUILD_TYPE=Release > "$FC_OUT/build.log" 2>&1
colcon --log-base log/joint-point-dependency-test test --build-base build/pr75 \
  --packages-select flexcell_mtc --test-result-base "$FC_OUT/test-results" > "$FC_OUT/tests.log" 2>&1
colcon test-result --test-result-base "$FC_OUT/test-results" --verbose > "$FC_OUT/test-result.log" 2>&1
python3 - <<'PY'
import hashlib,json,pathlib,subprocess
repo=pathlib.Path('/home/ros/agentic_workcell_ws')
identity=json.loads((repo/'artifacts/joint-point-runtime-20261031/identity-before.json').read_text())
relative='lib/flexcell_mtc/mtc_planner'
digest=hashlib.sha256((repo/'install/pr75'/relative).read_bytes()).hexdigest()
assert digest==identity['native_libraries'][relative]
receipt={'final_code_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         'physical_run_revision':identity['source_revision'],'native_binary_unchanged':True,'native_sha256':digest,
         'only_post_run_code_delta':'test_depend flexcell_skills in flexcell_mtc/package.xml'}
(repo/'artifacts/joint-point-fix-20261031/dependency-check/receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
PY
cat "$FC_OUT/test-result.log"
