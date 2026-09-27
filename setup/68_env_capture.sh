#!/usr/bin/env bash
# 68_env_capture.sh — capture WSL VM environment snapshot for delivery acceptance
# Usage: tr -d "\r" < 68_env_capture.sh > /tmp/env68 && bash /tmp/env68 <outfile-basename>
# Records CPU/load/memory/GPU-paravirt/rendering state as evidence.
set -o pipefail

E=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
OUT="$E/$1.out"

{
  echo "=== WSL VM environment snapshot | $(date -Is) ==="
  echo "nproc: $(nproc)"
  echo "uptime/loadavg: $(cat /proc/loadavg)"
  echo "mem: $(free -m | sed -n 2p)"
  echo "dev_dxg: $(ls -la /dev/dxg 2>&1)"
  echo "dri_cards: $(ls /dev/dri 2>&1)"
  echo "top_cpu_processes:"
  ps aux --sort=-%cpu | head -12
  echo "gz_gui_cpu_total_jiffies_check:"
  ps -o pid,pcpu,etime,comm -C gz 2>/dev/null | head -5
} > "$OUT" 2>&1

echo "[env] captured -> $OUT"
grep -E 'nproc|loadavg|dev_dxg' "$OUT"
