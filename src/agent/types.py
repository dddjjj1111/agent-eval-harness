"""Data the agent loop and the eval harness share.

The harness owns scenarios and scores. The agent owns the loop. Fault is the
one eval hook on the agent: it lets a scenario inject a reproducible failure
without editing the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Fault:
    """A single fault applied to one agent run."""

    kind: str
    tool: str | None = None
    arguments: dict | None = None
    message: str | None = None


@dataclass
class Message:
    role: str
    content: str
    tool: str | None = None
    kind: str | None = None


@dataclass
class Decision:
    """One mock-model turn: either a tool call or a final answer."""

    kind: str
    content: str = ""
    tool: str | None = None
    arguments: dict | None = None


@dataclass
class TraceEvent:
    step: int
    kind: str
    tool: str | None = None
    arguments: dict | None = None
    content: str = ""


@dataclass
class AgentResult:
    status: str
    answer: str
    trace: list[TraceEvent] = field(default_factory=list)
    error: str | None = None
