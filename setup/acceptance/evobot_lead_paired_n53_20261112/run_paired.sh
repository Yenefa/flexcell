#!/usr/bin/env bash
# Paired n>=53 recovery run: the experiment established in round 20.
#
# WHY A WRAPPER RATHER THAN AN EDIT
#   The existing evidence script hardcodes ROS_DOMAIN_ID=183 for every trial. Domain reuse
#   exhausts CycloneDDS participant slots - that is the measured cause of the T05 n6 batch
#   failing 4 of 6 runs with 'Failed to create unicast sockets for domain 233 participant
#   index 0'. So the domain must rotate. Rather than modify a script that already produced
#   committed evidence, this wrapper calls it UNMODIFIED once per chunk with a fresh domain.
#
#   Each chunk is 11 trials, well inside one domain's participant budget. Output goes to a
#   per-chunk directory; the tsvs are concatenated by summarise.sh afterwards.
set -u
OUT=${1:?output dir}
CHUNKS=${2:-6}
PER=${3:-11}
SCRIPT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_push_recover_20261112/scripts/evobot_t08_recovery_run.sh
mkdir -p "$OUT"
echo "wrapper start $(date -Is) chunks=$CHUNKS per=$PER" | tee -a "$OUT/wrapper.log"
for C in $(seq 1 "$CHUNKS"); do
  # ROS 2 domain IDs are 0..232. Above that the DDS port calculation overflows and NODE CREATION
  # FAILS with 'error creating node: error not set'. Round 22 used 241-246 and round 23-24 tested
  # 251/260/261/262/270/271 - every one of them invalid - and concluded the harness was broken. It
  # was not: see HARNESS_DIAGNOSIS.md, corrected below.
  DOMAIN=$((200 + C))
  echo "=== chunk $C  ROS_DOMAIN_ID=$DOMAIN ===" | tee -a "$OUT/wrapper.log"
  EVOBOT_ROS_DOMAIN=$DOMAIN timeout 3600 bash "$SCRIPT" "$OUT/c$C" "$PER" 0.0200 3 >> "$OUT/wrapper.log" 2>&1
  RC=$?
  echo "chunk $C exit=$RC $(date -Is)" | tee -a "$OUT/wrapper.log"
  if [ -f "$OUT/c$C/recovery.tsv" ]; then
    N=$(($(wc -l < "$OUT/c$C/recovery.tsv") - 1))
    echo "  chunk $C produced $N trial rows" | tee -a "$OUT/wrapper.log"
  else
    echo "  chunk $C produced NO tsv" | tee -a "$OUT/wrapper.log"
  fi
done
pkill -9 -f 'gz sim' 2>/dev/null || true
pkill -9 -f 'ros2 launch' 2>/dev/null || true
echo "wrapper done $(date -Is)" | tee -a "$OUT/wrapper.log"