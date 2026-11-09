# W5-E2e - second object is not registered

The two-object task stops at the second object: the safety gate rejects it as
target_not_available. The first object and the normal/regrasp tasks work.

The defect is a missing entry in config/week1.yaml (observe_server
tracked_objects). Do not inspect gate/ or other files. Run the target scenario
once with run_execution, then edit config/week1.yaml so both objects are
tracked and all three gates pass.
