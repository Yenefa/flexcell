#!/usr/bin/env bash
# Use the upstream ROS-MCP server; keep its Python environment separate from ROS.
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_VENV="${FLEXCELL_MCP_VENV:-$HOME/.cache/flexcell/ros-mcp-3.1.2}"

fail() { echo "$*" >&2; exit 1; }
ros_setup() {
  [[ -f /opt/ros/jazzy/setup.bash ]] || fail 'ROS 2 Jazzy is required on this machine.'
  source /opt/ros/jazzy/setup.bash
  if [[ -n "${FLEXCELL_ROS_SETUP:-}" ]]; then
    [[ -f "$FLEXCELL_ROS_SETUP" ]] || fail "Setup not found: $FLEXCELL_ROS_SETUP"
    source "$FLEXCELL_ROS_SETUP"
  elif [[ -f "$ROOT/install/setup.bash" ]]; then
    source "$ROOT/install/setup.bash"
  fi
}
installed() {
  [[ -x "$MCP_VENV/bin/ros-mcp" ]] || fail "Run: $ROOT/scripts/ros_mcp.sh install"
}

case "${1:-help}" in
  install)
    ros_setup
    install_args=()
    if [[ -n "${FLEXCELL_MCP_PIP_INDEX:-}" ]]; then
      install_args+=(--index-url "$FLEXCELL_MCP_PIP_INDEX")
    fi
    if [[ "${FLEXCELL_MCP_VERBOSE:-0}" == 1 ]]; then
      install_args+=(--verbose)
    fi
    if ! ros2 pkg prefix rosbridge_server >/dev/null 2>&1 || ! ros2 pkg prefix rosapi >/dev/null 2>&1 ||
        { ! command -v uv >/dev/null && ! python3 -c 'import ensurepip' >/dev/null 2>&1; } ||
        ! python3 -c 'import ctypes; ctypes.CDLL("libGL.so.1"); ctypes.CDLL("libglib-2.0.so.0")' >/dev/null 2>&1; then
      if [[ $(id -u) == 0 ]]; then
        apt-get update
        apt-get install -y --no-install-recommends ros-jazzy-rosbridge-suite python3-venv libgl1 libglib2.0-0
      else
        sudo apt-get update
        sudo apt-get install -y --no-install-recommends ros-jazzy-rosbridge-suite python3-venv libgl1 libglib2.0-0
      fi
    fi
    if [[ ! -x "$MCP_VENV/bin/python" ]]; then
      if command -v uv >/dev/null; then
        uv venv --python python3 "$MCP_VENV"
      else
        python3 -m venv "$MCP_VENV" || fail 'Install python3-venv, then run install again.'
      fi
    fi
    if command -v uv >/dev/null; then
      uv pip install --python "$MCP_VENV/bin/python" "${install_args[@]}" 'ros-mcp==3.1.2'
    else
      "$MCP_VENV/bin/python" -m pip install "${install_args[@]}" 'ros-mcp==3.1.2'
    fi
    echo "Installed upstream ros-mcp 3.1.2 in $MCP_VENV"
    ;;
  bridge)
    shift
    ros_setup
    ros2 interface show flexcell_interfaces/action/RunPickPlace >/dev/null ||
      fail 'Source the active FlexCell install, or set FLEXCELL_ROS_SETUP=/path/to/install/setup.bash.'
    echo "rosbridge: ${FLEXCELL_MCP_ADDRESS:-127.0.0.1}:${FLEXCELL_MCP_PORT:-9090}, ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}, RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-ROS-default}" >&2
    if [[ -z "${RMW_IMPLEMENTATION:-}" ]]; then
      echo 'Match RMW_IMPLEMENTATION to the running stack; run110 uses rmw_cyclonedds_cpp.' >&2
    fi
    exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
      address:="${FLEXCELL_MCP_ADDRESS:-127.0.0.1}" port:="${FLEXCELL_MCP_PORT:-9090}" "$@"
    ;;
  server)
    installed
    exec "$MCP_VENV/bin/ros-mcp" --transport stdio
    ;;
  check)
    installed
    shift
    exec "$MCP_VENV/bin/python" "$ROOT/scripts/ros_mcp_check.py" \
      --server "$MCP_VENV/bin/ros-mcp" --port "${FLEXCELL_MCP_PORT:-9090}" "$@"
    ;;
  codex)
    installed
    command -v codex >/dev/null || fail 'Codex CLI is not installed. Use the MCP configuration in docs/ROS_MCP.md.'
    codex mcp add flexcell-ros -- "$ROOT/scripts/ros_mcp.sh" server
    exec codex -c 'mcp_servers.flexcell-ros.tool_timeout_sec=180'
    ;;
  *)
    echo 'Usage: scripts/ros_mcp.sh install|bridge|server|check|codex'
    echo 'bridge uses the existing simulation; it does not start or reset it.'
    echo 'Set ROS_DOMAIN_ID to the running simulation domain before bridge.'
    echo 'Set RMW_IMPLEMENTATION to the same middleware as the running stack.'
    echo 'Set FLEXCELL_ROS_SETUP when its install is outside this checkout.'
    ;;
esac
