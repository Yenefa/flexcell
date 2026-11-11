# Non-secret runtime profile; credential stays in the separate private file.
export FLEXCELL_LLM_ENDPOINT=https://api.deepseek.com/chat/completions
export FLEXCELL_LLM_MODEL=deepseek-flash
# Credential is materialised through the budget gate, not pointed at the private file.
EVOBOT_LLM_GATE=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh
if [ ! -f "$EVOBOT_LLM_GATE" ]; then echo "FATAL: missing budget gate $EVOBOT_LLM_GATE" >&2; return 3 2>/dev/null || exit 3; fi
EVOBOT_LLM_KEY_TMP=$(mktemp) || { return 3 2>/dev/null || exit 3; }
bash "$EVOBOT_LLM_GATE" > "$EVOBOT_LLM_KEY_TMP" || { rm -f "$EVOBOT_LLM_KEY_TMP"; return 3 2>/dev/null || exit 3; }
export FLEXCELL_LLM_API_KEY_FILE="$EVOBOT_LLM_KEY_TMP"
export FLEXCELL_LLM_BACKEND=deepseek-official
export FLEXCELL_LLM_RESPONSE_FORMAT=json_object
export FLEXCELL_LLM_THINKING=disabled
export FLEXCELL_LLM_MAX_TOKENS=512
export FLEXCELL_LLM_TIMEOUT_S=30
export FLEXCELL_LLM_BUDGET_FILE=/home/ros/.config/flexcell/deepseek_budget_20261001.json
