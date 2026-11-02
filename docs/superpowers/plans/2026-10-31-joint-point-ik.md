# Joint attached-point IK Implementation Plan

**Goal:** Fix Joint/MTC PLACE point sampling and verify real local execution.

**Architecture:** A planning-only fixed TCP link and arm alias let upstream KDL
solve the actual attached point. The original arm group still plans EE retreat;
the existing sole executor consumes independently checked FK endpoints.

**Tech Stack:** ROS Jazzy, MoveIt 2.12.4, MTC 0.1.8, C++17, TinyXML2, pytest.

1. Add a frozen-scene service regression under `flexcell_mtc/test`. Generate
   real locked-model parameters; publish a measured GetPlanningScene response;
   call the existing PlanManipulation service. Record its current rejection.
2. Add `attached_point_model.hpp` for the fixed-link/group model and private
   loader. Modify only Joint PLACE selection in `mtc_planner.cpp`; preserve the
   original arm group for retreat. Add explicit TinyXML2 dependencies.
3. Require the service regression to pass with actual trajectory FK checks,
   plus zero-offset/original-model and configuration-boundary checks. Build
   and test first-party packages and run the existing static scan.
4. Capture planner request, exact scene reply and response in bounded diagnostic
   artifacts. Add a new one-task declaration linking the retained local failure;
   commit implementation/declaration before simulator dispatch.
5. On a verified clean source/install identity, run the five-case baseline and
   the new Joint declaration once each. Replay raw physical/contact gates,
   retain every failure, archive complete outputs, and update both handoffs.

Acceptance: numerical regression and independent endpoint FK pass; baseline
cases match expectations; Joint task plans, executes and passes the existing
measured release/final-position gates. Otherwise report the exact failed stage
and preserve it without replacement. No tolerance relaxation, new success-rate
claim, real hardware, default-backend admission or model batch unfreezing.
