"""The agent loop: the model calls tools until it has nothing left to do. Plain OpenAI-SDK code."""

from __future__ import annotations

import json

from solar_agent.agent.workspace import Workspace

SYSTEM_PROMPT = """You prepare the technical basis of a solar + storage proposal from the documents of a case.

Rules that cannot be bent:
1. You never do arithmetic and never invent a number. Code sizes the system; you only supply inputs.
2. Every input comes from a document: call read_document, then set_value with kind measured, datasheet or
   standard, naming the document and quoting it exactly, copy-paste. The value must appear in the quote.
3. If a document does not give a value, never guess to look complete. Facts about the world (who owns land,
   permits, people, access, local rules, how much is consumed) cannot be assumptions: call ask_human. Design
   parameters and routine engineering defaults (performance ratio, battery autonomy in days) may be recorded as
   kind assumption with a stated reason; a person confirms them later. If sizing needs a value you also asked a
   person about, record a reasoned assumption too, so sizing is not blocked; the question stays open.
4. Efficiencies, depth of discharge and performance ratio are fractions between 0 and 1: 45 % is 0.45.
5. Call get_solar_resource once for the site's design peak sun hours. Never set that value yourself.
6. As soon as no required input is missing, call size_system. Do not call get_status repeatedly. If size_system
   reports missing inputs, record them and call it again.
7. Finish with one short sentence. The proposal document is written by code from what you recorded.
"""


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    _tool("get_status", "Documents available, values already recorded, and what is still missing.", {}, []),
    _tool("read_document", "Read one case document in full.", {"name": {"type": "string"}}, ["name"]),
    _tool("set_value",
          "Record one input. measured/datasheet/standard need `document` and an exact `why_or_quote` from it; "
          "assumption needs a reason in `why_or_quote`. Fractions use 0-1 (45 % is 0.45).",
          {"section": {"type": "string"}, "field": {"type": "string"}, "value": {"type": "number"},
           "kind": {"type": "string", "enum": ["measured", "datasheet", "standard", "assumption"]},
           "why_or_quote": {"type": "string"}, "document": {"type": "string"}},
          ["section", "field", "value", "kind", "why_or_quote"]),
    _tool("ask_human", "Escalate something that cannot be proven from the documents.",
          {"question": {"type": "string"}, "why": {"type": "string"}}, ["question", "why"]),
    _tool("get_solar_resource", "Fetch the site's design peak sun hours (NASA POWER).", {}, []),
    _tool("size_system", "Size the system from the recorded inputs, or list what is missing.", {}, []),
]


def dispatch(ws: Workspace, name: str, args: dict) -> dict:
    fn = {"get_status": ws.get_status, "read_document": ws.read_document, "set_value": ws.set_value,
          "ask_human": ws.ask_human, "get_solar_resource": ws.get_solar_resource, "size_system": ws.size_system}.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # a tool failing must reach the model as text, never crash the run
        return {"error": f"{type(e).__name__}: {e}"}


def run(client, model: str, ws: Workspace, objective: str, max_turns: int = 25, max_tokens: int = 4000,
        log=lambda line: None) -> dict:
    """Returns {"finished": bool, "turns": int, "final_text": str}. `finished` is False if the turn limit was hit."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Case objective:\n\n{objective}\n\nBegin with get_status."}]
    for turn in range(1, max_turns + 1):
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, max_tokens=max_tokens)
        choice = resp.choices[0]
        msg = choice.message
        calls = msg.tool_calls or []
        entry: dict = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]
        messages.append(entry)
        if not calls:
            if choice.finish_reason == "length" and not (msg.content or "").strip():
                log(f"turn {turn}: the model ran out of tokens while reasoning; raise max_tokens")
                return {"finished": False, "turns": turn, "final_text": ""}
            return {"finished": True, "turns": turn, "final_text": (msg.content or "").strip()}
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                result = {"error": "arguments were not valid JSON"}
            else:
                result = dispatch(ws, c.function.name, args)
            log(f"turn {turn}: {c.function.name}({_short(c.function.arguments)}) -> {_short(json.dumps(result))}")
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(result, ensure_ascii=False)})
    return {"finished": False, "turns": max_turns, "final_text": ""}


def _short(text: str, n: int = 140) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"
