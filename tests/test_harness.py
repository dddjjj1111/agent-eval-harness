"""Scenario loading, scoring, and the bundled suite."""

import json
from pathlib import Path

import pytest

from src.agent.loop import run_agent
from src.eval.report import build_report
from src.eval.runner import load_scenarios, run_scenarios
from src.eval.schema import Expectation, Scenario, ScenarioNotFoundError
from src.eval.scoring import pass_rate, score_scenario

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
FAILURE_CASES = [
    "unknown_tool",
    "tool_raises",
    "empty_tool_result",
    "max_steps",
]
BUNDLED_NAMES = [
    "calculator_add",
    "lookup_capital",
    "population_per_thousand",
    "system_clock",
    "unknown_tool",
    "tool_raises",
    "empty_tool_result",
    "max_steps",
]


def test_bundled_scenarios_pass_rate():
    outcomes = run_scenarios(load_scenarios(SCENARIOS))
    assert [outcome.name for outcome in outcomes] == BUNDLED_NAMES
    assert len(outcomes) >= 6
    assert pass_rate(outcomes) == 1.0
    assert all(outcome.passed for outcome in outcomes)

    report = build_report(outcomes)
    assert report["summary"] == {
        "total": 8,
        "passed": 8,
        "failed": 0,
        "pass_rate": 1.0,
    }
    assert report["use_mock_llm"] is True
    calculator = next(item for item in report["scenarios"] if item["name"] == "calculator_add")
    assert calculator["answer"] == "The result is 42."
    assert calculator["trace"][0]["arguments"] == {"expression": "17 + 25"}


def test_failure_injection_subset():
    outcomes = run_scenarios(load_scenarios(SCENARIOS), names=FAILURE_CASES)
    assert [outcome.name for outcome in outcomes] == FAILURE_CASES
    assert pass_rate(outcomes) == 1.0
    by_name = {outcome.name: outcome for outcome in outcomes}

    unknown = by_name["unknown_tool"]
    assert unknown.status == "ok"
    assert unknown.tool_sequence == ["weather"]
    assert {event["kind"] for event in unknown.trace} >= {"unknown_tool", "final"}
    assert "sunny" not in unknown.answer

    raised = by_name["tool_raises"]
    assert any(event["kind"] == "tool_error" for event in raised.trace)
    assert any(
        event["content"] == "injected calculator fault" for event in raised.trace
    )
    assert "The result is" not in raised.answer

    empty = by_name["empty_tool_result"]
    assert empty.tool_sequence == ["lookup"]
    assert "Paris" not in empty.answer
    assert empty.trace[0]["content"] == ""

    limited = by_name["max_steps"]
    assert limited.status == "max_steps"
    assert limited.steps == 3
    assert limited.tool_sequence == ["calculator", "calculator", "calculator"]
    assert limited.trace[-1]["kind"] == "max_steps"


def test_score_fails_when_the_answer_does_not_match():
    scenario = Scenario(
        name="wrong_answer",
        description="",
        user_input="What is 2 plus 2?",
        max_steps=4,
        fault=None,
        expect=Expectation(status="ok", answer_contains=["5"]),
        source_name="memory",
    )
    result = run_agent(scenario.user_input, max_steps=scenario.max_steps)
    outcome = score_scenario(scenario, result, elapsed_ms=0)
    assert result.answer == "The result is 4."
    assert outcome.passed is False
    assert outcome.checks_passed == 1
    assert outcome.checks_total == 2
    failed = [check for check in outcome.checks if not check.passed]
    assert failed[0].name == "answer_contains"


def test_json_scenario_round_trip(tmp_path: Path):
    payload = {
        "name": "json_add",
        "description": "JSON scenario fixture.",
        "user_input": "What is 2 plus 2?",
        "max_steps": 4,
        "expect": {
            "status": "ok",
            "tool_sequence": ["calculator"],
            "answer_contains": ["4"],
            "answer_regex": r"^The result is 4\.$",
        },
    }
    (tmp_path / "json_add.json").write_text(json.dumps(payload), encoding="utf-8")
    outcomes = run_scenarios(load_scenarios(tmp_path))
    assert len(outcomes) == 1
    assert outcomes[0].passed is True
    assert outcomes[0].answer == "The result is 4."


def test_scenario_without_checks_is_rejected(tmp_path: Path):
    (tmp_path / "bad.yaml").write_text(
        "name: bad\nuser_input: hello\nexpect: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expect"):
        load_scenarios(tmp_path)


def test_unknown_scenario_name():
    with pytest.raises(ScenarioNotFoundError) as caught:
        run_scenarios(load_scenarios(SCENARIOS), names=["missing"])
    assert caught.value.name == "missing"
    assert "calculator_add" in caught.value.available
