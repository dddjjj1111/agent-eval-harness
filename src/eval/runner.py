"""Execute scenarios and collect scored outcomes."""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from src.agent.loop import run_agent
from src.agent.types import AgentResult
from src.eval.schema import Scenario, ScenarioNotFoundError, scenario_from_mapping
from src.eval.scoring import Outcome, score_scenario


def default_scenarios_dir() -> Path:
    local = Path.cwd() / "scenarios"
    if local.is_dir():
        return local
    return Path(__file__).resolve().parents[2] / "scenarios"


def load_scenarios(directory: Path) -> list[Scenario]:
    if not directory.is_dir():
        raise FileNotFoundError(f"scenarios directory not found: {directory}")
    paths = sorted(
        [
            *directory.glob("*.yaml"),
            *directory.glob("*.yml"),
            *directory.glob("*.json"),
        ],
        key=lambda path: path.name,
    )
    if not paths:
        raise FileNotFoundError(f"no scenarios in {directory}")
    scenarios = [_load_file(path) for path in paths]
    names = [scenario.name for scenario in scenarios]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate scenario names: {duplicates}")
    return scenarios


def run_scenarios(
    scenarios: list[Scenario],
    *,
    names: list[str] | None = None,
) -> list[Outcome]:
    selected = _select(scenarios, names)
    return [_execute(scenario) for scenario in selected]


def _select(scenarios: list[Scenario], names: list[str] | None) -> list[Scenario]:
    if not names:
        return list(scenarios)
    by_name = {scenario.name: scenario for scenario in scenarios}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise ScenarioNotFoundError(missing[0], [scenario.name for scenario in scenarios])
    return [by_name[name] for name in names]


def _execute(scenario: Scenario) -> Outcome:
    started = time.perf_counter()
    try:
        result = run_agent(
            scenario.user_input,
            max_steps=scenario.max_steps,
            fault=scenario.fault,
        )
    except Exception as exc:
        result = AgentResult(
            status="crashed",
            answer="",
            trace=[],
            error=f"{exc.__class__.__name__}: {exc}",
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return score_scenario(scenario, result, elapsed_ms)


def _load_file(path: Path) -> Scenario:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    return scenario_from_mapping(data, path)
