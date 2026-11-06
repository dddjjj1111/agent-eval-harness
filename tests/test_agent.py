"""Direct checks on the mock agent and its tools."""

import pytest

from src.agent.contract import (
    MSG_MAX_STEPS,
    MSG_NOT_FOUND,
    MSG_TOOL_FAILED,
    MSG_UNKNOWN_TOOL,
)
from src.agent.loop import run_agent
from src.agent.tools import CLOCK_TEXT, calculator, clock, lookup
from src.agent.types import Fault


def test_calculator_evaluates_arithmetic():
    assert calculator("17 + 25") == "42"
    assert calculator("13960000 / 1000") == "13960"
    assert calculator("(2 + 3) * 4") == "20"


def test_calculator_rejects_non_arithmetic():
    with pytest.raises(ValueError):
        calculator("__import__('os').system('echo hi')")
    with pytest.raises(ValueError):
        calculator("2 ** 3")
    with pytest.raises(ValueError):
        calculator("abs(2)")


def test_lookup_and_clock_are_fixtures():
    assert lookup("capital of France") == "Paris"
    assert lookup("population of Tokyo") == "13960000"
    assert lookup("capital of Atlantis") == ""
    assert clock() == CLOCK_TEXT


def test_unknown_tool_is_recorded_and_not_executed():
    result = run_agent(
        "What is the weather in Oslo?",
        fault=Fault(kind="unknown_tool", tool="weather", arguments={"city": "Oslo"}),
    )
    assert result.status == "ok"
    assert result.answer == MSG_UNKNOWN_TOOL
    kinds = [event.kind for event in result.trace]
    assert kinds == ["unknown_tool", "final"]
    assert result.trace[0].tool == "weather"
    assert result.trace[0].content == "Unknown tool: weather"


def test_tool_exception_is_captured():
    result = run_agent(
        "What is 2 plus 2?",
        fault=Fault(
            kind="tool_raises",
            tool="calculator",
            message="injected calculator fault",
        ),
    )
    assert result.status == "ok"
    assert result.answer == MSG_TOOL_FAILED
    error = next(event for event in result.trace if event.kind == "tool_error")
    assert error.tool == "calculator"
    assert error.content == "injected calculator fault"
    assert "4" not in result.answer


def test_empty_tool_result_does_not_invent_a_fact():
    result = run_agent(
        "What is the capital of France?",
        fault=Fault(kind="empty_result", tool="lookup"),
    )
    assert result.status == "ok"
    assert result.answer == MSG_NOT_FOUND
    assert "Paris" not in result.answer
    assert result.trace[0].kind == "tool_result"
    assert result.trace[0].content == ""


def test_max_steps_stops_a_model_that_never_finishes():
    result = run_agent("Keep calculating.", max_steps=3, fault=Fault(kind="max_steps"))
    assert result.status == "max_steps"
    assert result.answer == MSG_MAX_STEPS
    tool_events = [event for event in result.trace if event.kind == "tool_result"]
    assert len(tool_events) == 3
    assert [event.tool for event in tool_events] == ["calculator", "calculator", "calculator"]
    assert result.trace[-1].kind == "max_steps"


def test_two_step_lookup_then_divide():
    result = run_agent("Look up the population of Tokyo and divide it by 1000.")
    assert result.status == "ok"
    assert result.answer == "The result is 13960."
    tools = [event.tool for event in result.trace if event.tool]
    assert tools == ["lookup", "calculator"]
    assert result.trace[1].arguments == {"expression": "13960000 / 1000"}
