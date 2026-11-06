"""Load one scenario from a YAML or JSON mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agent.types import Fault

FAULT_KINDS = ("unknown_tool", "tool_raises", "empty_result", "max_steps")
TRACE_KINDS = ("final", "tool_result", "tool_error", "unknown_tool", "max_steps")
STATUSES = ("ok", "max_steps", "crashed")


class ScenarioNotFoundError(Exception):
    """Raised when a requested scenario name is not in the loaded set."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(name)


@dataclass
class Expectation:
    status: str | None = None
    tool_sequence: list[str] | None = None
    answer_contains: list[str] | None = None
    answer_not_contains: list[str] | None = None
    answer_regex: str | None = None
    trace_kinds: list[str] | None = None

    def defined_checks(self) -> bool:
        return any(
            value is not None
            for value in (
                self.status,
                self.tool_sequence,
                self.answer_contains,
                self.answer_not_contains,
                self.answer_regex,
                self.trace_kinds,
            )
        )


@dataclass
class Scenario:
    name: str
    description: str
    user_input: str
    max_steps: int
    fault: Fault | None
    expect: Expectation
    source_name: str


def scenario_from_mapping(data: object, source: Path) -> Scenario:
    label = source.name
    if not isinstance(data, dict):
        raise ValueError(f"{label}: scenario must be a mapping")

    name = _require_str(data.get("name"), label, "name")
    user_input = _require_str(data.get("user_input"), label, "user_input")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValueError(f"{label}: description must be a string")

    max_steps = data.get("max_steps", 6)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError(f"{label}: max_steps must be a positive integer")

    expect = _parse_expect(data.get("expect"), label)
    fault = _parse_fault(data.get("inject"), label)
    return Scenario(
        name=name,
        description=description,
        user_input=user_input,
        max_steps=max_steps,
        fault=fault,
        expect=expect,
        source_name=label,
    )


def _parse_fault(raw: object, label: str) -> Fault | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: inject must be a mapping")
    kind = raw.get("kind")
    if kind not in FAULT_KINDS:
        allowed = ", ".join(FAULT_KINDS)
        raise ValueError(f"{label}: inject.kind must be one of {allowed}")
    tool = raw.get("tool")
    if tool is not None and not isinstance(tool, str):
        raise ValueError(f"{label}: inject.tool must be a string")
    arguments = raw.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        raise ValueError(f"{label}: inject.arguments must be a mapping")
    message = raw.get("message")
    if message is not None and not isinstance(message, str):
        raise ValueError(f"{label}: inject.message must be a string")
    if kind == "unknown_tool" and not tool:
        raise ValueError(f"{label}: unknown_tool injection requires inject.tool")
    return Fault(kind=kind, tool=tool, arguments=arguments, message=message)


def _parse_expect(raw: object, label: str) -> Expectation:
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: expect must be a mapping")
    status = raw.get("status")
    if status is not None:
        if status not in STATUSES:
            allowed = ", ".join(STATUSES)
            raise ValueError(f"{label}: expect.status must be one of {allowed}")
    answer_regex = raw.get("answer_regex")
    if answer_regex is not None and not isinstance(answer_regex, str):
        raise ValueError(f"{label}: expect.answer_regex must be a string")
    trace_kinds = _optional_str_list(raw.get("trace_kinds"), label, "expect.trace_kinds")
    if trace_kinds is not None:
        unknown = [kind for kind in trace_kinds if kind not in TRACE_KINDS]
        if unknown:
            raise ValueError(f"{label}: unknown trace kinds {unknown}")
    expect = Expectation(
        status=status,
        tool_sequence=_optional_str_list(
            raw.get("tool_sequence"), label, "expect.tool_sequence"
        ),
        answer_contains=_optional_str_list(
            raw.get("answer_contains"), label, "expect.answer_contains"
        ),
        answer_not_contains=_optional_str_list(
            raw.get("answer_not_contains"), label, "expect.answer_not_contains"
        ),
        answer_regex=answer_regex,
        trace_kinds=trace_kinds,
    )
    if not expect.defined_checks():
        raise ValueError(f"{label}: expect must define at least one check")
    return expect


def _require_str(value: object, label: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: {field} is required")
    return value.strip()


def _optional_str_list(value: object, label: str, field: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label}: {field} must be a non-empty list of strings")
    return list(value)
