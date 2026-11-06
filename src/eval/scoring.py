"""Compare one agent result with one scenario expectation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from src.agent.types import AgentResult
from src.eval.schema import Scenario

_TOOL_EVENTS = {"tool_result", "tool_error", "unknown_tool"}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class Outcome:
    name: str
    description: str
    source_name: str
    user_input: str
    passed: bool
    status: str
    answer: str
    tool_sequence: list[str]
    steps: int
    checks: list[Check]
    trace: list[dict]
    elapsed_ms: float
    inject: dict | None = None
    error: str | None = None
    checks_passed: int = 0
    checks_total: int = 0

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["elapsed_ms"] = round(self.elapsed_ms, 2)
        return payload


def score_scenario(scenario: Scenario, result: AgentResult, elapsed_ms: float) -> Outcome:
    sequence = tool_sequence(result)
    checks = _checks(scenario, result, sequence)
    passed = all(check.passed for check in checks)
    steps = max((event.step for event in result.trace), default=0)
    inject = None
    if scenario.fault is not None:
        inject = {
            "kind": scenario.fault.kind,
            "tool": scenario.fault.tool,
            "arguments": scenario.fault.arguments,
            "message": scenario.fault.message,
        }
    return Outcome(
        name=scenario.name,
        description=scenario.description,
        source_name=scenario.source_name,
        user_input=scenario.user_input,
        passed=passed,
        status=result.status,
        answer=result.answer,
        tool_sequence=sequence,
        steps=steps,
        checks=checks,
        trace=[asdict(event) for event in result.trace],
        elapsed_ms=elapsed_ms,
        inject=inject,
        error=result.error,
        checks_passed=sum(1 for check in checks if check.passed),
        checks_total=len(checks),
    )


def tool_sequence(result: AgentResult) -> list[str]:
    return [
        event.tool
        for event in result.trace
        if event.tool and event.kind in _TOOL_EVENTS
    ]


def pass_rate(outcomes: list[Outcome]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for outcome in outcomes if outcome.passed) / len(outcomes)


def _checks(scenario: Scenario, result: AgentResult, sequence: list[str]) -> list[Check]:
    expect = scenario.expect
    checks: list[Check] = []
    if expect.status is not None:
        ok = result.status == expect.status
        checks.append(
            Check("status", ok, f"expected {expect.status}, got {result.status}")
        )
    if expect.tool_sequence is not None:
        ok = sequence == expect.tool_sequence
        checks.append(
            Check(
                "tool_sequence",
                ok,
                f"expected {expect.tool_sequence}, got {sequence}",
            )
        )
    if expect.answer_contains is not None:
        missing = [item for item in expect.answer_contains if item not in result.answer]
        checks.append(
            Check(
                "answer_contains",
                not missing,
                "matched" if not missing else f"missing {missing}",
            )
        )
    if expect.answer_not_contains is not None:
        present = [item for item in expect.answer_not_contains if item in result.answer]
        checks.append(
            Check(
                "answer_not_contains",
                not present,
                "absent" if not present else f"found {present}",
            )
        )
    if expect.answer_regex is not None:
        matched = re.search(expect.answer_regex, result.answer) is not None
        checks.append(
            Check(
                "answer_regex",
                matched,
                f"pattern {expect.answer_regex!r} against {result.answer!r}",
            )
        )
    if expect.trace_kinds is not None:
        kinds = {event.kind for event in result.trace}
        missing = [kind for kind in expect.trace_kinds if kind not in kinds]
        checks.append(
            Check(
                "trace_kinds",
                not missing,
                "present" if not missing else f"missing {missing}",
            )
        )
    if not checks:
        checks.append(Check("expectation", False, "scenario defines no checks"))
    return checks
