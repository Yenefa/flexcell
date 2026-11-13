# ADR-005: Repository module and evidence boundaries

- Status: isolated first-phase implementation for review; no main merge or baseline promotion.
- Scope: issue #240 and the user's 2026-11-13 choice to organize version/build/evidence first.
- Base:83ffafe117208dc82d2e02320e3cd7204ec8b97c.

## Problem

Active ROS packages and archived source workspaces are discovered together.
The public Runtime CI already failed at duplicate package discovery before a
robot could run. Source identity, evidence identity and development branch names
also carry different meanings and need an explicit index.

## Decision

1. Keep the existing four ROS deployment packages under src/flexcell. Their
   behavior and interfaces are unchanged in this phase.
2. Declare module ownership and archive/build roots in config/repository_layout.json.
   Mark historical evidence/workspace parents with COLCON_IGNORE, preserving
   all existing snapshot contents and paths.
3. Record executed-source/evidence SHAs and qualification scope separately in
   config/version_baselines.json. Branch names are development locations, not
   accepted-capability identifiers.
4. Use explicit first-party source discovery in the ordinary CI build. Add a
   small independent boundary check with actual colcon discovery and negative
   regression cases; it starts no simulator and changes no acceptance rule.
5. Keep generated run output in ignored artifacts/ or outside the checkout.
   Archive reviewed evidence in separate commits with provenance and hashes.

## Consequences and limits

Old workspaces remain available for isolated replay, while root builds find
only current packages. New source packages require an explicit registry update.
This phase neither decomposes TaskFsmServer nor moves historical tools/data;
later source extractions need compatibility and module-specific verification.
ADR-002's decision/execution/verification authority and ADR-004's simulation
contracts are unchanged. No new physical capability is claimed.
