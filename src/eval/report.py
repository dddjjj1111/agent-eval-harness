"""JSON report and the text table printed by the CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.eval.scoring import Outcome, pass_rate


def build_report(outcomes: list[Outcome]) -> dict:
    passed = sum(1 for outcome in outcomes if outcome.passed)
    total = len(outcomes)
    return {
        "project": "agent-eval-harness",
        "use_mock_llm": os.environ.get("USE_MOCK_LLM", "1") == "1",
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(pass_rate(outcomes), 4),
        },
        "scenarios": [outcome.to_dict() for outcome in outcomes],
    }


def write_report(outcomes: list[Outcome], path: Path) -> dict:
    payload = build_report(outcomes)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def format_summary(outcomes: list[Outcome], report_path: Path) -> str:
    headers = ("scenario", "status", "result", "checks", "steps", "tools")
    rows = [_row(outcome) for outcome in outcomes]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(cells: tuple[str, ...]) -> str:
        return "  ".join(
            cell.ljust(widths[index]) for index, cell in enumerate(cells)
        ).rstrip()

    lines = [
        "agent-eval-harness",
        "",
        render(headers),
        render(tuple("-" * width for width in widths)),
    ]
    lines.extend(render(row) for row in rows)

    failures = _failure_lines(outcomes)
    if failures:
        lines.append("")
        lines.append("failed checks:")
        lines.extend(failures)

    passed = sum(1 for outcome in outcomes if outcome.passed)
    lines.append("")
    lines.append(f"{passed}/{len(outcomes)} passed")
    lines.append(f"report: {report_path}")
    return "\n".join(lines)


def _row(outcome: Outcome) -> tuple[str, ...]:
    tools = " ".join(outcome.tool_sequence) if outcome.tool_sequence else "-"
    return (
        outcome.name,
        outcome.status,
        "PASS" if outcome.passed else "FAIL",
        f"{outcome.checks_passed}/{outcome.checks_total}",
        str(outcome.steps),
        tools,
    )


def _failure_lines(outcomes: list[Outcome]) -> list[str]:
    lines: list[str] = []
    for outcome in outcomes:
        if outcome.passed:
            continue
        if outcome.error:
            lines.append(f"- {outcome.name} error: {outcome.error}")
        for check in outcome.checks:
            if not check.passed:
                lines.append(f"- {outcome.name} {check.name}: {check.detail}")
    return lines
