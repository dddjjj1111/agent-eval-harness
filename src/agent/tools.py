"""Three deterministic tools.

The knowledge base and the clock are fixtures. They are not live data.
The calculator accepts only arithmetic AST nodes so a model reply cannot
turn the tool into a Python interpreter.
"""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable

CLOCK_TEXT = "2026-01-15T09:00:00Z"

# Fixed demo facts. Keys are already normalized.
FACTS: dict[str, str] = {
    "capital of france": "Paris",
    "capital of japan": "Tokyo",
    "population of paris": "2100000",
    "population of tokyo": "13960000",
}

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expression: str) -> str:
    """Evaluate a single arithmetic expression and return a plain number string."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid expression: {expression}") from exc
    value = _eval_node(tree.body)
    return _format_number(value)


def lookup(query: str) -> str:
    """Return a fixture fact, or an empty string when nothing matches."""
    needle = _normalize(query)
    if not needle:
        return ""
    if needle in FACTS:
        return FACTS[needle]
    matches = [
        (key, value)
        for key, value in FACTS.items()
        if key in needle or needle in key
    ]
    if not matches:
        return ""
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def clock() -> str:
    """Return the fixed demo timestamp."""
    return CLOCK_TEXT


def build_registry() -> dict[str, Callable[..., str]]:
    return {
        "calculator": calculator,
        "lookup": lookup,
        "clock": clock,
    }


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            raise ValueError("only arithmetic expressions are allowed")
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("only arithmetic expressions are allowed")


def _format_number(value: float) -> str:
    if value.is_integer() and abs(value) < 10**15:
        return str(int(value))
    return str(value)


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return " ".join(cleaned.split())
