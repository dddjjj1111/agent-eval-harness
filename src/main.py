"""CLI for the demo harness.

Examples:
    python -m src.main run
    python -m src.main run --scenario calculator_add
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.agent.loop import MockLLMRequired, ensure_mock_llm
from src.eval.report import format_summary, write_report
from src.eval.runner import default_scenarios_dir, load_scenarios, run_scenarios
from src.eval.schema import ScenarioNotFoundError


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    parser.print_help(sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description=(
            "Run scripted scenarios against the mock agent. "
            "Teaching demo, not a production eval platform."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="score scenarios and write a JSON report")
    run_parser.add_argument(
        "--scenario",
        help="run one scenario by name (default: every file under scenarios/)",
    )
    run_parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=None,
        help="directory of YAML or JSON scenarios (default: ./scenarios)",
    )
    run_parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/latest.json"),
        help="where to write the JSON report (default: reports/latest.json)",
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    try:
        ensure_mock_llm()
    except MockLLMRequired as exc:
        print(str(exc), file=sys.stderr)
        return 2

    directory = args.scenarios_dir or default_scenarios_dir()
    try:
        scenarios = load_scenarios(directory)
        names = [args.scenario] if args.scenario else None
        outcomes = run_scenarios(scenarios, names=names)
    except ScenarioNotFoundError as exc:
        available = ", ".join(exc.available)
        print(f"scenario not found: {exc.name}", file=sys.stderr)
        print(f"available: {available}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    write_report(outcomes, args.report)
    print(format_summary(outcomes, args.report))
    return 0 if all(outcome.passed for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
