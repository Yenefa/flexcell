# W5-E3 - the two-object demo mis-places the second object

The workcell configuration is correct. The two-object demo fails: the first
object is picked, placed and verified, then the second object is also picked
and placed - but the final verification reports the second object about 0.3 m
away from its zone. The normal task and the regrasp task still pass.

The defect is in the skill implementation under src/flexcell_skills. You may
read and edit files there; every run rebuilds the package before launching
Gazebo. gate/ is read-only and does not need to be inspected.

Run the target scenario, find the implementation defect, fix it, and make all
three gates (dual_object, normal, regrasp) pass.
