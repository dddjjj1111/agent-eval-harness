"""CLI exit codes, the text table, and the JSON report."""

import json
import os
import subprocess
import sys
from pathlib import Path

from src.main import main

ROOT = Path(__file__).resolve().parents[1]


def test_run_writes_a_passing_table(tmp_path: Path, capsys):
    report = tmp_path / "report.json"
    code = main(["run", "--report", str(report)])
    captured = capsys.readouterr()
    assert code == 0
    assert "agent-eval-harness" in captured.out
    assert "calculator_add" in captured.out
    assert "max_steps" in captured.out
    assert "PASS" in captured.out
    assert "FAIL" not in captured.out
    assert "8/8 passed" in captured.out
    assert f"report: {report}" in captured.out

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["project"] == "agent-eval-harness"
    assert payload["summary"]["pass_rate"] == 1.0
    assert len(payload["scenarios"]) == 8


def test_run_one_scenario(tmp_path: Path, capsys):
    report = tmp_path / "one.json"
    code = main(["run", "--scenario", "lookup_capital", "--report", str(report)])
    captured = capsys.readouterr()
    assert code == 0
    assert "lookup_capital" in captured.out
    assert "1/1 passed" in captured.out
    assert "calculator_add" not in captured.out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["scenarios"][0]["answer"] == "The answer is Paris."


def test_failed_check_exits_1(tmp_path: Path, capsys):
    scenario = tmp_path / "bad_expect.yaml"
    scenario.write_text(
        "\n".join(
            [
                "name: bad_expect",
                "user_input: What is 2 plus 2?",
                "expect:",
                "  status: ok",
                "  answer_contains:",
                '    - "5"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    code = main(["run", "--scenarios-dir", str(tmp_path), "--report", str(report)])
    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL" in captured.out
    assert "0/1 passed" in captured.out
    assert "answer_contains" in captured.out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"]["failed"] == 1


def test_missing_scenario_exits_2(capsys):
    code = main(["run", "--scenario", "not_a_scenario"])
    captured = capsys.readouterr()
    assert code == 2
    assert "scenario not found: not_a_scenario" in captured.err
    assert "calculator_add" in captured.err


def test_non_mock_llm_is_rejected(monkeypatch, capsys):
    monkeypatch.setenv("USE_MOCK_LLM", "0")
    code = main(["run"])
    captured = capsys.readouterr()
    assert code == 2
    assert "USE_MOCK_LLM=1" in captured.err


def test_module_entrypoint(tmp_path: Path):
    report = tmp_path / "cli.json"
    env = os.environ.copy()
    env["USE_MOCK_LLM"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "run", "--scenario", "calculator_add", "--report", str(report)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "calculator_add" in result.stdout
    assert "PASS" in result.stdout
    assert "1/1 passed" in result.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert "42" in payload["scenarios"][0]["answer"]
