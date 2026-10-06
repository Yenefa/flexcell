#!/usr/bin/env python3
"""Finish the single already registered S1 task after read-only audit repair."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

WS=Path('/home/ros/agentic_workcell_ws');sys.path.insert(0,str(WS/'setup/transferbench'))
import t1_pilot as base
import t3_swap_pilot as previous
ROOT=Path(__file__).resolve().parents[1];COST=base.COST


def main():
    COST.read_ledger(ROOT/'cost.jsonl')
    manifest=previous.load(ROOT/'plan/manifest.json');deployment=previous.load(ROOT/'plan/deployment.json')
    for rel,sha in dict(manifest['source_sha256'],**manifest['helpers_sha256']).items():
        if rel!='setup/127_composite_audit.py':COST.require(base.sha(WS/rel)==sha,'registered runtime/source changed')
    base.verify_deployment(deployment)
    corrected=previous.load(ROOT/'validation/audit_attempt02.json');COST.require(corrected['ok'] and len(corrected['component_run_ids'])==3,'corrected read-only audit must pass')
    result=previous.load(ROOT/'execution/composite/client_result.json');COST.require(result['action_status']==4 and result['outcome_val']==0,'parent terminal must confirm success')
    old=previous.load(ROOT/'plan/budget.json');COST.require(base.new_call_upper_bound(old,base.budget_snapshot())<250000,'registered paid stop threshold')
    COST.require(not (ROOT/'execution/S1').exists() and not (ROOT/'execution/source-preparation').exists(),'source task already attempted')
    amendment=dict(record_kind='CONTINUATION_OF_REGISTERED_SOURCE_TASK',new_composite_trials=0,new_source_trials=1,
                   registered_source_limit=manifest['source_regressions'],runtime_fingerprint=manifest['runtime_fingerprint'],
                   original_audit_failure_retained=True,correction='EpisodeRecorder nine-decimal representation only; unrounded success predicates unchanged',
                   original_auditor_sha256=manifest['source_sha256']['setup/127_composite_audit.py'],corrected_auditor_sha256=base.sha(WS/'setup/127_composite_audit.py'),
                   continuation_sha256=base.sha(Path(__file__)),no_resampling=True)
    base.write(ROOT/'plan/continuation_source_only.json',amendment)
    directory=ROOT/'execution/source-preparation';directory.mkdir()
    start=time.perf_counter_ns();error=previous.prepare(directory,'hybrid','S1')
    if error:base.write(directory/'failure.json',dict(error=error));raise ValueError(error)
    source=previous.native(ROOT,'hybrid',ROOT/'execution/S1',deployment,'S1-source-regression')
    COST.require(not source['harness_error'],'source harness failure; retain without replacement')
    base.write(ROOT/'execution_summary.json',dict(record_kind='ACTUAL_COMPOSITE_API_PILOT',composite_result=result,source_result=source,
               composite_native_components=3,source_native_episodes=1,logical_composite_attempts=1,source_regression_attempts=1,
               original_pilot_exit_code=1,original_audit_failure='RETAINED',final_audit='POSTHOC_SERIALIZATION_CORRECTION',
               source_continuation_elapsed_minutes=(time.perf_counter_ns()-start)/60e9,total_elapsed_minutes=None,no_resampling=True,n_ge_50='FROZEN'))
    print(json.dumps(dict(source=source['outcome'],no_composite_resampling=True)),flush=True)


if __name__=='__main__':main()
