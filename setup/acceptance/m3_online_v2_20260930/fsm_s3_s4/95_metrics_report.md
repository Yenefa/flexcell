# FlexCell benchmark metrics report

generated from the replay store; every number regenerates - no hand-written PASS lines.

## Cell S3 @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=unfingerprinted (n=1)

| metric | value |
| --- | --- |
| success rate (metric 1) | 1/1 = 1.00, Wilson95 [0.21, 1.00] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 10, 'p50_ms': 0.030025, 'p95_ms': 0.080854, 'p99_ms': 0.08472, 'max_ms': 0.085686}
| invalid decisions (metric 6) | {'evaluated': 10, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 1/1 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)
| actual decision sources | {'fsm': 10} |

- recovery_b_demo_v1_recovery_b_demo_v1-69d7d17f.json: outcome=0 steps=10 replayed=10

## Cell S4 @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=unfingerprinted (n=1)

| metric | value |
| --- | --- |
| success rate (metric 1) | 0/1 = 0.00, Wilson95 [0.00, 0.79] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 4, 'p50_ms': 0.02342, 'p95_ms': 0.033566, 'p99_ms': 0.034789, 'max_ms': 0.035095}
| invalid decisions (metric 6) | {'evaluated': 4, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 1/1 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)
| actual decision sources | {'fsm': 4} |

- pick_place_v1_pick_place_v1-16d5aa87.json: outcome=1 steps=4 replayed=4

REPORT: PASS (2 episodes, 0 replay-dirty)
