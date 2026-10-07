#!/usr/bin/env python3
"""Compute a statistical proposal only. Never generate states or run episodes."""
import hashlib
import json
from math import comb
from pathlib import Path


def exact_lower(successes,n,alpha):
    if type(n) is not int or n<=0 or type(successes) is not int or not 0<=successes<=n or not 0<alpha<1:raise ValueError('invalid binomial counts/alpha')
    if successes==0:return 0.
    low,high=0.,1.
    for _ in range(60):
        p=(low+high)/2
        tail=sum(comb(n,k)*p**k*(1-p)**(n-k) for k in range(successes,n+1))
        if tail<alpha:low=p
        else:high=p
    return (low+high)/2


def main():
    root=Path(__file__).resolve().parents[1];deployment=json.loads((root/'plan/deployment.json').read_text())
    n,cells,alpha,target=100,4,.05,.9;cell_alpha=alpha/cells
    minimum=next(k for k in range(n+1) if exact_lower(k,n,cell_alpha)>=target)
    profile={k:v for k,v in deployment.items() if k not in ['head','install','runtime_fingerprint']};fingerprints={}
    for arm in ['fsm','hybrid']:
        p=dict(profile,policy=arm);fingerprints[arm]=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
    draft=dict(schema_version=1,record_kind='DRAFT_PLAN',protocol_id='transferbench-qualification-v2-proposal',status='FROZEN_NOT_EXECUTABLE',sampling_authorized=False,
      implementation_freeze_candidate='f10be54fee2a4ae3dd1ef7479e155baee8fd4062',proposed_runtime_fingerprints=fingerprints,
      proposed_cells=[dict(axis=axis,arm=arm,n_logical_tasks=n) for axis in ['T1','T3'] for arm in ['fsm','hybrid']],
      proposed_statistic=dict(method='one-sided exact binomial Clopper-Pearson lower bound; Bonferroni across 4 fixed cell claims',family_alpha=alpha,alpha_per_cell=cell_alpha,target_lower_bound=target,min_successes_at_n100=minimum,lower_at_min=exact_lower(minimum,n,cell_alpha),lower_at_previous=exact_lower(minimum-1,n,cell_alpha),checks='one final fixed checkpoint only; no repeated looks or sample replenishment',assumption='independent Bernoulli outcomes at fixed cell settings; reset/time/transport prerequisites must be ratified'),
      sample_units=dict(target='logical complete task; T3 component episodes correlated, never separate successes',T1='paired independent heldout layouts; training/diagnostic states excluded',T3='post-adaptation reliability of frozen three-stage swap; does not establish unseen-composition generalization'),
      holdout=dict(status='NOT_GENERATED_NOT_EVALUATED',custodian='designate an independent keeper before evaluation; freeze artifacts without tuning from their outcomes',paired_arms_use_identical_inputs=True,source_history_manifest_required=True),
      ordering=dict(phase_order=['T1','T3'],arm_order='balanced paired AB/BA in blocks; freeze exact schedule before outcomes',old_task_regression='every 20 target tasks: S1 in T1 phase; S1 plus 3 frozen familiar T1 cases in T3 phase',planned_target_logical_tasks=400,planned_target_native_episodes=800,planned_regression_native_episodes=50),
      budget=dict(absolute_cny_cap=5,existing_budget_never_reset=True,additional_paid_stop_threshold_cny=.25,threshold_scope='cumulative new reservations since protocol registration, checked at boundaries; not per episode or an invoice',status='COST_ENVELOPE_NOT_RATIFIED; API reservations and elapsed/GPU costs still required'),
      failure_handling=dict(known_failures='retain in fixed registered denominator, no replacement; proceed only after confirmed idle/ownership and successful reset',unknown_signal_or_quarantine='stop all collection; incomplete/censored, never success from an earlier JSON',source_regression='failure stops that qualification phase; keep partial matrix'),
      AC90=dict(status='NOT_RUN',reason='historical adaptation labor and invoices incomplete; new prospective adaptation blocks needed for any complete cost claim'),
      prerequisites=['ratify this proposed count, primary cells and binomial assumptions','freeze independent inputs, exact arm schedule, success predicates, source/cali/model/profile identities','resolve or formally assess NET-001 and GRASP-B-001 while preserving failed baselines','confirm existing budget coverage without resets or invented bills','implement reviewed qualification ledger/runner separately; v1 recorder still refuses qualification'],
      large_tests_started=False,n_ge_50='FROZEN',qualification_executor='NOT_IMPLEMENTED_NOT_INVOKED',references=['https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm','https://www.itl.nist.gov/div898/handbook/prc/section4/prc463.htm'])
    with (root/'plan/qualification_v2_draft.json').open('x') as f:json.dump(draft,f,indent=2)
    print(json.dumps(dict(status=draft['status'],proposed_n_per_cell=n,min_successes=minimum,lower_at_min=draft['proposed_statistic']['lower_at_min'],no_sampling=True)))


if __name__=='__main__':main()
