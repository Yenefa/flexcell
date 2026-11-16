"""Per-slot budget enforcement for the v0.2 repair matrix.

WHY THIS EXISTS
    PROTOCOL.md 5.1 caps every candidate at 6 model interactions and 20,000
    tokens, and says exceeding either stops the record with terminal state
    BUDGET_EXHAUSTED, which "must not count as success, and must not be
    topped up". Nothing in this repository enforced that. The draft driver used
    a ScriptedAgent that never touches a model, so the cap, the accounting and
    the terminal state had no execution coverage at all.

    A cap that exists only in a document is not a cap. When the credential
    finally arrives, the first real run would be the first time this rule is
    exercised - and the failure mode of getting it wrong is the worst one
    available here: a run that spent past its budget still recorded as a
    success, which silently biases the comparison toward whichever condition
    happens to be chattier.

HOW THE LIMITS ARE APPLIED
    Both limits are checked BEFORE the transport is called, so a call that
    would exceed the interaction cap is never made and costs nothing. Tokens
    cannot be known until after a call, so the token cap is also checked after
    accumulation: a response that pushes the total past the cap ends the record.
    That call's cost is counted, because it was really spent.

    Once a limit is hit the ledger closes permanently. 5.1 forbids "one more
    try", so a closed ledger refuses every later call without reaching the
    transport. This is deliberately not a flag the caller can reset.
"""
import time

DEFAULT_INTERACTIONS = 6
DEFAULT_TOKENS = 20000

# Terminal states a slot can end in. BUDGET_EXHAUSTED is not a failure of the
# repair and not a success: 5.1 requires it be excluded from the denominators.
DONE = "DONE"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
INVALID = "INVALID"


class BudgetExhausted(Exception):
    """Raised when a call would exceed, or did exceed, a hard limit."""

    def __init__(self, which, at_interaction, at_tokens):
        self.which = which
        self.at_interaction = at_interaction
        self.at_tokens = at_tokens
        super().__init__(
            "budget exhausted: %s (interactions=%d, tokens=%d)"
            % (which, at_interaction, at_tokens)
        )

    def as_dict(self):
        return {"budget_exhausted": self.which,
                "budget_exhausted_at": {"interaction": self.at_interaction,
                                        "tokens": self.at_tokens}}


class Ledger:
    """The only way a repair run may reach the model.

    The transport is any object with chat(messages, **kwargs) returning a dict
    that carries the text and usage: {"usage": {"prompt_tokens": n,
    "completion_tokens": m}}. Injecting it is what lets the cap be proven
    without spending money.
    """

    def __init__(self, transport, max_interactions=DEFAULT_INTERACTIONS,
                 max_tokens=DEFAULT_TOKENS, max_candidate_executions=None,
                 clock=time.monotonic):
        if max_interactions < 1:
            raise ValueError("max_interactions must be at least 1")
        if max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        self.transport = transport
        self.max_interactions = max_interactions
        self.max_tokens = max_tokens
        self.max_candidate_executions = max_candidate_executions
        self._clock = clock
        self.interactions_used = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.candidate_executions = 0
        self._closed = None
        self._started = clock()
        self._finished = None

    # ---------------------------------------------------------------- checks
    @property
    def tokens_total(self):
        return self.tokens_in + self.tokens_out

    @property
    def closed(self):
        return self._closed is not None

    def _refuse_if_closed(self):
        if self._closed is not None:
            # 5.1: no topping up. The original exception is re-raised so the
            # position it records stays the one that actually stopped the run.
            raise self._closed

    def _check_before(self):
        self._refuse_if_closed()
        if self.interactions_used >= self.max_interactions:
            self._closed = BudgetExhausted("interactions", self.interactions_used,
                                           self.tokens_total)
            raise self._closed
        if self.tokens_total >= self.max_tokens:
            self._closed = BudgetExhausted("tokens", self.interactions_used,
                                           self.tokens_total)
            raise self._closed

    # ------------------------------------------------------------------ call
    def chat(self, messages, **kwargs):
        """One request-response. Counts as one interaction, per 5.1."""
        self._check_before()
        response = self.transport.chat(messages, **kwargs)
        usage = (response or {}).get("usage") or {}
        self.interactions_used += 1
        self.tokens_in += int(usage.get("prompt_tokens") or 0)
        self.tokens_out += int(usage.get("completion_tokens") or 0)
        # A response that pushed the total past the cap ends the record, but its
        # cost stays counted: it was really spent.
        if self.tokens_total > self.max_tokens:
            self._closed = BudgetExhausted("tokens", self.interactions_used,
                                           self.tokens_total)
            raise self._closed
        return response

    def count_execution(self):
        """Record one candidate scene execution against 5.3."""
        if (self.max_candidate_executions is not None
                and self.candidate_executions >= self.max_candidate_executions):
            self._closed = BudgetExhausted("candidate_executions",
                                           self.interactions_used, self.tokens_total)
            raise self._closed
        self.candidate_executions += 1

    def finish(self):
        if self._finished is None:
            self._finished = self._clock()

    # -------------------------------------------------------------- account
    def terminal_state(self, exhausted=False, claimed_success=False):
        """What the record's terminal state must be.

        5.1 is explicit that an exhausted record does not count as success, so
        a late claim from the agent cannot upgrade it. Exhaustion wins.
        """
        if exhausted or self.closed:
            return BUDGET_EXHAUSTED
        return DONE if claimed_success else INVALID

    def account(self):
        """The 5.2 ledger fields, every one of which is required."""
        end = self._finished if self._finished is not None else self._clock()
        payload = {
            "interactions_used": self.interactions_used,
            "interactions_cap": self.max_interactions,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "tokens_total": self.tokens_total,
            "tokens_cap": self.max_tokens,
            "tokens_source": "provider_usage",
            "candidate_executions": self.candidate_executions,
            "wall_clock_s": round(max(0.0, end - self._started), 3),
            "budget_exhausted_at": None,
        }
        if self._closed is not None:
            payload["budget_exhausted_at"] = {
                "on": self._closed.which,
                "interaction": self._closed.at_interaction,
                "tokens": self._closed.at_tokens,
            }
        return payload
