"""FlexCell skill contracts (M2.2-1): the unified failure-language layer.

One failure language for every policy consumer: skills keep their legacy
per-action error_code fields untouched (backward compat), and this package
is the single mapping point to canonical codes + status.

- error_codes.py: canonical taxonomy, legacy->canonical mapping (fail-closed),
  status derivation.
- skill_result.py: the single derivation point servers call from finish(),
  plus the decision-log shaping for previous_skill_result.

Pure python, no ROS imports - offline testable by construction.
"""
