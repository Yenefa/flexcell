#!/usr/bin/env bash
# FlexCell acceptance gate helper (M2.3 audit P1-5 / P1-7 / P1-8).
#
# The audit found that the acceptance batteries only echoed "EXPECT: ..." and
# never failed - they could not red-flag anything.  Batteries source this file
# and register hard gates; gate_finalize exits non-zero when any gate failed.
#
# Session versioning (P1-7): gate_init creates
#   $FLEXCELL_STAGE/setup/acceptance/sessions/<suite>_<sha>_<ts>/
# and every artifact lands INSIDE it, with a header carrying commit sha +
# timestamp.  Sessions are never overwritten or mixed across runs.
#
# Environment overrides (machine portability):
#   FLEXCELL_WS     default /home/ros/agentic_workcell_ws
#   FLEXCELL_STAGE  default /mnt/f/flexcell-stage

GATE_FAILS=0
GATE_SESSION=''

_flexcell_ws() { echo "${FLEXCELL_WS:-/home/ros/agentic_workcell_ws}"; }
_flexcell_stage() { echo "${FLEXCELL_STAGE:-/mnt/f/flexcell-stage}"; }

gate_init() { # <suite-name>
  local suite="$1" sha ts
  sha=$(git -C "$(_flexcell_ws)" rev-parse --short HEAD 2>/dev/null || echo unknown)
  ts=$(date +%Y%m%d_%H%M%S)
  GATE_SESSION="$(_flexcell_stage)/setup/acceptance/sessions/${suite}_${sha}_${ts}"
  mkdir -p "$GATE_SESSION"
  {
    echo "suite: $suite"
    echo "commit: $sha"
    echo "started: $(date -Is)"
    echo "host: $(hostname)"
    echo "ws: $(_flexcell_ws)"
  } > "$GATE_SESSION/00_header.txt"
  echo "GATE session: $GATE_SESSION"
}

gate_session_dir() { echo "$GATE_SESSION"; }

gate_check() { # <name> <file> <expected-egrep-regex>
  local name="$1" file="$2" want="$3"
  if [ ! -f "$file" ]; then
    echo "GATE FAIL $name: artifact missing: $file"
    GATE_FAILS=$((GATE_FAILS + 1))
    return 1
  fi
  if grep -qE "$want" "$file"; then
    echo "GATE PASS $name"
    return 0
  fi
  echo "GATE FAIL $name: /$want/ not matched in $file"
  GATE_FAILS=$((GATE_FAILS + 1))
  return 1
}

# numeric gate: last "<key>: <float>" in <file> must be < <threshold>
gate_num_lt() { # <name> <file> <key> <threshold>
  local name="$1" file="$2" key="$3" thr="$4" val
  val=$(grep -o "\"$key\": [0-9.]*" "$file" 2>/dev/null | head -1 | grep -o '[0-9.]*$')
  if [ -z "$val" ]; then
    echo "GATE FAIL $name: $key not found in $file"
    GATE_FAILS=$((GATE_FAILS + 1))
    return 1
  fi
  if awk "BEGIN{exit !($val < $thr)}"; then
    echo "GATE PASS $name ($key=$val < $thr)"
    return 0
  fi
  echo "GATE FAIL $name: $key=$val not < $thr"
  GATE_FAILS=$((GATE_FAILS + 1))
  return 1
}

# audit P1-8: a gz.msgs.Pose "No message class registered" traceback flood
# poisoned the reset artifacts; the vocabulary must stay at zero.
gate_flood() { # <file>
  local file="$1" n
  n=$(grep -c "No message class registered" "$file" 2>/dev/null); n=${n:-0}
  if [ "$n" -eq 0 ]; then
    echo "GATE PASS flood-clean $(basename "$file")"
    return 0
  fi
  echo "GATE FAIL flood-clean $(basename "$file"): $n unregistered-gz-class tracebacks"
  GATE_FAILS=$((GATE_FAILS + 1))
  return 1
}

gate_finalize() {
  {
    echo "finished: $(date -Is)"
    echo "gate failures: $GATE_FAILS"
  } >> "$GATE_SESSION/00_header.txt" 2>/dev/null
  if [ "$GATE_FAILS" -eq 0 ]; then
    echo "GATE: ALL PASS ($GATE_SESSION)"
    return 0
  fi
  echo "GATE: $GATE_FAILS FAILURE(S) ($GATE_SESSION)"
  return 1
}
