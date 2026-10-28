# Recorder offline regression, 2026-10-28

Source: rejected camera CI run 40537157656, artifact 12750996664; ZIP SHA256
`ddccc76c4e0597e663352cb24faa61c19847344722bd9b5064b37f62b6f2af96`.
The original rejection and raw records are unchanged.

`replay.py` publishes only clock, state, controller-state, accepted-command telemetry,
physics trace and images in an isolated DDS domain. No simulator, action goals or
actuator commands. One affected bag is the old-recorder control; all five are then
replayed once through the candidate, without filtering the source range. Both versions
receive a deterministic 0.8 s encoding stall every 30 images.

| Check | Old callback | Bounded writer |
| --- | --- | --- |
| First bag | 480/504 images | 504/504 |
| All candidate bags | Not a comparison cohort | 2445/2445, original order |
| Original task/context intervals | First: 169/179, 34 invalid alignments | All five: 718/718, no invalid alignments |
| Queue/cleanup | Not available | No overflow/errors; fully drained, peak pending 7–8 of 64 |
| Source RGB pixel comparison | Not used for admission | 2445/2445 images match exactly |

This verifies resistance to the tested stalls, not the unique historical cause,
unlimited throughput or fresh camera CI success. No new learning dataset was published;
the earlier 5-episode/574-frame sample is unchanged.

The report, compressed frame manifests and pixel comparison results are retained.
`inputs.json` contains source/manifests/image hashes. PNGs are not in Git; regenerate
from the source artifact. `integration.json` pins the source PRs and 25 byte-identical
imported inputs. Narrative/tool corrections are separate from preserved data.

```bash
python3 setup/acceptance/recorder_replay_20261028/verify.py
# Optional identity check against the currently tested recorder and harness:
python3 setup/acceptance/recorder_replay_20261028/verify.py --current-source
```

Reproduce in the Jazzy CPU environment without starting the workcell:

```bash
git show 619e132:scripts/record_sim_data.py > /tmp/recorder-baseline.py
python3 setup/acceptance/recorder_replay_20261028/replay.py \
  --archive /path/to/camera-artifact.zip --baseline-script /tmp/recorder-baseline.py \
  --out /tmp/flexcell-recorder-replay --domain 169
```

Use a fresh output directory and isolated domain. `pixel-check.json` records an
independent lossless PNG IDAT/RGB-byte comparison against every source rosbag Image;
it is separate from the live replay. The compact archive excludes PNG payloads.
Local 564-test result is in `colcon-564.log`. Default joint admission stays NO_GO.
