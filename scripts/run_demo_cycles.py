#!/usr/bin/env python3
"""Run the continuous demo (RunDemo) N times against a live stack.

RunDemo is the continuous scene: OBSERVE -> PICK A -> PLACE A -> VERIFY A ->
OBSERVE -> PICK B -> PLACE B -> VERIFY B. This client sends one goal per cycle,
saves each result under `OUT/cycle-<n>/result.json`, and optionally resets the
scene between cycles so the next cycle starts from the canonical spawns.

Read-only with respect to control: it only sends the documented task goal.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from flexcell_interfaces.action import RunDemo


class DemoClient(Node):
    def __init__(self):
        super().__init__('demo_cycles')
        self.client = ActionClient(self, RunDemo, '/run_demo')


def wait_future(node, future, timeout_s):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not future.done():
        rclpy.spin_once(node, timeout_sec=0.1)
    return future.done()


def reset_scene(repo, timeout_s=120):
    proc = subprocess.run(
        [sys.executable, str(repo / 'setup/flexcell_admin.py'), 'reset'],
        cwd=str(repo), capture_output=True, text=True, timeout=timeout_s)
    ok = proc.returncode == 0 and '"ok": true' in (proc.stdout or '')
    return ok, (proc.stdout or proc.stderr or '')[-400:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--cycles', type=int, default=2)
    parser.add_argument('--timeout-s', type=float, default=300.0)
    parser.add_argument('--repo', type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--no-reset', action='store_true')
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = DemoClient()
    results = []
    exit_code = 0
    try:
        if not node.client.wait_for_server(timeout_sec=30.0):
            print(json.dumps({'error': 'no /run_demo server'}))
            return 2

        for index in range(args.cycles):
            goal = RunDemo.Goal()
            goal.scenario_id = 'demo-cycle-%d' % (index + 1)
            send = node.client.send_goal_async(goal)
            if not wait_future(node, send, 30.0):
                results.append(dict(cycle=index + 1, outcome='SEND_TIMEOUT'))
                exit_code = 2
                break
            handle = send.result()
            if handle is None or not handle.accepted:
                results.append(dict(cycle=index + 1, outcome='REJECTED'))
                exit_code = 1
                break

            result_future = handle.get_result_async()
            if not wait_future(node, result_future, args.timeout_s):
                results.append(dict(cycle=index + 1, outcome='TIMEOUT'))
                exit_code = 1
                break

            result = result_future.result().result
            record = dict(
                cycle=index + 1,
                outcome=int(result.outcome),
                succeeded=result.outcome == RunDemo.Result.OUTCOME_SUCCEEDED,
                error_code=int(result.error_code),
                object_a_at_zone=bool(result.object_a_at_zone),
                object_b_at_zone=bool(result.object_b_at_zone),
                zone_a_error_m=float(result.zone_a_error_m),
                zone_b_error_m=float(result.zone_b_error_m),
                duration_s=float(result.duration_s),
                evidence_id=result.evidence_id,
                fsm_trace=list(result.fsm_trace),
                detail=result.detail,
            )
            cycle_dir = args.out / ('cycle-%d' % (index + 1))
            cycle_dir.mkdir(parents=True, exist_ok=True)
            (cycle_dir / 'result.json').write_text(json.dumps(record, indent=2))
            results.append(record)
            print('CYCLE %d outcome=%s errors=(%.4f, %.4f) duration=%.1fs' % (
                index + 1, record['outcome'], record['zone_a_error_m'],
                record['zone_b_error_m'], record['duration_s']))

            if not record['succeeded']:
                exit_code = 1
                break
            if index + 1 < args.cycles and not args.no_reset:
                ok, detail = reset_scene(args.repo)
                print('RESET', 'ok' if ok else 'failed', detail[:120])
                if not ok:
                    exit_code = 1
                    break
    finally:
        node.destroy_node()
        rclpy.shutdown()

    summary = dict(
        cycles=len(results),
        passed=sum(1 for r in results if r.get('succeeded')),
        results=results,
    )
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
