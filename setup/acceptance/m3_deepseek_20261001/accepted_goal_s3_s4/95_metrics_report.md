# FlexCell benchmark metrics report

generated from the replay store; every number regenerates - no hand-written PASS lines.

## Cell S3/llm @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=eff09a70e6331d024a7447b7443a27c9d696428eb1f0390ed1123919ee3a28e3 (n=1)

| metric | value |
| --- | --- |
| success rate (metric 1) | 1/1 = 1.00, Wilson95 [0.21, 1.00] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 10, 'p50_ms': 778.683956, 'p95_ms': 1044.821883, 'p99_ms': 1091.969787, 'max_ms': 1103.756763}
| invalid decisions (metric 6) | {'evaluated': 10, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 0/0 replayed episodes clean (0 diverged steps total; 0 safety-rejection records excluded)
| model replay | NOT_RUN (1 episodes; pinned backend required) |
| actual decision sources | {'fsm': 1, 'llm': 9} |

- recovery_b_demo_v1_recovery_b_demo_v1-b9970416.json: outcome=0 steps=10 replayed=0 **REPLAY NOT_RUN**

## Cell S4/llm @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=eff09a70e6331d024a7447b7443a27c9d696428eb1f0390ed1123919ee3a28e3 (n=1)

| metric | value |
| --- | --- |
| success rate (metric 1) | 0/1 = 0.00, Wilson95 [0.00, 0.79] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 4, 'p50_ms': 762.736727, 'p95_ms': 850.798853, 'p99_ms': 851.786345, 'max_ms': 852.033218}
| invalid decisions (metric 6) | {'evaluated': 4, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 0/0 replayed episodes clean (0 diverged steps total; 0 safety-rejection records excluded)
| model replay | NOT_RUN (1 episodes; pinned backend required) |
| actual decision sources | {'fsm': 1, 'llm': 3} |

- pick_place_v1_pick_place_v1-07c23d11.json: outcome=1 steps=4 replayed=0 **REPLAY NOT_RUN**

REPORT: INCOMPLETE (2 episodes, 0 replay-dirty)
