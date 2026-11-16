"""A wrong --families value must stop the run, not quietly run something else.

On 2026-11-17 a pilot passed --families DEF-F1-REG, which is an instance id. The
runner took it as a family, the seed fell back to 5000+, the slot ids carried the
instance name, and the gate answered for a different family. Three slots and
63,460 tokens went by before anyone looked at the gate code.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_an_instance_id_is_refused_as_a_family():
    proc = subprocess.run(
        [sys.executable, str(HERE / "run_matrix_real.py"), "--source", "instances",
         "--families", "DEF-F1-REG", "--budget", "1", "--limit", "1"],
        capture_output=True, text=True, timeout=120)
    told = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "a wrong family name was accepted"
    assert "unknown family DEF-F1-REG" in told
    assert "F1_OBJECT_REGISTRATION" in told, "the message must name a valid family"


def test_the_known_families_are_the_protocol_ones():
    sys.path.insert(0, str(HERE))
    import run_matrix_real as R
    assert set(R.FAMILIES) == {"F1_OBJECT_REGISTRATION", "F2_GOAL_MAPPING"}
