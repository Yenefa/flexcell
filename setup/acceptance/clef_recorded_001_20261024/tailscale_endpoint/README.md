# Tailscale endpoint: Windows client proxy comparison

`#33` has carried an open question since 2026-10-17: a `GET /health` against the
Tailscale endpoint returned HTTP503 through the cloud environment's proxy.
That observation did not establish that the home machine was offline. The
comparisons below diagnose a later Windows-client proxy failure on the service
host; they do not establish the cause of the earlier cloud response.

## Three runs, one variable

Same client, same server, same model, same weights. Only the destination address
and the proxy override differ.

| # | endpoint | `no_proxy` | result |
| --- | --- | --- | --- |
| 1 | `http://100.87.190.44:11435/v1/systemone` | not set | **first call FAIL** — HTTP 502 after 7 652 ms, FSM fallback, `No real Clef proposal` |
| 2 | `http://100.87.190.44:11435/v1/systemone` | `100.87.190.44` | **20/20 PASS**, p50 ≈ 1.9 s |
| 3 | `http://127.0.0.1:11435/v1/systemone` | not set | **20/20 PASS** (the archived CLEF-RECORDED-001 receipt) |

Run 1's report is kept as it came out; nothing was retried into it or overwritten.
The verifier rejected it for exactly the right reasons — a 502 produced an FSM
fallback, and a fallback is not a model proposal.

## Root cause

```
HKCU\...\Internet Settings
  ProxyEnable   = 1
  ProxyServer   = 127.0.0.1:7890
  ProxyOverride = ...;localhost;*.local;127.*;10.*;172.16.*;...;192.168.*
```

The bypass list covers `127.*` and the RFC1918 ranges, but **not
`100.87.190.44`**, which is in the Tailscale CGNAT range `100.64.0.0/10`.
`urllib.request.getproxies()` therefore returns `http://127.0.0.1:7890`, and the
typed request goes to the local proxy, which answers **502 Bad Gateway** because
it has no route for a private overlay address.

`curl` succeeded on the same URL at the same time while Python used the Windows
registry proxy. The process-local exception comparison supports this diagnosis
for this Windows client.

The cloud HTTP503 and this Windows HTTP502 came from different clients and
proxies. No same-environment comparison or proxy log ties them together; the
cloud root cause remains unestablished. This Windows process-local setting is
not an instruction to bypass the managed cloud environment's proxy.
The original `same_root_cause_as` field in `proxy_evidence.json` is preserved
as received; it records the earlier interpretation, not a verified attribution.

## What this does and does not establish

**Establishes:** the server binds `0.0.0.0:11435`, the Tailscale interface answers
`GET /health` with `{"status":"ok"}`, `GET /v1/models` returns the same Q8 path,
and a real 20-call typed workload completes through `100.87.190.44` once the proxy
is bypassed. The endpoint works.

**Does not establish:** direct cross-machine HTTP access to port 11435. These
requests were issued from the service host. The earlier
[home functional regressions](../../home_gpu_abort_20261024/README.md) already
record cross-machine inference through an SSH forward over Tailscale. That
separate route need not be rerun; this local comparison does not prove direct
HTTP access from another peer or qualify competition deployment.

## Fix, for whoever configures the client

For this Windows Python client, set an exact endpoint exception in the calling
process and verify with that client:

```
no_proxy=100.87.190.44
```

CIDR matching is client-specific; do not assume Python/Windows accepts
`100.64.0.0/10` as a bypass. Local loopback and an explicitly configured SSH
forward are also different paths; label which was tested.

## Files

| file | what it is |
| --- | --- |
| `clef_tailscale_20261024T132010Z.json` | run 1, the 502 failure, kept verbatim |
| `clef_tailscale_noproxy_20261024T132052Z.json` | run 2, 20/20 PASS with `no_proxy` set |
| `proxy_evidence.json` | registry settings, `urllib`'s view, and the finding |

`GET /v1/models` also reports the model under its **file path**
(`F:\flexcell-models\Clef-Flash-Q8_0.gguf`) rather than the alias
`clef-flash-q8_0` the typed client requests. Both resolve to the same weights, but
the alias is not the identity — the sha is, and the sha is checked locally.
