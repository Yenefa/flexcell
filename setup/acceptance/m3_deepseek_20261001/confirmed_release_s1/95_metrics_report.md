# FlexCell benchmark metrics report

generated from the replay store; every number regenerates - no hand-written PASS lines.

## Cell S1/llm @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=e909d3451b4d0d496df1b5711d5c2de8b306f38d02ddf0774afe995f9710217c (n=5)

| metric | value |
| --- | --- |
| success rate (metric 1) | 3/5 = 0.60, Wilson95 [0.23, 0.88] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 40, 'p50_ms': 811.847775, 'p95_ms': 1274.859868, 'p99_ms': 1596.923543, 'max_ms': 1783.778357}
| invalid decisions (metric 6) | {'evaluated': 40, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 0/0 replayed episodes clean (0 diverged steps total; 0 safety-rejection records excluded)
| model replay | NOT_RUN (5 episodes; pinned backend required) |
| actual decision sources | {'fsm': 5, 'llm': 35} |

- week1_demo_v1_week1_demo_v1-8693a880.json: outcome=0 steps=8 replayed=0 **REPLAY NOT_RUN**
- week1_demo_v1_week1_demo_v1-e00aee26.json: outcome=0 steps=10 replayed=0 **REPLAY NOT_RUN**
- week1_demo_v1_week1_demo_v1-18134b4f.json: outcome=0 steps=8 replayed=0 **REPLAY NOT_RUN**
- week1_demo_v1_week1_demo_v1-d3edbb7e.json: outcome=1 steps=9 replayed=0 **REPLAY NOT_RUN**
- week1_demo_v1_week1_demo_v1-b3d0c0f8.json: outcome=1 steps=5 replayed=0 **REPLAY NOT_RUN**

REPORT: INCOMPLETE (5 episodes, 0 replay-dirty)
