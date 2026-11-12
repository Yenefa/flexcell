# V7: explicit pre-robot telemetry boundary

V6 E1 retained as pre-dispatch FAILED, zero actuator goals. E2/E3 are NOT_RUN;
that batch is incomplete. The actual raw prefix is unambiguous: ContactTrace
begins at5ms; PhysicsTrace first has a robot parent pose at10ms. The first5ms
contact record cannot have a matching robot pose because the robot link did not
yet exist. V6 incorrectly treated this bootstrap prefix as a lost execution step.

V7 counts and reports only contact rows strictly before the first-ever physics
row as pre-robot prefix. Keep these raw rows. They never count as observed arm
contact. Later unmatched/expired rows still refuse, exact-step joins remain
required, and no time/contact/geometry/acceptance threshold is relaxed.

Before more motion, incrementally replay all five candidate raw recordings,
including two-step-ahead contact reads and bounded paused/offset clocks. Keep
both archived V6 and current V7 replay results. This is a read-only acquisition
test, not a physical rerun or real-time scheduling proof. Positive bootstrap and
negative later-missing-step cases also have unit coverage.

Freeze V7 before the following declared validation sequence:

- F1/domain225: one physical development validation, two30mm requests maximum.
- Only if F1 has two bounded strokes, two ready/geometry-valid completed-return
  receipts, true registered native contact and full frozen9/9 PASS, execute the
  two fixed confirmations F2/domain226 then F3/domain227, same frozen V7.

Same image/exposed seed2000/world/task/demo_veryslow/60s executor deadlines and
40-goal cap as D1. D1 is an earlier descriptive comparator, not a randomized
superiority trial. F1 is the development validation; keep it separate from the
two confirmation slots. Keep failures and never replace a slot. No tuning
within the confirmation pair; actual physical guard violation stops for
diagnosis. All earlier failures and incomplete batches remain in the report.

Report precise bounded stroke verdict, return/arm readiness, live receipt
acceptance/expiry, native patch/TCP/pitch evidence and frozen full-task grade
separately. These three runs, if earned/completed, concern one exposed instance;
they do not prove unseen transfer, statistical reliability, Runtime Agent
integration, ordinary release consistency, baseline promotion or L4.
