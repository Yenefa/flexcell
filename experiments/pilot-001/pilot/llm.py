"""OpenAI-compatible chat client; key never logged, only a fingerprint."""
import hashlib
import json
import os
import sys
import time
import urllib.request


def _from_windows_registry(name):
    if os.name != "nt":
        return None
    try:
        import winreg
    except Exception:
        return None
    for hive, path in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return str(value)
        except OSError:
            continue
    return None


def _from_env_file():
    path = os.environ.get("FLEXCELL_PILOT_ENV_FILE",
                          os.path.expanduser("~/.config/flexcell/pilot.env"))
    if not os.path.isfile(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


GATE = ("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/"
        "ci-public-window/scripts/evobot_llm_key.sh")


def _looks_like_a_credential(name):
    return "API_KEY" in name.upper() or "TOKEN" in name.upper()


def _from_gate():
    """The ONE sanctioned source for the credential.

    WHY THE FALLBACKS HAD TO GO (measured, not suspected): setting() used to resolve
    env -> Windows registry -> ~/.config/flexcell/pilot.env. The budget gate only ever
    closed the FIRST of those. With the environment variable removed, the registry still
    returned a 35-byte key, so a caller that never touched the gate could still spend
    money the ledger never saw -- the exact incident this project was held accountable
    for. A credential that can arrive by three roads is not gated by closing one of them.

    The gate checks the real account balance, refuses when the spend cannot be accounted
    for, and appends an audit line. If it cannot run, we fail closed rather than fall back
    to a copy of the key lying somewhere else on the machine.
    """
    import subprocess
    try:
        done = subprocess.run(["bash", GATE], capture_output=True, text=True, timeout=60)
    except Exception as exc:
        raise RuntimeError("budget gate could not run (%s); refusing to use a key from "
                           "any other source" % exc)
    if done.returncode != 0:
        raise RuntimeError("budget gate refused (exit %d): %s"
                           % (done.returncode, (done.stderr or "").strip()[:300]))
    return done.stdout.strip()


def setting(name, default=None):
    if _looks_like_a_credential(name):
        # No registry, no env file, no inherited copy: only the gate, or nothing.
        return _from_gate()
    if os.environ.get(name):
        return os.environ[name]
    value = _from_windows_registry(name)
    if value:
        return value
    return _from_env_file().get(name, default)


def key_fingerprint(key):
    return hashlib.sha256(key.encode()).hexdigest()[:8]


class Chat:
    def __init__(self, model=None, base_url=None, timeout=None):
        self.key = setting("FLEXCELL_PILOT_API_KEY")
        self.base_url = (setting("FLEXCELL_PILOT_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        self.model = model or setting("FLEXCELL_PILOT_MODEL", "deepseek-flash")
        self.timeout = float(timeout or setting("FLEXCELL_PILOT_TIMEOUT_S", 120))
        self.temperature = float(setting("FLEXCELL_PILOT_TEMPERATURE", 0))
        self.max_tokens = int(setting("FLEXCELL_PILOT_MAX_TOKENS", 2048))
        if not self.key:
            raise RuntimeError("no API key: set FLEXCELL_PILOT_API_KEY")
        self.calls = 0
        self.tokens = 0
        self.seconds = 0.0
        self.returned_models = []
        self.fingerprint = key_fingerprint(self.key)

    def metadata(self):
        return {"requested_model": self.model, "base_url": self.base_url,
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "key_fingerprint": self.fingerprint}

    def summary(self):
        return {"requested_model": self.model,
                "returned_models": sorted(set(self.returned_models)),
                "base_url": self.base_url, "temperature": self.temperature,
                "max_tokens": self.max_tokens, "calls": self.calls,
                "tokens": self.tokens, "seconds": round(self.seconds, 3),
                "key_fingerprint": self.fingerprint}

    def chat(self, messages, tools=None, tool_choice=None):
        payload = {
            "model": self.model, "messages": messages,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        else:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.key})
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            doc = json.load(resp)
        usage = doc.get("usage", {})
        elapsed = round(time.monotonic() - started, 3)
        self.calls += 1
        self.tokens += int(usage.get("total_tokens", 0) or 0)
        self.seconds += elapsed
        returned = doc.get("model", self.model)
        self.returned_models.append(returned)
        message = doc["choices"][0]["message"]
        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
            "tokens": int(usage.get("total_tokens", 0) or 0),
            "seconds": elapsed,
            "model": returned,
        }
