"""A scripted stand-in for the Meta Model API. It proves the loop and the checks work; it says nothing about the real model."""

import json
from types import SimpleNamespace as NS


def call(_fn, **args):
    return NS(id=f"c{abs(hash((_fn, json.dumps(args, sort_keys=True)))) % 10**8}", function=NS(name=_fn, arguments=json.dumps(args)))


def reply(*calls, text="", finish="tool_calls"):
    return NS(choices=[NS(finish_reason="stop" if (not calls and finish == "tool_calls") else finish, message=NS(content=text, tool_calls=list(calls) or None))])


class FakeClient:
    def __init__(self, script):
        self.script, self.seen = list(script), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw["messages"][-1])
        return self.script.pop(0)
