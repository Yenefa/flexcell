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


def setting(name, default=None):
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
        self.model = model or setting("FLEXCELL_PILOT_MODEL", "deepseek-chat")
        self.timeout = float(timeout or setting("FLEXCELL_PILOT_TIMEOUT_S", 120))
        self.temperature = float(setting("FLEXCELL_PILOT_TEMPERATURE", 0))
        self.max_tokens = int(setting("FLEXCELL_PILOT_MAX_TOKENS", 2048))
        if not self.key:
            raise RuntimeError("no API key: set FLEXCELL_PILOT_API_KEY")
        self.calls = 0
        self.tokens = 0
        self.fingerprint = key_fingerprint(self.key)

    def metadata(self):
        return {"model": self.model, "base_url": self.base_url,
                "key_fingerprint": self.fingerprint}

    def chat(self, messages):
        body = json.dumps({
            "model": self.model, "messages": messages,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.key})
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            doc = json.load(resp)
        usage = doc.get("usage", {})
        self.calls += 1
        self.tokens += int(usage.get("total_tokens", 0) or 0)
        return {
            "content": doc["choices"][0]["message"]["content"],
            "tokens": int(usage.get("total_tokens", 0) or 0),
            "seconds": round(time.monotonic() - started, 3),
            "model": doc.get("model", self.model),
        }
