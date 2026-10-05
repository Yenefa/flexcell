# Fast arm profile: Clef-flash Q8_0 on the RX 6800 via upstream llama-server
# (llama.cpp b11389 Vulkan, Windows side; reached from WSL over the NAT gateway).
# The Ollama Windows build is broken for Clef (ollama#18769 non-finite logit).
# Prompt v2 (FSM cycle semantics in instructions + enriched criteria) is part of
# the identity: the calibration file binds model + digest + prompt AST.
export FLEXCELL_JEV_ENDPOINT=http://172.17.144.1:11435/v1/systemone
export FLEXCELL_JEV_MODEL=clef-flash-q8_0
export FLEXCELL_JEV_MODEL_SHA256=8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9
export FLEXCELL_JEV_TIMEOUT_S=30
export FLEXCELL_JEV_CALIBRATION="$HOME/.config/flexcell/jev_calibration_clef_q8.json"
