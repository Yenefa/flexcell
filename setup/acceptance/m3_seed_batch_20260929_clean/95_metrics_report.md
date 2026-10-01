# FlexCell benchmark metrics report

generated from the replay store; every number regenerates - no hand-written PASS lines.

## Cell S1 (n=20)

| metric | value |
| --- | --- |
| success rate (metric 1) | 18/20 = 0.90, Wilson95 [0.70, 0.97]
| decision latency (metric 3) | NOT_RUN (legacy integer-ms truncation; recorded decisions n=176; unusable for latency claims) |
| invalid decisions (metric 6) | {'evaluated': 176, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 20/20 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)

- week1_demo_v1_week1_demo_v1-17fb0b78.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-99713ca1.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-03a49a7e.json: outcome=0 steps=10 replayed=10
- week1_demo_v1_week1_demo_v1-3b2073ae.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-8e8d7732.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-df0f62f1.json: outcome=0 steps=10 replayed=10
- week1_demo_v1_week1_demo_v1-81caab18.json: outcome=0 steps=10 replayed=10
- week1_demo_v1_week1_demo_v1-b7bd00bf.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-7638da4e.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-ae7ad184.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-b9c1c6e8.json: outcome=1 steps=9 replayed=9
- week1_demo_v1_week1_demo_v1-331379e9.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-d64185b7.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-34a88434.json: outcome=0 steps=10 replayed=10
- week1_demo_v1_week1_demo_v1-036aca81.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-5e335544.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-c1697e8e.json: outcome=0 steps=8 replayed=8
- week1_demo_v1_week1_demo_v1-a2dda292.json: outcome=0 steps=10 replayed=10
- week1_demo_v1_week1_demo_v1-56dfbc1d.json: outcome=1 steps=11 replayed=11
- week1_demo_v1_week1_demo_v1-77e6e0cf.json: outcome=0 steps=10 replayed=10

## Cell S2 (n=20)

| metric | value |
| --- | --- |
| success rate (metric 1) | 8/20 = 0.40, Wilson95 [0.22, 0.61]
| decision latency (metric 3) | NOT_RUN (legacy integer-ms truncation; recorded decisions n=180; unusable for latency claims) |
| invalid decisions (metric 6) | {'evaluated': 180, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 20/20 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)

- recovery_demo_v1_recovery_demo_v1-53f0e556.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-7d342bc8.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-b2116c2a.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-c73f05e5.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-6d4bf5bb.json: outcome=1 steps=11 replayed=11
- recovery_demo_v1_recovery_demo_v1-81ed8fb5.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-36167df4.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-b1c8f281.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-b5b108d3.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-84664ed5.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-3d8e4def.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-59f06be4.json: outcome=1 steps=11 replayed=11
- recovery_demo_v1_recovery_demo_v1-8d9c48c4.json: outcome=1 steps=11 replayed=11
- recovery_demo_v1_recovery_demo_v1-8f7231ca.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-d377fdaf.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-41aa9b33.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-2ba481ae.json: outcome=1 steps=5 replayed=5
- recovery_demo_v1_recovery_demo_v1-e3469bcc.json: outcome=0 steps=12 replayed=12
- recovery_demo_v1_recovery_demo_v1-e1abcfdf.json: outcome=1 steps=11 replayed=11
- recovery_demo_v1_recovery_demo_v1-e81a10bf.json: outcome=0 steps=12 replayed=12

## Cell S5 (n=20)

| metric | value |
| --- | --- |
| success rate (metric 1) | 1/20 = 0.05, Wilson95 [0.01, 0.24]
| decision latency (metric 3) | NOT_RUN (legacy integer-ms truncation; recorded decisions n=103; unusable for latency claims) |
| invalid decisions (metric 6) | {'evaluated': 103, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 20/20 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)

- exhaust_demo_v1_exhaust_demo_v1-fed26d74.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-6096cbb9.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-c10bd921.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-8fa06922.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-1fd28d5a.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-e456fb9a.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-2659b6a3.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-acedea60.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-9b329e20.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-843c2121.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-3fb6af86.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-c359f99b.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-5b273747.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-197df378.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-c3f66428.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-6f5ce309.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-e86dad49.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-77ed3de2.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-3c06cfb3.json: outcome=1 steps=5 replayed=5
- exhaust_demo_v1_exhaust_demo_v1-dabdd93d.json: outcome=0 steps=8 replayed=8

## Cell S7 (n=10)

| metric | value |
| --- | --- |
| success rate (metric 1) | 6/10 = 0.60, Wilson95 [0.31, 0.83] ⚠ n<20 (CI wide; prefer n≥20)
| decision latency (metric 3) | NOT_RUN (legacy integer-ms truncation; recorded decisions n=80; unusable for latency claims) |
| invalid decisions (metric 6) | {'evaluated': 80, 'rejected': 0, 'invalid_per_1000': 0.0}
| replay integrity | 10/10 episodes clean (0 diverged steps total; 0 safety-rejection records excluded)

- s7_perturb_v1_s7_perturb_v1-c4d5ce9b.json: outcome=1 steps=9 replayed=9
- s7_perturb_v1_s7_perturb_v1-fb12d4b5.json: outcome=1 steps=5 replayed=5
- s7_perturb_v1_s7_perturb_v1-2351febf.json: outcome=0 steps=10 replayed=10
- s7_perturb_v1_s7_perturb_v1-bdfaecab.json: outcome=0 steps=10 replayed=10
- s7_perturb_v1_s7_perturb_v1-4bd21a92.json: outcome=0 steps=8 replayed=8
- s7_perturb_v1_s7_perturb_v1-54ec5f38.json: outcome=0 steps=8 replayed=8
- s7_perturb_v1_s7_perturb_v1-eb8d6476.json: outcome=0 steps=8 replayed=8
- s7_perturb_v1_s7_perturb_v1-7956c53b.json: outcome=1 steps=9 replayed=9
- s7_perturb_v1_s7_perturb_v1-10816bd8.json: outcome=0 steps=8 replayed=8
- s7_perturb_v1_s7_perturb_v1-d53b624f.json: outcome=1 steps=5 replayed=5

REPORT: PASS (70 episodes, 0 replay-dirty)
