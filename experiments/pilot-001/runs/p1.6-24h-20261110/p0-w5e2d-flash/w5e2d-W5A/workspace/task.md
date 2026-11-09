# W5-E2d - repair the workcell configuration (explicit action)

The two-object task fails: zone_2 is out of reach.

Do not inspect gate/ or other files. First run the target scenario once with
run_execution. Then edit config/week1.yaml and set zone_2_x to a reachable
value (0.20-0.25). The gate checks the two-object task and the normal and
regrasp regressions; you do not need to run them yourself.
