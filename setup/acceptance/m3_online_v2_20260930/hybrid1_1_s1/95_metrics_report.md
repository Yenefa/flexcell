# FlexCell benchmark metrics report

generated from the replay store; every number regenerates - no hand-written PASS lines.

## Cell S1/hybrid @ flexcell-benchmark-v2:e37cebe00ab6d6e711cc16332079eb502127d91aac3cb00d06edf70e66c4d51a / runtime=14f28cc2d7dfea360877fac5f656a052fc737750913d9379e9b74a42e98d82ab (n=2)

| metric | value |
| --- | --- |
| success rate (metric 1) | 0/2 = 0.00, Wilson95 [0.00, 0.66] ⚠ n<50 (CI wide; prefer n≥50)
| decision latency (metric 3) | {'n': 10, 'p50_ms': 2127.515553, 'p95_ms': 4065.016738, 'p99_ms': 4644.838211, 'max_ms': 4789.793579}
| invalid decisions (metric 6) | {'evaluated': 10, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 0/2 episodes clean (2 diverged steps total; 0 safety-rejection records excluded)
| model replay | NOT_RUN (2 episodes; pinned backend required) |
| actual decision sources | {'fsm': 5, 'jev': 2, 'llm': 3} |

- week1_demo_v1_week1_demo_v1-d14db4f9.json: outcome=1 steps=5 replayed=0 **REPLAY NOT_RUN**
- week1_demo_v1_week1_demo_v1-3ef92beb.json: outcome=1 steps=5 replayed=0 **REPLAY NOT_RUN**

REPORT: INCOMPLETE (2 episodes, 0 replay-dirty)
