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
            "Two actions are available. Prefer the second for large files:"
        )
        lines.append('  {"write_file": [path, content]} replaces the whole file.')
        lines.append('  {"edit_file": [path, old_text, new_text]} replaces the first')
        lines.append("   occurrence of old_text. old_text must match the file exactly.")
        lines.append('  {"search": [path, pattern]} returns the matching lines and their')
        lines.append("   numbers. Use it to find the place; a whole large file will not")
        lines.append("   fit in the budget.")
        lines.append('  {"read_file": [path, start, lines]} returns that window of the file.')
        lines.append("Reading the file you are repairing is allowed in every condition;")
        lines.append("so is reading this workspace's tests and task.md. Nothing else is.")
        lines.append(
            "Reply with a single JSON object: "
            '{"actions": [...], "claim_success": bool, "done": bool}. '
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
            if not isinstance(action, dict):
                continue
            if "write_file" in action:
                target = action["write_file"]
                if not isinstance(target, (list, tuple)) or len(target) != 2:
                    continue
                path, content = target
                self.boundary.write_text(path, str(content),
                                         self.boundary.category_for(path))
                self.writes.append(path)
                continue
            if "search" in action:
                target = action["search"]
                if not isinstance(target, (list, tuple)) or len(target) != 2:
                    continue
                path, pattern = str(target[0]), str(target[1])
                try:
                    body = self.boundary.read_text(path, self.boundary.category_for(path))
                except Exception as exc:                        # noqa: BLE001
                    self.transcript.append({"role": "user", "content":
                                            "search: cannot read %s (%s)" % (path, exc)})
                    continue
                hits = [(n, line) for n, line in enumerate(body.splitlines(), 1)
                        if pattern in line]
                if not hits:
                    self.transcript.append({"role": "user", "content":
                                            "search: %r does not appear in %s" % (pattern, path)})
                    continue
                shown = chr(10).join("%5d: %s" % (n, line.rstrip())
                                     for n, line in hits[:40])
                self.transcript.append({"role": "user", "content":
                                        "SEARCH %s for %r: %d hit(s)%s%s"
                                        % (path, pattern, len(hits), chr(10), shown)})
                continue
            if "read_file" in action:
                target = action["read_file"]
                if not isinstance(target, (list, tuple)) or not target:
                    continue
                path = str(target[0])
                start = int(target[1]) if len(target) > 1 else 1
                count = int(target[2]) if len(target) > 2 else 120
                count = max(1, min(int(count), 400))
                try:
                    body = self.boundary.read_text(path, self.boundary.category_for(path))
                except Exception as exc:                        # noqa: BLE001
                    self.transcript.append({"role": "user", "content":
                                            "read_file: cannot read %s (%s)" % (path, exc)})
                    continue
                all_lines = body.splitlines()
                window = all_lines[max(0, start - 1): max(0, start - 1) + count]
                numbered = chr(10).join("%5d: %s" % (start + i, line)
                                        for i, line in enumerate(window))
                self.transcript.append({"role": "user", "content":
                                        "FILE %s lines %d-%d of %d%s%s"
                                        % (path, start, start + len(window) - 1,
                                           len(all_lines), chr(10), numbered)})
                continue
            if "edit_file" in action:
                target = action["edit_file"]
                if not isinstance(target, (list, tuple)) or len(target) != 3:
                    continue
                path, old_text, new_text = (str(x) for x in target)
                # Reading the candidate's own source is allowed in every
                # condition (candidate_source: true), which is what makes a
                # targeted edit possible. Without it the only action is a
                # whole-file rewrite, and a 1578-line node cannot be repaired
                # that way: measured, the model replaced it with an 18-line stub.
                try:
                    current = self.boundary.read_text(path, self.boundary.category_for(path))
                except Exception as exc:                        # noqa: BLE001
                    self.transcript.append({"role": "user", "content":
                                            "edit_file: cannot read %s (%s)" % (path, exc)})
                    continue
                if old_text not in current:
                    # Say so, and say it in a way the next turn can use.
                    self.transcript.append({"role": "user", "content":
                                            "edit_file: the old_text was not found in %s"
                                            " - read the file and copy it exactly" % path})
                    continue
                self.boundary.write_text(path, current.replace(old_text, new_text, 1))
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
        return self.result(exhausted=exhausted)

    def result(self, exhausted=None):
        """The run's outcome, also usable by a caller that drives step() itself.

        A caller that refreshes execution feedback between steps cannot use run(),
        because run() owns the loop. It should not have to re-derive the record
        either, or the two drivers will drift apart.
        """
        if exhausted is None:
            exhausted = bool(not self.done and self.ledger.closed)
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
