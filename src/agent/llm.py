"""Deterministic stand-in for a tool-calling model.

Decision order:
1. A max_steps fault always requests another calculator call.
2. After a tool message, recover (unknown tool, tool error, empty result)
   or take the next planned step (lookup result that still needs division).
3. On the first turn, an unknown_tool / tool_raises / empty_result fault
   forces that call.
4. Otherwise plan from the user text: lookup, then arithmetic, then clock.

There is no network call and no sampled text. The same input yields the
same decision, which is what makes the scenarios repeatable.
"""

from __future__ import annotations

import re

from src.agent.contract import (
    MSG_FALLBACK,
    MSG_NOT_FOUND,
    MSG_TOOL_FAILED,
    MSG_UNKNOWN_TOOL,
)
from src.agent.types import Decision, Fault, Message

_LOOKUP = re.compile(r"\b((?:population|capital) of [A-Za-z]+)\b", re.IGNORECASE)
_DIVIDE_RESULT = re.compile(
    r"divid(?:e|ed)\s+(?:it\s+)?by\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_PLUS = re.compile(r"(\d+(?:\.\d+)?)\s+plus\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
_MINUS = re.compile(r"(\d+(?:\.\d+)?)\s+minus\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
_TIMES = re.compile(r"(\d+(?:\.\d+)?)\s+times\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
_DIVIDED = re.compile(
    r"(\d+(?:\.\d+)?)\s+divided\s+by\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_RAW_EXPR = re.compile(r"(\d+(?:\.\d+)?(?:\s*[\+\-\*/]\s*\d+(?:\.\d+)?)+)")
_CLOCK = re.compile(r"\b(clock|time|date)\b", re.IGNORECASE)


def decide(messages: list[Message], fault: Fault | None) -> Decision:
    """Return the next mock-model action. The loop records the step number."""
    user_text = _user_text(messages)
    if fault is not None and fault.kind == "max_steps":
        return Decision(kind="tool", tool="calculator", arguments={"expression": "1 + 1"})

    last_tool = _last_tool(messages)
    if last_tool is not None:
        return _continue_after_tool(user_text, messages, last_tool)

    if fault is not None and fault.kind in {"unknown_tool", "tool_raises", "empty_result"}:
        return _fault_tool_call(user_text, fault)

    return _plan(user_text)


def _continue_after_tool(
    user_text: str,
    messages: list[Message],
    last_tool: Message,
) -> Decision:
    if last_tool.kind == "unknown_tool":
        return Decision(kind="final", content=MSG_UNKNOWN_TOOL)
    if last_tool.kind == "tool_error":
        return Decision(kind="final", content=MSG_TOOL_FAILED)
    if not last_tool.content.strip():
        return Decision(kind="final", content=MSG_NOT_FOUND)
    pending = _pending_division(user_text, messages)
    if pending is not None:
        return pending
    return _final_from_tool(last_tool)


def _pending_division(user_text: str, messages: list[Message]) -> Decision | None:
    match = _DIVIDE_RESULT.search(user_text)
    if match is None:
        return None
    tool_messages = [message for message in messages if message.role == "tool"]
    if any(message.tool == "calculator" for message in tool_messages):
        return None
    lookups = [
        message
        for message in tool_messages
        if message.tool == "lookup"
        and message.kind == "tool_result"
        and message.content.strip()
    ]
    if not lookups:
        return None
    number = lookups[-1].content.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", number) is None:
        return None
    expression = f"{number} / {match.group(1)}"
    return Decision(kind="tool", tool="calculator", arguments={"expression": expression})


def _final_from_tool(message: Message) -> Decision:
    if message.tool == "clock":
        return Decision(kind="final", content=f"The system clock reports {message.content}.")
    if message.tool == "calculator":
        return Decision(kind="final", content=f"The result is {message.content}.")
    if message.tool == "lookup":
        return Decision(kind="final", content=f"The answer is {message.content}.")
    return Decision(kind="final", content=message.content)


def _fault_tool_call(user_text: str, fault: Fault) -> Decision:
    if fault.kind == "unknown_tool":
        return Decision(
            kind="tool",
            tool=fault.tool or "",
            arguments=dict(fault.arguments or {}),
        )
    if fault.arguments is not None:
        return Decision(kind="tool", tool=fault.tool, arguments=dict(fault.arguments))
    tool_name = fault.tool or ("lookup" if fault.kind == "empty_result" else "calculator")
    if tool_name == "clock":
        return Decision(kind="tool", tool="clock", arguments={})
    if tool_name == "lookup":
        query = extract_lookup_query(user_text) or user_text
        return Decision(kind="tool", tool="lookup", arguments={"query": query})
    expression = extract_expression(user_text) or "0 + 0"
    return Decision(kind="tool", tool=tool_name, arguments={"expression": expression})


def _plan(user_text: str) -> Decision:
    query = extract_lookup_query(user_text)
    if query is not None:
        return Decision(kind="tool", tool="lookup", arguments={"query": query})
    expression = extract_expression(user_text)
    if expression is not None:
        return Decision(kind="tool", tool="calculator", arguments={"expression": expression})
    if _CLOCK.search(user_text):
        return Decision(kind="tool", tool="clock", arguments={})
    return Decision(kind="final", content=MSG_FALLBACK)


def extract_lookup_query(text: str) -> str | None:
    match = _LOOKUP.search(text)
    if match is None:
        return None
    return " ".join(match.group(1).split())


def extract_expression(text: str) -> str | None:
    for pattern, symbol in (
        (_PLUS, "+"),
        (_MINUS, "-"),
        (_TIMES, "*"),
        (_DIVIDED, "/"),
    ):
        match = pattern.search(text)
        if match is not None:
            return f"{match.group(1)} {symbol} {match.group(2)}"
    match = _RAW_EXPR.search(text)
    if match is not None:
        return match.group(1)
    return None


def _user_text(messages: list[Message]) -> str:
    for message in messages:
        if message.role == "user":
            return message.content
    return ""


def _last_tool(messages: list[Message]) -> Message | None:
    for message in reversed(messages):
        if message.role == "tool":
            return message
    return None
