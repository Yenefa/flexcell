#!/usr/bin/env bash
# Source this for every mainline stack, admin, client and runner process.
_flexcell_repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export FLEXCELL_WS=${FLEXCELL_WS:-/home/ros/agentic_workcell_ws}
export FLEXCELL_INSTALL=${FLEXCELL_INSTALL:-$HOME/.local/share/flexcell/mainline/install}
_flexcell_physics_env=${FLEXCELL_PHYSICS_ENV:-$HOME/.config/flexcell/mainline_physics.sh}
if [ -f "$_flexcell_physics_env" ]; then source "$_flexcell_physics_env"; fi
export ROS_DOMAIN_ID=${FLEXCELL_ROS_DOMAIN_ID:-45}
export RMW_IMPLEMENTATION=${FLEXCELL_RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
if [ -n "${FLEXCELL_DDS_PROFILE:-}" ]; then
    if [ "$RMW_IMPLEMENTATION" = rmw_cyclonedds_cpp ]; then
        export CYCLONEDDS_URI=$FLEXCELL_DDS_PROFILE
        unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
    else
        export FASTRTPS_DEFAULT_PROFILES_FILE=$FLEXCELL_DDS_PROFILE
        export FASTDDS_DEFAULT_PROFILES_FILE=$FLEXCELL_DDS_PROFILE
        unset CYCLONEDDS_URI
    fi
else
    unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE CYCLONEDDS_URI
fi
# Optional user-owned, non-secret backend profile. Credentials are read by the
# authenticated transport from a separate mode-600 file, never exported here.
_flexcell_model_env=${FLEXCELL_MODEL_ENV:-$HOME/.config/flexcell/mainline_model.sh}
if [ -f "$_flexcell_model_env" ]; then source "$_flexcell_model_env"; fi
export FLEXCELL_JEV_ENDPOINT=${FLEXCELL_JEV_ENDPOINT:-http://127.0.0.1:18081/v1/chat/completions}
export FLEXCELL_JEV_MODEL=${FLEXCELL_JEV_MODEL:-flexcell-fast}
export FLEXCELL_LLM_ENDPOINT=${FLEXCELL_LLM_ENDPOINT:-http://127.0.0.1:18082/v1/chat/completions}
export FLEXCELL_LLM_MODEL=${FLEXCELL_LLM_MODEL:-flexcell-slow}
# ROS setup scripts reference unset variables; preserve the caller's setting.
_flexcell_had_nounset=false
[[ $- == *u* ]] && _flexcell_had_nounset=true
set +u
source /opt/ros/jazzy/setup.bash
source "$FLEXCELL_WS/install/setup.bash"
source "$FLEXCELL_INSTALL/setup.bash"
$_flexcell_had_nounset && set -u
unset _flexcell_repo _flexcell_had_nounset _flexcell_model_env _flexcell_physics_env
