# Signed support force — local contact probe, 2026-10-31

One declared standalone contact spike (`infra/contact-probe.json`,
`contact_probe.py`), executed once on the local WSL stack. No arm, no carry, no
robot task: the fixture only lets a box rest on the ground so the support force has
a known direction and a known magnitude.

- probe status: `CONTACT_PIPELINE_PASS`
- signed evidence: `SIGNED_FORCE_PASS`
- settled samples: 501 (1.0–2.0 s, 2 ms steps)
- summed force on the target: z ∈ [0.48999999999, 0.49000000035] N (= m·g, m = 50 g)
- direction cosine against the declared +z: 1.0
- maximum lateral component: 3.6e-16 N (limit 1e-6 N)
- every one of the 4 contact points pushes the body up; no point acts downward
- contact partner: `ground_plane::link::col`, i.e. the declared partner only

Files:

- `result.json` — probe result, including `signed_force_evidence`
- `declaration.json` — the fixture as declared before execution (world, mass,
  settle window, frozen signed-force block)
- `contact_steps_settled.jsonl` — the 501 settled rows the gate consumes (the raw
  file had 1,200 rows; its SHA-256 is in `result.json` as `raw_sha256`)
- `world.sdf` — the exact probe world

Replay (from the repository root):

```bash
PYTHONPATH=scripts python3 -c "
import json; from signed_force_gate import verify_file
spec = json.load(open('setup/acceptance/signed_force_20261031/declaration.json'))
print(verify_file('setup/acceptance/signed_force_20261031/contact_steps_settled.jsonl', spec)['status'])"
```

Scope: this calibrates the **sign and direction of one known support load**. A
known lateral or oblique load, and torque, remain uncalibrated; collisions without
a contact sensor stay UNKNOWN; this is not contact-grasp or D3 admission.
