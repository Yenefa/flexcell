# Tailscale endpoint reachability — the proxy, not the network

`#33` has carried an open question since 2026-10-17: a `GET /health` against the
Tailscale endpoint returned HTTP503 and the result was recorded as "path
unreachable". That reading was wrong. The service was never unreachable; the
client was routing the Tailscale address through the Windows system proxy.

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

`curl` succeeded on the same URL at the same time because it does not read the
Windows registry proxy. That asymmetry is what made this look like a machine or
network fault for three weeks.

This is the same failure mode as the 2026-10-17 `HTTP503` note in `#33`: "对端
不可达" and "客户端把对端塞进了代理" produce identical symptoms from the outside.

## What this does and does not establish

**Establishes:** the server binds `0.0.0.0:11435`, the Tailscale interface answers
`GET /health` with `{"status":"ok"}`, `GET /v1/models` returns the same Q8 path,
and a real 20-call typed workload completes through `100.87.190.44` once the proxy
is bypassed. The endpoint works.

**Does not establish:** cross-machine reachability. These requests were issued
from the same node that hosts the service, so they exercise the Tailscale listen
path and local routing, not a second machine's route. `#33`'s first acceptance
item still needs a request from another Tailscale peer.

## Fix, for whoever configures the client

Either add `100.64.0.0/10` to the bypass list, or set `no_proxy` for the endpoint
in whatever process calls it:

```
no_proxy=100.87.190.44     # or the whole 100.64.0.0/10 range
```

Do not "fix" this by switching the client to `127.0.0.1`. That would hide the
proxy problem rather than solve it, and it is not a channel — it is the same
machine talking to itself.

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
