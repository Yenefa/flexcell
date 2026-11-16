"""Adapt the repository's gated client to the Ledger's transport shape.

WHY A SEPARATE ADAPTER
    budget.Ledger calls transport.chat(messages) and expects {"text", "usage"}.
    GatedChat.chat(messages) returns {"content", "tokens", ...}. The names differ
    and, more importantly, so does the accounting: GatedChat reports one total
    token count and no input/output split.

    DATA_DICTIONARY 3.4 already covers that case - a provider that does not give
    the split must have tokens_total recorded only, and the split must not be
    inferred from it. So this adapter reports total-only usage and says so,
    rather than splitting a number in half to make a field look filled in.

WHAT IT WILL NOT DO
    It never reads the key itself. The key only ever exists inside GatedChat,
    which obtains it by running the budget gate. That is the whole point of the
    gate, and an adapter that shortcuts it would undo it.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GATED_CHAT = ROOT / "runtime" / "planner" / "gated_chat.py"


def _load_gated_chat():
    """Import runtime/planner/gated_chat.py by path.

    It is not an importable package from here, and adding the repository root to
    sys.path would shadow other modules, so it is loaded explicitly.
    """
    if not GATED_CHAT.exists():
        raise RuntimeError("gated_chat.py not found at %s" % GATED_CHAT)
    spec = importlib.util.spec_from_file_location("flexcell_gated_chat", GATED_CHAT)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("flexcell_gated_chat", module)
    spec.loader.exec_module(module)
    return module


class GatedTransport:
    """One repair run's only route to the model."""

    def __init__(self, model=None, base_url=None, timeout=None, caller="repair-eval-v02"):
        self._module = _load_gated_chat()
        self._resolve_gate()
        self.client = self._module.GatedChat(model=model, base_url=base_url,
                                             timeout=timeout, caller=caller)
        self.calls = 0
        self.total_tokens = 0

    @staticmethod
    def _resolve_gate():
        """Point gated_chat at the operator's gate when the repo default is absent.

        The repository default is an absolute path belonging to another machine,
        so on this one it never exists. Rather than editing that file - it is not
        ours - the adapter sets the override the client already supports. If
        neither path exists, nothing is set and the client raises its own clear
        error, which is the correct outcome: no gate means no spending.
        """
        import os
        if os.environ.get("EVOBOT_LLM_GATE"):
            return os.environ["EVOBOT_LLM_GATE"]
        default = ("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/"
                   "ci-public-window/scripts/evobot_llm_key.sh")
        if os.path.exists(default):
            return default
        candidate = os.environ.get("FLEXCELL_GATE_PATH") or os.path.expanduser(
            "~/.config/flexcell/llm_gate.sh")
        if os.path.exists(candidate):
            os.environ["EVOBOT_LLM_GATE"] = candidate
            return candidate
        return None

    # ------------------------------------------------------------ identity
    def metadata(self):
        """What a reader needs to reproduce the call, and nothing secret."""
        info = self.client.metadata()
        return {"requested_model": info["requested_model"],
                "base_url": info["base_url"],
                "temperature": info["temperature"],
                "max_tokens": info["max_tokens"],
                "key_fingerprint": info["key_fingerprint"],
                "key_source": info["key_source"],
                "gate": info["gate"],
                "adapter": "GatedTransport/1"}

    # ---------------------------------------------------------------- call
    def chat(self, messages, **kwargs):
        reply = self.client.chat(messages)
        self.calls += 1
        tokens = int(reply.get("tokens") or 0)
        self.total_tokens += tokens
        return {
            "text": reply.get("content") or "",
            # total only: the provider does not report the split, and 3.4 forbids
            # inventing one
            "usage": {"total_tokens": tokens, "split_available": False},
            "model_returned": reply.get("model"),
            "seconds": reply.get("seconds"),
        }
