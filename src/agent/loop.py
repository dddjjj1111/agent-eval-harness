"""A short tool loop.

Each iteration asks the mock model for one decision. A final answer ends
the run. A tool name is executed only when it is registered. Unknown names
and tool exceptions are written to the trace and handed back to the model.
The loop stops after `max_steps` model turns even if the model keeps
requesting tools.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from src.agent.contract import MSG_MAX_STEPS
from src.agent.llm import decide
from src.agent.tools import build_registry
from src.agent.types import AgentResult, Fault, Message, TraceEvent

_DEFAULT_TOOL = {
    "tool_raises": "calculator",
    "empty_result": "lookup",
}


class MockLLMRequired(RuntimeError):
    """Raised when USE_MOCK_LLM is set to something other than 1."""


def ensure_mock_llm() -> None:
    """Refuse to run unless the mock model is selected.

    Unset means 1. This demo does not ship another model.
    """
    value = os.environ.get("USE_MOCK_LLM", "1")
    if value != "1":
        raise MockLLMRequired(
            "This demo only includes a mock LLM. Set USE_MOCK_LLM=1."
        )


def run_agent(
    user_input: str,
    *,
    max_steps: int = 6,
    fault: Fault | None = None,
) -> AgentResult:
    """Run one user turn. Exceptions from tools are captured, not raised."""
    ensure_mock_llm()
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    tools = _registry_for(fault)
    messages = [Message(role="user", content=user_input)]
    trace: list[TraceEvent] = []

    for step in range(1, max_steps + 1):
        decision = decide(messages, fault)
        if decision.kind == "final":
            trace.append(TraceEvent(step=step, kind="final", content=decision.content))
            return AgentResult(status="ok", answer=decision.content, trace=trace)

        tool_name = decision.tool or ""
        arguments = dict(decision.arguments or {})
        if tool_name not in tools:
            content = f"Unknown tool: {tool_name}"
            trace.append(
                TraceEvent(
                    step=step,
                    kind="unknown_tool",
                    tool=tool_name,
                    arguments=arguments,
                    content=content,
                )
            )
            messages.append(
                Message(role="tool", content=content, tool=tool_name, kind="unknown_tool")
            )
            continue

        try:
            output = tools[tool_name](**arguments)
        except Exception as exc:
            content = str(exc) or exc.__class__.__name__
            trace.append(
                TraceEvent(
                    step=step,
                    kind="tool_error",
                    tool=tool_name,
                    arguments=arguments,
                    content=content,
                )
            )
            messages.append(
                Message(role="tool", content=content, tool=tool_name, kind="tool_error")
            )
            continue

        text = "" if output is None else str(output)
        trace.append(
            TraceEvent(
                step=step,
                kind="tool_result",
                tool=tool_name,
                arguments=arguments,
                content=text,
            )
        )
        messages.append(
            Message(role="tool", content=text, tool=tool_name, kind="tool_result")
        )

    trace.append(TraceEvent(step=max_steps, kind="max_steps", content=MSG_MAX_STEPS))
    return AgentResult(status="max_steps", answer=MSG_MAX_STEPS, trace=trace)


def _registry_for(fault: Fault | None) -> dict[str, Callable[..., str]]:
    tools = build_registry()
    if fault is None:
        return tools
    if fault.kind in {"unknown_tool", "max_steps"}:
        if fault.kind == "unknown_tool" and not fault.tool:
            raise ValueError("unknown_tool injection requires a tool name")
        return tools
    if fault.kind not in _DEFAULT_TOOL:
        raise ValueError(f"unsupported fault kind: {fault.kind}")

    tool_name = fault.tool or _DEFAULT_TOOL[fault.kind]
    if tool_name not in tools:
        raise ValueError(f"{fault.kind} injection targets unknown tool {tool_name}")
    if fault.kind == "empty_result":
        tools[tool_name] = _empty_tool
        return tools

    message = fault.message or "injected tool fault"

    def raise_fault(**kwargs: object) -> str:
        del kwargs
        raise RuntimeError(message)

    tools[tool_name] = raise_fault
    return tools


def _empty_tool(**kwargs: object) -> str:
    del kwargs
    return ""
