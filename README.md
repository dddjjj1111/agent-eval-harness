# agent-eval-harness

Small teaching project. It runs a fixed set of scenarios against a mock tool-using agent and scores each run pass or fail. The agent and the model are stand-ins, so the harness can be shown without an API key.

This is not a production evaluation platform. It does not use LangChain, and it does not call a hosted model.

## Features

- A mock agent loop with three tools: `calculator`, `lookup`, and `clock`.
- Scenario files in YAML or JSON under `scenarios/`.
- Checks for status, tool sequence, answer substrings, answer regex, and trace event kinds.
- Fault injection for an unknown tool name, a tool exception, an empty tool result, and a step limit.
- A CLI that prints a pass/fail table and writes a JSON report.
- pytest coverage for the full suite pass rate and for each injected failure.

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`USE_MOCK_LLM` defaults to `1`. Any other value is rejected. Copy `.env.example` if you want the variable written down; the program does not load `.env` by itself.

```bash
export USE_MOCK_LLM=1
python -m src.main run
python -m src.main run --scenario calculator_add
pytest -q
```

Exit codes for `run`: `0` when every selected scenario passes, `1` when one fails, `2` for a bad argument, a missing scenario, or `USE_MOCK_LLM` set to something other than `1`.

The table from a full run:

```text
agent-eval-harness

scenario                 status     result  checks  steps  tools
-----------------------  ---------  ------  ------  -----  --------------------------------
calculator_add           ok         PASS    4/4     2      calculator
lookup_capital           ok         PASS    3/3     2      lookup
population_per_thousand  ok         PASS    4/4     3      lookup calculator
system_clock             ok         PASS    3/3     2      clock
unknown_tool             ok         PASS    5/5     2      weather
tool_raises              ok         PASS    5/5     2      calculator
empty_tool_result        ok         PASS    4/4     2      lookup
max_steps                max_steps  PASS    4/4     3      calculator calculator calculator

8/8 passed
report: reports/latest.json
```

`PASS` means the scenario expectations held, including the failure-injection scenarios. A fault that the agent mishandles is a `FAIL`.

## Layout

```text
src/agent/          mock loop, three tools, mock model
src/eval/           loader, scorer, JSON report, text table
src/main.py         CLI (`python -m src.main run`)
scenarios/          one scenario per YAML file
tests/              agent, harness, and CLI tests
notes/failure_cases.md
reports/            generated on each run; gitignored
```

The agent does not import the eval package. Scenarios call `run_agent` and, when they need a fault, pass a `Fault` value into that one run.

## How to add a scenario

Add a `.yaml` or `.json` file under `scenarios/`. Files are loaded in filename order. `name` is what `--scenario` matches.

```yaml
name: capital_of_japan
description: One-sentence note on what this case locks in.
user_input: What is the capital of Japan?
max_steps: 4
expect:
  status: ok
  tool_sequence:
    - lookup
  answer_contains:
    - Tokyo
```

`expect` needs at least one of `status`, `tool_sequence`, `answer_contains`, `answer_not_contains`, `answer_regex`, and `trace_kinds`. `status` is `ok` (the model produced a final answer), `max_steps` (the loop stopped at the limit), or `crashed` (an exception escaped the loop).

Optional `inject`:

| `kind` | What changes for that run |
| --- | --- |
| `unknown_tool` | The mock model calls `inject.tool`, which must not be a registered tool. |
| `tool_raises` | The named registered tool raises `RuntimeError`. |
| `empty_result` | The named registered tool returns an empty string. |
| `max_steps` | The mock model requests `calculator` on every turn and never finishes. |

The mock model only understands a few phrasings: `capital of <Word>`, `population of <Word>`, `<n> plus|minus|times|divided by <n>`, a raw `a + b` expression, and a question that mentions the clock. Lookup data and the clock value are fixtures in `src/agent/tools.py`. Recovery sentences live in `src/agent/contract.py`; if you change one, update the scenario that asserts it.

`notes/failure_cases.md` describes what each injected fault is meant to catch.

## Notes

- The model is a script in `src/agent/llm.py`. Same input, same trace. There is no sampling and no network.
- `lookup` answers from a fixed table (France/Paris, Japan/Tokyo, and two population figures). `clock` always returns `2026-01-15T09:00:00Z`.
- The calculator evaluates arithmetic AST nodes only. Names, calls, and operators such as `**` are rejected.
- `max_steps` counts model turns. A final answer uses one turn.
- The JSON report includes the summary, each check, and the trace. The default path is `reports/latest.json`.
