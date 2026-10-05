#!/usr/bin/env bash
set -eo pipefail
evidence=/home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005
mkdir -p "$evidence"
chown ros:ros "$evidence"
old_pattern=$(cat /proc/sys/kernel/core_pattern)
printf '%s\n' "$old_pattern" > "$evidence/core_pattern_before.txt"
trap 'printf "%s\n" "$old_pattern" > /proc/sys/kernel/core_pattern' EXIT
printf '%s\n' "$evidence/core.%e.%p" > /proc/sys/kernel/core_pattern
ulimit -c unlimited
set +e
runuser -u ros -- bash /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_teardown_run_20261005.sh capture
probe_rc=$?
set -e
for core in "$evidence"/core.*; do
    [ -f "$core" ] || continue
    gdb -batch -ex 'set debuginfod enabled off' -ex 'thread apply all bt' /usr/bin/python3 "$core" > "$core.gdb.txt" 2>&1
done
echo "PROBE_RC=$probe_rc"
