"""The repair loop that spends the budget, and the only place that may call it.

WHAT THIS ADDS OVER THE SCRIPTED DRY RUN
    ScriptedAgent applies a known fix without reading anything, so it cannot
    show that the information a condition is allowed to see actually reaches the
    grader, and it never spends a token. This agent composes its prompt from the
    visibility boundary - which is what enforces the condition - and reaches the
    model only through the Ledger, so every turn is counted against 5.1.

    The agent cannot read the evaluator, the verdict or the hidden answer,
    because it only ever touches the ToolFacade; the facade refuses. That is the
    point of routing file access through it rather than open-coding paths.
"""
import json

from budget import BUDGET_EXHAUSTED, BudgetExhausted, DONE, INVALID, Ledger  # noqa: F401


class RepairAgent:
    """One candidate's repair attempt under one condition."""

    def __init__(self, ledger, boundary, task_text, editable_fields, guidance=None):
        self.ledger = ledger
        self.boundary = boundary
        self.task_text = task_text
        self.editable_fields = tuple(editable_fields)
        self.guidance = guidance
        self.transcript = []
        self.claimed_success = False
        self.done = False
        self.writes = []

    # ------------------------------------------------------------ prompt
    def system_prompt(self):
        lines = [
            "You are repairing a robot skill so the task succeeds.",
            "",
            "TASK",
            self.task_text.strip(),
            "",
            "You may only change these paths:",
        ]
        for field in self.editable_fields:
            lines.append("  - " + field)
        lines.append("")
        lines.append(
            "Reply with a single JSON object: "
            '{"actions": [{"write_file": [path, content]}], '
            '"claim_success": bool, "done": bool}. '
            "No prose outside the JSON."
        )
        return "\n".join(lines)

    def messages(self):
        """Everything this condition is permitted to know, and nothing else."""
        messages = [{"role": "system", "content": self.system_prompt()}]
        feedback = self._feedback()
        if feedback:
            messages.append({"role": "user", "content": "EXECUTION FEEDBACK\n" + feedback})
        if self.guidance:
            messages.append({"role": "user", "content": "GUIDANCE\n" + self.guidance})
        if self.transcript:
            messages.extend(self.transcript)
        return messages

    def _feedback(self):
        """Ask the boundary for whatever this condition permits.

        For A this raises AccessDenied, which is the mechanism working, so an
        empty string is the correct answer there. Any other failure is a real
        problem and must not be silently flattened into "no feedback", because
        that would turn a broken harness into a plausible-looking A run.
        """
        try:
            return str(self.boundary.read_feedback() or "")
        except Exception as exc:
            reason = (getattr(exc, "as_dict", None) or (lambda: {}))().get("reason")
            if reason in ("policy_denied", "policy_refused"):
                return ""
            raise

    # -------------------------------------------------------------- steps
    def step(self):
        """One interaction. Returns True when the agent says it is done."""
        response = self.ledger.chat(self.messages())
        text = (response or {}).get("text") or ""
        self.transcript.append({"role": "assistant", "content": text})
        payload = _parse(text)
        if payload is None:
            # An unparseable turn still costs an interaction; it does not end
            # the run by itself, because 5.1 counts interactions not replies.
            self.transcript.append({"role": "user", "content":
                                    "Your reply was not valid JSON. Reply with the object only."})
            return False

        for action in payload.get("actions") or []:
            if not isinstance(action, dict) or "write_file" not in action:
                continue
            target = action["write_file"]
            if not isinstance(target, (list, tuple)) or len(target) != 2:
                continue
            path, content = target
            self.boundary.write_text(path, str(content))
            self.writes.append(path)

        if payload.get("claim_success"):
            self.claimed_success = True
        self.done = bool(payload.get("done"))
        return self.done

    def run(self, max_steps=None):
        """Drive to done or exhaustion. Exhaustion is a state, not a crash.

        The loop is bounded at cap+1 on purpose. Stopping exactly at the cap
        would end the run having used every allowed interaction and never
        asking for one more, so the ledger would never get the chance to refuse
        and the record would come back INVALID instead of BUDGET_EXHAUSTED -
        an agent that silently ran out of turns would look like an agent that
        gave up. The extra attempt is refused before it reaches the transport,
        so discovering exhaustion costs nothing.
        """
        exhausted = False
        limit = max_steps if max_steps is not None else self.ledger.max_interactions + 1
        steps = 0
        while not self.done and steps < limit:
            try:
                self.step()
            except BudgetExhausted:
                exhausted = True
                break
            steps += 1
        if not self.done and self.ledger.closed:
            exhausted = True
        self.ledger.finish()
        return dict(
            terminal_state=self.ledger.terminal_state(
                exhausted=exhausted, claimed_success=self.claimed_success),
            account=self.ledger.account(),
            claimed_success=self.claimed_success,
            writes=list(self.writes),
        )


def _parse(text):
    """Pull one JSON object out of a reply, tolerating fences and prose."""
    if not isinstance(text, str) or not text.strip():
        return None
    body = text.strip()
    fence = "```"
    if body.startswith(fence):
        body = body.split(fence)[1] if fence in body[len(fence):] else body[len(fence):]
        if body.startswith("json"):
            body = body[4:]
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(body[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
