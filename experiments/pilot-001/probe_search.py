import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot.toolbox import ToolBox
ws = Path(tempfile.mkdtemp())
(ws / "a.py").write_text("x = 1\nzone_of = {}\ny = zone_of[1]\n")
tb = ToolBox("W5A", ["search_code"], ws, None, ws / "v.json", None)
print("FILE  :", repr(tb.search_code("zone", "a.py")))
print("DIR   :", repr(tb.search_code("zone", ".")))
print("MISS  :", repr(tb.search_code("nope", "a.py")))
