#!/usr/bin/env python3
"""The only LLM client Baseline B may use, and it has no bypass path.

WHY THIS IS NOT A WRAPPER AROUND pilot.llm.Chat
-----------------------------------------------
`experiments/pilot-001/pilot/llm.py` resolves the credential through THREE
fallbacks: environment variable, Windows registry, then `~/.config/flexcell/pilot.env`.
Measured on this machine, with the env var explicitly removed:

    pilot.llm.setting("FLEXCELL_PILOT_API_KEY") -> 35 bytes, source = windows_registry

So any code path that reaches `pilot.llm.Chat()` can spend money without ever
touching `ci-public-window/scripts/evobot_llm_key.sh`. `runtime/planner/
prepare_baseline_b.py` does exactly that: it contains the string
"from pilot.llm import Chat" and does NOT contain "evobot_llm_key" (measured).
The gate's own comment names this file as the spender that is not governed by the
ledger. Wrapping it and hoping would leave the same fallbacks underneath.

This module therefore does NOT import pilot.llm. It has exactly one way to
obtain a credential -- run the gate -- and no fallback branch to fall through.

WHAT IT GUARANTEES, each one a test
-----------------------------------
  1. no gate  -> no key   : `key_from_gate` raises if the script is absent
  2. gate rc != 0 -> no key: a refusal (exit 3 = over budget / low balance)
                            propagates as an exception, never as an empty key
  3. key never logged      : only a sha256 prefix is recorded
  4. every call is counted : tokens and seconds are returned per call, so cost
                            per arm is reportable (experiment protocol rule 1:
                            a budget advantage must not masquerade as capability)
  5. no key in argv/env    : the key is passed in-process, never exported, so it
                            cannot be inherited by a child or read from ps

The gate itself is unchanged. This module only calls it.
"""
import hashlib
import json
import os
import subprocess
import time
import urllib.request

# Absolute path, because a relative one depends on the caller's cwd and a cwd trap
# has already silently disabled a pipeline step in this repository once.
GATE = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh"

# Used only when the gate lives somewhere else, e.g. on the Windows side of the
# WSL boundary. Kept explicit so a missing gate is loud rather than papered over.
GATE_ENV_OVERRIDE = "EVOBOT_LLM_GATE"


class GateRefused(RuntimeError):
    """The budget gate refused to release a key. Never downgraded to a warning."""


def gate_path():
    return os.environ.get(GATE_ENV_OVERRIDE) or GATE


def key_from_gate(caller="baseline-b"):
    """Run the gate and return the key. Raises on every non-success path.

    The gate's contract is: stdout is the key and nothing else; diagnostics go to
    stderr; exit 3 means refused. This function adds no leniency -- an empty
    stdout, a non-zero status, or a missing script all raise.
    """
    path = gate_path()
    if not os.path.isfile(path):
        raise GateRefused(
            "budget gate not found at %s -- refusing to spend money through an "
            "unaccounted path (set %s to relocate it)" % (path, GATE_ENV_OVERRIDE))
    env = dict(os.environ)
    env["EVOBOT_CALLER"] = caller
    proc = subprocess.run(["bash", path], capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise GateRefused(
            "budget gate refused (exit %d): %s"
            % (proc.returncode, (proc.stderr or "").strip()[:400]))
    key = (proc.stdout or "").strip()
    if not key:
        raise GateRefused("budget gate exited 0 but released no key")
    return key


def key_fingerprint(key):
    return hashlib.sha256(key.encode()).hexdigest()[:8]


class GatedChat:
    """Minimal OpenAI-compatible client that can only be built from the gate."""

    def __init__(self, model=None, base_url=None, timeout=None, caller="baseline-b"):
        self.key = key_from_gate(caller=caller)
        self.fingerprint = key_fingerprint(self.key)
        self.base_url = (base_url or os.environ.get("EVOBOT_LLM_BASE_URL")
                         or "https://api.deepseek.com").rstrip("/")
        self.model = model or os.environ.get("EVOBOT_LLM_MODEL") or "deepseek-flash"
        self.timeout = float(timeout or os.environ.get("EVOBOT_LLM_TIMEOUT_S") or 120)
        # Temperature 0 by default: a baseline that is reproducible is a baseline
        # that can be re-run by a third party. A sampling baseline confounds
        # "the agent cannot plan this" with "the agent sampled badly today".
        self.temperature = float(os.environ.get("EVOBOT_LLM_TEMPERATURE") or 0)
        self.max_tokens = int(os.environ.get("EVOBOT_LLM_MAX_TOKENS") or 2048)
        self.calls = 0
        self.tokens = 0
        self.seconds = 0.0
        self.returned_models = []

    def metadata(self):
        """Everything a reader needs to reproduce this, and nothing secret."""
        return {"requested_model": self.model, "base_url": self.base_url,
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "key_fingerprint": self.fingerprint,
                "key_source": "evobot_llm_key.sh", "gate": gate_path()}

    def summary(self):
        return {"calls": self.calls, "tokens": self.tokens,
                "seconds": round(self.seconds, 3),
                "returned_models": sorted(set(self.returned_models)),
                **self.metadata()}

    def chat(self, messages):
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature, "max_tokens": self.max_tokens,
                   "response_format": {"type": "json_object"}}
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.key})
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            doc = json.load(response)
        elapsed = round(time.monotonic() - started, 3)
        usage = doc.get("usage") or {}
        tokens = int(usage.get("total_tokens", 0) or 0)
        returned = doc.get("model", self.model)
        self.calls += 1
        self.tokens += tokens
        self.seconds += elapsed
        self.returned_models.append(returned)
        message = doc["choices"][0]["message"]
        return {"content": message.get("content") or "", "tokens": tokens,
                "seconds": elapsed, "model": returned}


def main(argv=None):
    """Self-test: prove the gate is reachable and a key can be obtained.

    This spends NO tokens -- it never calls /chat/completions. It is safe to run
    as a preflight, and it is what the harness calls before a batch so a dead
    gate fails before a 25-minute run rather than during it.
    """
    import sys
    argv = argv or sys.argv[1:]
    try:
        key = key_from_gate(caller="baseline-b-preflight")
    except GateRefused as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}))
        return 3
    print(json.dumps({"ok": True, "key_len": len(key),
                      "fingerprint": key_fingerprint(key),
                      "gate": gate_path(),
                      "spent_tokens": 0}, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
