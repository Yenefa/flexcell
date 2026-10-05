# School-mode bring-up — FlexCell with the home GPU fast arm (2026-10-05)

> For the school laptop (RTX 4060, campus network, WSL2 mirrored networking).
> Home desktop = GPU decision server, RX 6800, reachable only via Tailscale.

## Home side (done 2026-10-05, desktop `node` = `100.87.190.44`)

- Weights moved OUT of `%TEMP%` (disk-cleanup fodder) to `F:\flexcell-models\`:
  `Clef-Flash-Q8_0.gguf` (primary), `Clef-Flash-Q4_K_M.gguf` (comparison),
  `llama-b11389-vulkan\` (runtime), `start-gpu-server.bat`, `llama-server.log`.
- `start-gpu-server.bat`: idempotent (taskkill → restart), binds `0.0.0.0:11435`,
  full Q8 offload, 16384 ctx, `-ub 32768`. Verified healthy on localhost AND the
  tailnet IP. **Startup-folder registration was blocked by ACLs — manual step:
  `Win+R` → `shell:startup` → copy `F:\flexcell-models\start-gpu-server.bat` in.**
- Server has NO `--api-key` (single-user tailnet — accepted risk; one flag if
  the tailnet ever gains a third-party device).

## School side (laptop first session)

1. Join the tailnet (`tailscale` on Windows), confirm the desktop is online.
2. **Test Tailscale × mirrored-WSL2 coexistence FIRST** (both mutate routing/DNS;
   known conflict family; mirrored is mandatory on the campus network). From WSL:
   `curl http://100.87.190.44:11435/health`. Fallback ladder: NAT-mode WSL2
   outbound via the Windows stack → Tailscale userspace mode.
3. Sync code: `git fetch && git checkout feat/clef-fast-arm` (or main after the
   merge lands). The DeepSeek key/ledger on the laptop are its own (¥1.16/¥5
   history) — do NOT merge ledgers across machines.
4. Fast-arm profile: copy `mainline_jev.sh` content with ONLY the endpoint
   changed to `http://100.87.190.44:11435/v1/systemone`. Model name, weight
   sha256, calibration file and prompt digest are endpoint-independent — copy
   `jev_calibration_clef_q8.json` verbatim from the desktop
   (`~/.config/flexcell/`).
5. Smoke before any batch: 5-episode hybrid run; per-decision gates must show
   jev proposals with positive measured tokens. Cross-WAN adds ~10-200 ms per
   decision (DERP relay worst case) — irrelevant against ~2 s decisions.
6. **Batch-level anti-silent-degradation gate is REQUIRED before overnight
   batches**: assert `jev_proposals > 0` and calibration sha match per batch,
   else HARNESS_ERROR. Home reboot/Windows update otherwise silently turns a
   hybrid batch into a pure-DeepSeek batch at 30-100× cost with a green report.

## Known physical blocker (both arms)

B-grasp double-failure → `ERR_RECOVERY_EXHAUSTED` (23→51) is physics, not
routing; it caps every arm's success rate. Root cause UNKNOWN — needs its own
issue before n≥50 conclusions.
