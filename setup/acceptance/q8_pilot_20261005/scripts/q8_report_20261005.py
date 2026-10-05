"""Read-only episode-level accounting; smoke and baseline remain separate."""
import json
from pathlib import Path
import re
import statistics
import sys

from flexcell_skills.contracts.metrics import wilson

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_pilot_20261005')
groups = []
for log in sorted(root.glob('*.log')):
    match = re.match(r'(smoke|baseline)_([0-9.]+)_(\d+)_', log.name)
    if not match:
        continue
    stage, tau, planned = match.groups()
    text = log.read_text()
    paths = re.findall(r'batch summary: (.+)', text)
    if not paths:
        continue
    batch = Path(paths[-1])
    rows = [json.loads(line) for line in batch.read_text().splitlines() if line]
    outcomes, episodes = [], []
    for row in rows:
        record = json.loads(Path(row['episode']).read_text()) if row.get('episode') else {}
        audit = row.get('routing_audit') or {}
        cost, cost_calls = 0., 0
        for step in record.get('steps', []):
            trace = step.get('policy_output', {}).get('policy_trace') or {}
            for proposal in trace.get('proposals', []):
                if proposal.get('policy') == 'llm':
                    payment = (proposal.get('policy_trace') or {}).get('cost') or {}
                    if payment.get('upper_bound_cny') is not None:
                        cost += payment['upper_bound_cny']
                        cost_calls += 1
        count = audit.get('model_decisions', 0)
        episodes.append(dict(run_id=record.get('run_id'), run=row['run'], outcome=row['outcome'],
            routing_ok=audit.get('ok'), harness_error=row.get('harness_error'),
            bootstrap=audit.get('bootstrap', 0), fast=audit.get('fast_selected', 0),
            slow=audit.get('slow_selected', 0), model_decisions=count,
            escalation_fraction=audit.get('slow_selected', 0)/count if count else None,
            duration_s=record.get('final_state', {}).get('duration_s'),
            error_code=record.get('final_state', {}).get('error_code'),
            safety=record.get('final_state', {}).get('safety'),
            paid_upper_bound_cny=round(cost, 6), paid_settled_calls=cost_calls))
        if row['outcome'] != 'HARNESS_ERROR':
            outcomes.append(row['outcome'])
    success = outcomes.count('SUCCEEDED')
    rates = [e['escalation_fraction'] for e in episodes if e['escalation_fraction'] is not None
             and e['outcome'] != 'HARNESS_ERROR' and e['routing_ok'] is True]
    audited = [e for e in episodes if e['routing_ok'] is not None]
    groups.append(dict(stage=stage, threshold=float(tau), planned_n=int(planned),
        completed_n=len(rows), graded_n=len(outcomes), successes=success,
        harness_errors=len(rows)-len(outcomes), success_ci95=wilson(success, len(outcomes)),
        audited_n=len(audited), unaudited_n=len(rows)-len(audited),
        all_routing_ok=bool(audited) and all(e['routing_ok'] is True for e in audited),
        success_fraction_per_attempt=success/len(rows) if rows else None,
        episode_mean_escalation=statistics.mean(rates) if rates else None,
        fast=sum(e['fast'] for e in episodes), slow=sum(e['slow'] for e in episodes),
        paid_upper_bound_cny=round(sum(e['paid_upper_bound_cny'] for e in episodes), 6),
        batch=str(batch), log=str(log), episodes=episodes))
result = dict(unit='episode', groups=groups, model_replay='NOT_RUN',
              superiority_over_FSM='UNKNOWN', local_compute_cost='UNKNOWN')
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({**result, 'groups': [{k: v for k, v in g.items() if k != 'episodes'} for g in groups]}, indent=2))
