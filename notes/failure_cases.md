# Failure cases

The files under `scenarios/` with an `inject` block are expected to pass. A pass means the agent stayed inside the contract for that fault. A crash, a fabricated tool result, or a run that ignores the step limit fails the scenario.

Injection is applied outside the decision logic:

- `unknown_tool` and `max_steps` change what the mock model returns.
- `tool_raises` and `empty_result` replace one registered tool for that run.

The loop itself is unchanged. Traces are how the harness tells those cases apart.

## unknown_tool

Scenario: `unknown_tool`.

The model replies with a call to `weather`, which is not in the registry. The loop does not execute a tool. It appends a trace event of kind `unknown_tool` and returns that error to the model. The model then stops with "The requested tool is not available."

The checks look for that event, the attempted tool name, and the absence of a made-up forecast (`sunny`, `degrees`). A loop that called an unregistered name and invented a result would fail `answer_not_contains`. A loop that raised `KeyError` would be scored as `crashed`.

## tool_raises

Scenario: `tool_raises`.

The user asks for `2 plus 2`. The harness replaces `calculator` with a function that raises `RuntimeError`. The loop catches the exception, records `tool_error` with the message `injected calculator fault`, and does not include a numeric result in the final answer.

The checks require status `ok` (the process stayed up), tool sequence `[calculator]`, a `tool_error` event, and an answer that does not contain `The result is`. An uncaught exception fails the scenario as `crashed`. An agent that swallowed the error and still answered `4` would fail `answer_not_contains`.

## empty_tool_result

Scenario: `empty_tool_result`.

The question is the capital of France, which is in the fixture table. The harness forces `lookup` to return `""` anyway. The model treats an empty tool result as missing data and answers "No matching information was found."

The checks require that sentence and forbid `Paris`. This is the case that catches a model which ignores the tool output and fills in a fact from the question text. A natural miss (a query that is not in the fixture table) also returns an empty string; this scenario is different because the empty string is injected over a known fact.

## max_steps

Scenario: `max_steps`.

The fault makes the mock model return `calculator("1 + 1")` on every turn, so it never emits a final answer. `max_steps` is 3, counted as model turns. After the third tool call the loop stops, sets status `max_steps`, and answers "Stopped after reaching the maximum number of steps."

The checks require that status, exactly three calculator calls, and both a `tool_result` event and a `max_steps` event. A loop that kept going, or that treated a tool result as a final answer and returned status `ok`, would fail.

## What the other scenarios check

`calculator_add`, `lookup_capital`, `population_per_thousand`, and `system_clock` have no `inject` block. They check the happy path: tool order, and an answer that contains the tool output (including a regex on the arithmetic answer). `population_per_thousand` is two steps, lookup then calculator, and the final answer must be the quotient rather than the raw population.
