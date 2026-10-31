# Legacy carry-backend parity — local WSL, 2026-10-31

One manifest (`infra/legacy-parity-window.json`), five declared tasks, executed once
per carry backend on the local WSL stack. Same tasks, same skill backend (MTC), same
12 mm placement tolerance, no replacement trials.

| backend | window | cases | max placement error |
| --- | --- | --- | --- |
| `teleport` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.171 mm |
| `velocity_servo` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.230 mm |
| `detachable_joint` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 2.254 mm |

The `budget_exhaustion` case is the declared negative in all three windows: it must
fail with `ERR_RECOVERY_EXHAUSTED`, and it does.

**Reading this honestly:** the joint backend passes the same criterion, but its
placement error is about ten times the legacy backends' (2.20–2.25 mm vs
0.017–0.230 mm). Parity here means "same tasks, same threshold, same verdict" — it
does **not** mean the backends are equivalent in accuracy, and that gap is a reason
to keep the joint backend experimental, not to promote it.

Files: `parity-report.json` (machine comparison), `<backend>/window.json` (each
window as produced, with its own declaration and runtime fingerprint).

Replay:

```bash
PYTHONPATH=scripts python3 scripts/parity_report.py \
  setup/acceptance/legacy_parity_20261031/*/window.json
```

Scope: one bounded window per backend. This is not a success rate, not a reliability
estimate, and not a D3 admission decision.
