"""Structured failure diagnosis for the B2 arm (derived from the verdict)."""
import json
from pathlib import Path

LIMITS = {"max_reach_m": 0.30, "max_overshoot_mm": 5,
          "allowed_profiles": ["standard", "slow"]}


def derive(verdict_path):
    path = Path(verdict_path)
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("passed"):
        return {"passed": True, "cause": None, "suggested_action": None}
    code = doc.get("error_code")
    if code == 71:
        cause = "reachability"
        action = "choose a destination whose hypot(x, y) is below max_reach_m"
    elif code == 72:
        cause = "overshoot"
        action = "use a profile in allowed_profiles or reduce speed"
    elif code == 60:
        cause = "contract"
        action = "satisfy the declared plan constraints"
    else:
        cause = "unknown"
        action = "inspect telemetry and the failing stage"
    return {"passed": False, "error_code": code, "detail": doc.get("detail"),
            "failed_stage": doc.get("failed_stage"), "limits": LIMITS,
            "cause": cause, "suggested_action": action}
