"""Function-calling agent (OpenAI tools protocol) for the pilot tasks."""
import json

SYSTEM = """You are a coding agent working inside a small repository.
Use the provided tools to inspect and modify files. Never modify anything under gate/.
You may call several tools per turn. When the task is done, reply without tool calls."""

SPECS = {
    "read_file": {"type": "object", "properties": {"path": {"type": "string"}},
                  "required": ["path"]},
    "write_file": {"type": "object",
                   "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                   "required": ["path", "content"]},
    "edit_file": {"type": "object",
                  "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                 "new": {"type": "string"}},
                  "required": ["path", "old", "new"]},
    "run_checks": {"type": "object", "properties": {}},
    "run_execution": {"type": "object", "properties": {}},
    "read_telemetry": {"type": "object", "properties": {}},
    "read_verification": {"type": "object", "properties": {}}
    ,"read_diagnosis": {"type": "object", "properties": {}},
}


class FCAgent:
    def __init__(self, chat, tools, task_text, force_first_tool=None, max_iterations=5):
        self.chat = chat
        self.tools = list(tools)
        self.force_first_tool = force_first_tool if force_first_tool in self.tools else None
        self.task_text = task_text
        self.history = []
        self.calls = 0
        self.max_iterations = int(max_iterations)

    def _schemas(self):
        return [{"type": "function",
                 "function": {"name": name, "description": name,
                              "parameters": SPECS[name]}} for name in self.tools]

    def step(self, toolbox, iteration):
        modified = [c for c in toolbox.calls if c and c[0] in ("write_file", "edit_file")]
        progress = ("Iteration %d/%d. Files modified so far: %s. Reading alone does not "
                    "complete the task; once you know the fix, apply it with edit_file "
                    "(small targeted change) or write_file." %
                    (iteration, self.max_iterations, "yes" if modified else "none"))
        messages = [{"role": "system", "content": SYSTEM + "\nTask: " + self.task_text},
                    {"role": "system", "content": progress}]
        messages.extend(self.history)
        choice = "auto"
        if not self.history and self.force_first_tool:
            choice = {"type": "function", "function": {"name": self.force_first_tool}}
        reply = self.chat.chat(messages, tools=self._schemas(), tool_choice=choice)
        self.calls += 1
        calls = reply.get("tool_calls") or []
        if not calls:
            self.history.append({"role": "assistant", "content": reply.get("content") or ""})
            return {"claim_success": False, "done": True, "tokens": reply["tokens"]}

        assistant = {"role": "assistant", "content": reply.get("content") or "",
                     "tool_calls": calls}
        self.history.append(assistant)
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                if name == "read_file":
                    result = toolbox.read_file(args["path"])
                elif name == "write_file":
                    toolbox.write_file(args["path"], args["content"])
                    result = "wrote " + args["path"]
                elif name == "edit_file":
                    toolbox.edit_file(args["path"], args["old"], args["new"])
                    result = "edited " + args["path"]
                elif name == "run_checks":
                    result = json.dumps(toolbox.run_checks())
                elif name == "run_execution":
                    result = json.dumps(toolbox.run_execution())
                elif name == "read_telemetry":
                    result = str(toolbox.read_telemetry())
                elif name == "read_verification":
                    result = str(toolbox.read_verification())
                else:
                    result = "unknown tool: " + name
            except Exception as exc:
                result = "ERROR " + type(exc).__name__ + ": " + str(exc)
            self.history.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": str(result)[:4000]})
        return {"claim_success": False, "done": False, "tokens": reply["tokens"]}
