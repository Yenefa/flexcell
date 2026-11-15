"""Compatibility import for the former experiment-owned placement helper."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime.planner.spread_destinations import SPREAD_STEP_M, spread

__all__ = ["SPREAD_STEP_M", "spread"]
