# Rejected joint PLACE, CI run 40953343176

The complete original 35-file artifact is retained without modification.
Its SHA-256 is `a13c191acce9b3774c30a7c094bca71d4262a78b86ad8efdd1bfd82f08ea0d8c`.
The installed CI source identity is the PR merge ref
`01f7fc0a3ac9fb7e1f556fe4b64b1e12e35042b6`, for PR #75 head
`4494adce4cfe757e643a98bf2842805e1c08e356` before the attached-object planning
correction. The single declared task remains STOPPED.
PICK succeeded first attempt, all three PLACE motions and release succeeded,
but the settled box missed by 112.617 mm (unchanged tolerance 60 mm).

Run `python3 setup/acceptance/joint_place_failure_20261030/verify.py` to independently
retain that rejection, check motion identities, and recompute the stable full
relative translation from the complete 2 ms attachment interval. Stable joint
attachment does not make the old world-vertical EE offset a valid object goal.
This failure is separate from GRASP-B-001, whose exact mechanism remains UNKNOWN.
