"""Function-calling agent (OpenAI tools protocol) for the pilot tasks."""
import json

SYSTEM = """You are a coding agent working inside a small repository.
Use the provided tools to inspect and modify files. Never modify anything under gate/.
You may call several tools per turn. When the task is done, reply without tool calls."""

SPECS = {
    "search_code": {
        "name": "search_code",
        "description": "Regex search across workspace source/text files; returns path:line matches. Use it first to find the relevant function, then read_file with start/count around that line.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]},
    },
    "read_file": {"type": "object",
                  "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                                 "count": {"type": "integer"}},
                  "required": ["path"]},
    "write_file": {"type": "object",
                   "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                   "required": ["path", "content"]},
    "list_dir": {"type": "object", "properties": {"path": {"type": "string"}}},
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


DESCRIPTIONS = {
    "read_file": "Read a workspace file. A directory returns a listing. For a large file pass "
                 "start (1-based line) and count to read a line range.",
    "list_dir": "List the entries of a workspace directory.",
    "search_code": "Regex search across workspace .py/.yaml/.md/.json files; returns "
                   "path:line: text. Use it to locate a function before reading it.",
    "write_file": "Write a whole file with the given content.",
    "edit_file": "Replace exactly one occurrence of old with new inside a file.",
    "run_checks": "Run the workspace unit checks (fast, no simulation).",
    "run_execution": "Run the target scenario on the real Gazebo stack and return its summary.",
    "read_telemetry": "Read the telemetry of the most recent execution.",
    "read_verification": "Read the independent judge verdict of the last execution.",
    "read_diagnosis": "Read the recorded failure diagnosis of the last execution.",
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
                 "function": {"name": name,
                              "description": DESCRIPTIONS.get(name, name),
                              "parameters": SPECS[name]}} for name in self.tools]

    def step(self, toolbox, iteration):
        modified = [c for c in toolbox.calls if c and c[0] in ("write_file", "edit_file")]
        ran = [c for c in toolbox.calls if c and c[0] == "run_execution"]
        progress = (
            "Iteration %d/%d. Files modified so far: %s. Executions run so far: %d. "
            "Reading alone does not complete the task. The scenario must be run at "
            "least once so the failure is observed, and the fix must be applied with "
            "edit_file (a small targeted change)." %
            (iteration, self.max_iterations,
             "yes" if modified else "none", len(ran)))
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
        results = []
        self.history.append(assistant)
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                if name == "read_file":
                    result = toolbox.read_file(args["path"], args.get("start"), args.get("count"))
                elif name == "list_dir":
                    result = toolbox.list_dir(args.get("path", "."))
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
                elif name == "search_code":
                    result = toolbox.search_code(args["pattern"], args.get("path", "."))
                elif name == "read_telemetry":
                    result = str(toolbox.read_telemetry())
                elif name == "read_verification":
                    result = str(toolbox.read_verification())
                else:
                    result = "unknown tool: " + name
            except Exception as exc:
                result = "ERROR " + type(exc).__name__ + ": " + str(exc)
            limit = 20000 if name in ("read_file", "search_code") else 4000
            self.history.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": str(result)[:limit]})
            # P1 tooling: record the ARGUMENTS too. Without them a failed run is
            # undiagnosable - you cannot tell which pattern the agent searched for
            # or which page it read.
            results.append({"tool": name, "args": args,
                            "result": str(result)[:400]})
        return {"claim_success": False, "done": False, "tokens": reply["tokens"],
                "assistant_text": (reply.get("content") or "")[:800], "results": results}
