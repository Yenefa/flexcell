import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot import w5s
env = {"PILOT_P14_SRC": "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp",
       "PILOT_P14_REPO": "/home/ros/flexcell-p14",
       "PILOT_P14_WS": "/home/ros/flexcell-p14-ws",
       "PILOT_HOME": os.path.dirname(os.path.abspath(__file__))}
os.environ.update(env)
ex = w5s.W5SourceExecution("/tmp/levelb-w5a-3/w5s-W5A/workspace", env)
try:
    print("RESULT:", ex.run_execution())
except Exception:
    traceback.print_exc()
