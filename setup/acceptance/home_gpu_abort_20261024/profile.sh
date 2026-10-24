# Fast-arm profile -- Clef-flash Q8_0 on the HOME GPU over Tailscale.
# Identity binding table: docs/MODEL_IDENTITY.md (2026-10-05).
# Verified live from this laptop 2026-10-06: /v1/models served
# Clef-Flash-Q8_0.gguf; real typed /v1/systemone calls returned
# choice=PICK prob=0.860 tokens=503 at 1.5-2.1 s.
#
# Only the ENDPOINT differs from the desktop deployment. Model name, weight
# sha256 and the prompt digest are endpoint-independent and copied verbatim.
export FLEXCELL_JEV_ENDPOINT=http://100.87.190.44:11435/v1/systemone
export FLEXCELL_JEV_MODEL=clef-flash-q8_0
export FLEXCELL_JEV_MODEL_SHA256=8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9

# Cross-WAN timeout. Measured 1.5-2.1 s per decision; the code default is 2.0 s,
# which would time out on inference jitter and SILENTLY escalate to DeepSeek
# (30-100x cost, still-green report). Keep generous.
export FLEXCELL_JEV_TIMEOUT_S=45

# jev_backends._http_transport only bypasses the proxy for localhost/127.0.0.1;
# a tailnet host goes through urllib.request.urlopen and therefore INHERITS the
# campus proxy at 127.0.0.1:7890, which answers 502 for tailnet IPs. Python's
# no_proxy does not understand CIDR, so the literal IP is required here. Without
# this the fast arm fails with an opaque 502.
export no_proxy="${no_proxy:+${no_proxy},}100.87.190.44"
export NO_PROXY="$no_proxy"

# Locally generated, identity-checked FSM-action calibration (2026-10-06).
export FLEXCELL_JEV_CALIBRATION=/home/ros/.config/flexcell/jev_calibration_clef_q8_20261005.json

# School DERP relay: explicit startup probe deadline, bounded by inference timeout.
export FLEXCELL_JEV_HEALTH_TIMEOUT_S=10

# Per-run SSH forwarding over the verified Tailscale connection.
export FLEXCELL_JEV_ENDPOINT=http://127.0.0.1:21435/v1/systemone
